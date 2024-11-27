import hashlib
import json
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

# Importante: Use PyJWT, não o módulo jwt
import jwt as PyJWT
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
from pydantic import BaseModel, HttpUrl

from uwtv.managers import VideoStreamManager


# Modelos para autenticação
class TokenData(BaseModel):
    access_token: str
    token_type: str


class ClientAuth(BaseModel):
    client_id: str
    client_secret: str


# Modelo para representar um vídeo
class VideoSource(str, Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"


class VideoInfo(BaseModel):
    id: str
    name: str
    path: str
    type: str
    created_date: str
    modified_date: str
    size: int
    source: VideoSource
    youtube_url: Optional[HttpUrl] = None


# Configurações de segurança
# Em produção, mova estas configurações para um arquivo .env
SECRET_KEY = "seu_secret_key_muito_secreto"  # Altere para uma chave segura em produção
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class SortOption(str, Enum):
    TITLE = "title"
    DATE = "date"
    NONE = "none"


app = FastAPI(title="Video Streaming API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEO_DIR = Path(__file__).parent.parent / "downloads"
VIDEO_DIR.mkdir(exist_ok=True)
JSON_CONFIG_PATH = Path(__file__).parent.parent / "data" / "videos.json"

# Sistema simplificado de autenticação (use um banco de dados em produção)
AUTHORIZED_CLIENTS = {
    "your_client_id": {
        "secret": "your_client_secret",
        "name": "Your Application"
    }
}

video_mapping: Dict[str, Union[Path, str]] = {}
security = HTTPBearer()
# Instância global do gerenciador de streaming
stream_manager = VideoStreamManager()


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Cria um novo token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = PyJWT.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    logger.debug("encoded_jwt: {}".format(encoded_jwt))
    if isinstance(encoded_jwt, bytes):
        return encoded_jwt.decode('utf-8')
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verifica se o token é válido"""
    try:
        token = credentials.credentials
        payload = PyJWT.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: str = payload.get("sub")

        if client_id not in AUTHORIZED_CLIENTS:
            raise HTTPException(
                status_code=401,
                detail="Cliente não autorizado"
            )

        return payload
    except PyJWT.ExpiredSignatureError:
        logger.error("Token expirado.")
        raise HTTPException(
            status_code=401,
            detail="Token expirado"
        )
    except PyJWT.JWTError:
        logger.error("Token invalido.")
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )


def get_clean_filename(file_path: Path) -> str:
    """Remove a extensão do nome do arquivo"""
    name = file_path.name
    video_extensions = {'.mp4', '.webm'}
    for ext in video_extensions:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    return name


def generate_video_id(identifier: Union[Path, str]) -> str:
    """Gera um ID único para um vídeo baseado no caminho ou URL"""
    identifier_str = str(identifier)
    return hashlib.md5(identifier_str.encode()).hexdigest()[:8]


def get_video_info(video_path: Path) -> dict:
    """Coleta informações sobre um arquivo de vídeo local"""
    stats = video_path.stat()
    return {
        'id': generate_video_id(video_path),
        'name': get_clean_filename(video_path),
        'path': str(video_path.relative_to(VIDEO_DIR)),
        'type': video_path.suffix.lower()[1:],
        'created_date': datetime.fromtimestamp(stats.st_ctime).isoformat(),
        'modified_date': datetime.fromtimestamp(stats.st_mtime).isoformat(),
        'size': stats.st_size,
        'source': VideoSource.LOCAL,
        'youtube_url': None
    }


def load_json_videos() -> List[Dict]:
    """Carrega a configuração de vídeos do arquivo JSON"""
    try:
        if JSON_CONFIG_PATH.exists():
            with open(JSON_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Validação básica dos dados
            for video in data["videos"]:
                if 'youtube_url' in video:
                    video['source'] = VideoSource.YOUTUBE
                    video['id'] = generate_video_id(video['youtube_url'])
                    video_mapping[video['id']] = video['youtube_url']
            return data["videos"]
        return []
    except Exception as e:
        logger.error(f"Erro ao carregar arquivo JSON: {str(e)}")
        return []


def scan_video_directory(sort_by: SortOption = SortOption.NONE) -> List[Dict]:
    """Escaneia o diretório de vídeos e combina com os vídeos do JSON"""
    video_mapping.clear()
    video_list = []

    # Carrega vídeos locais
    video_extensions = {'.mp4', '.webm'}
    for video_path in VIDEO_DIR.rglob('*'):
        if video_path.is_file() and video_path.suffix.lower() in video_extensions:
            video_info = get_video_info(video_path)
            video_mapping[video_info['id']] = video_path
            video_list.append(video_info)

    # Carrega vídeos do JSON
    json_videos = load_json_videos()
    video_list.extend(json_videos)

    # Aplica ordenação
    if sort_by == SortOption.TITLE:
        video_list.sort(key=lambda x: x['name'].lower())
    elif sort_by == SortOption.DATE:
        video_list.sort(key=lambda x: x['modified_date'], reverse=True)

    return video_list


def generate_video_stream(video_path: Path):
    """Gera o stream de vídeo em chunks"""
    CHUNK_SIZE = 1024 * 1024  # 1MB por chunk
    try:
        with open(video_path, "rb") as video_file:
            while chunk := video_file.read(CHUNK_SIZE):
                yield chunk
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler o arquivo: {str(e)}")


@app.post("/auth/token", response_model=TokenData)
async def login_for_access_token(client: ClientAuth):
    """Endpoint para autenticação do cliente"""
    if (client.client_id not in AUTHORIZED_CLIENTS or
            AUTHORIZED_CLIENTS[client.client_id]["secret"] != client.client_secret):
        logger.error("Credenciais inválidas.")
        raise HTTPException(
            status_code=401,
            detail="Credenciais inválidas"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": client.client_id},
        expires_delta=access_token_expires
    )

    result = {"access_token": access_token, "token_type": "bearer"}
    logger.debug(f"Credenciais: {result}")
    return result


@app.get("/videos")
async def list_videos(
        sort_by: SortOption = Query(SortOption.NONE),
        token_data: dict = Depends(verify_token)
):
    """Lista todos os vídeos (requer autenticação)"""
    logger.debug(f"Listando vídeos. Token: {token_data}")
    try:
        videos = scan_video_directory(sort_by)
        return {"videos": videos}
    except Exception as e:
        logger.error(f"Erro ao listar vídeos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar vídeos: {str(e)}")


@app.get("/video/{video_id}")
async def stream_video(
        video_id: str,
        token_data: dict = Depends(verify_token)
):
    """Stream de vídeo (requer autenticação)"""
    if video_id not in video_mapping:
        logger.error("Vídeo não encontrado.")
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    video_source = video_mapping[video_id]

    # Se for uma URL do YouTube
    if isinstance(video_source, str) and video_source.startswith('http'):
        logger.debug(f"Iniciando streaming do YouTube: {video_source}")
        return StreamingResponse(
            stream_manager.stream_youtube_video(video_source),
            media_type='video/mp4'  # YouTube geralmente fornece MP4
        )

    # Para vídeos locais, mantém o código original
    video_path = video_source
    content_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm'
    }

    content_type = content_types.get(video_path.suffix.lower())
    if not content_type:
        logger.error("Formato de vídeo não suportado.")
        raise HTTPException(status_code=400, detail="Formato de vídeo não suportado")

    return StreamingResponse(
        generate_video_stream(video_path),
        media_type=content_type
    )
