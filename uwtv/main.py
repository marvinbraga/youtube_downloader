# main.py
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List

# Importante: Use PyJWT, não o módulo jwt
import jwt as PyJWT
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from loguru import logger


# Modelos para autenticação
class TokenData(BaseModel):
    access_token: str
    token_type: str


class ClientAuth(BaseModel):
    client_id: str
    client_secret: str


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

# Sistema simplificado de autenticação (use um banco de dados em produção)
AUTHORIZED_CLIENTS = {
    "your_client_id": {
        "secret": "your_client_secret",
        "name": "Your Application"
    }
}

video_mapping: Dict[str, Path] = {}
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Cria um novo token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    # PyJWT.encode retorna bytes em algumas versões, então convertemos para str
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


def generate_video_id(file_path: Path) -> str:
    """Gera um ID único para um vídeo"""
    path_str = str(file_path.absolute())
    return hashlib.md5(path_str.encode()).hexdigest()[:8]


def get_video_info(video_path: Path) -> dict:
    """Coleta informações sobre um arquivo de vídeo"""
    stats = video_path.stat()
    return {
        'id': generate_video_id(video_path),
        'name': get_clean_filename(video_path),
        'path': str(video_path.relative_to(VIDEO_DIR)),
        'type': video_path.suffix.lower()[1:],
        'created_date': datetime.fromtimestamp(stats.st_ctime).isoformat(),
        'modified_date': datetime.fromtimestamp(stats.st_mtime).isoformat(),
        'size': stats.st_size
    }


def scan_video_directory(sort_by: SortOption = SortOption.NONE) -> List[Dict]:
    """Escaneia o diretório de vídeos recursivamente"""
    video_mapping.clear()
    video_list = []

    video_extensions = {'.mp4', '.webm'}

    for video_path in VIDEO_DIR.rglob('*'):
        if video_path.is_file() and video_path.suffix.lower() in video_extensions:
            video_info = get_video_info(video_path)
            video_mapping[video_info['id']] = video_path
            video_list.append(video_info)

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
        logger.error(f"Erro ao ler o arquivo: {str(e)}")
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

    video_path = video_mapping[video_id]
    content_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm'
    }

    content_type = content_types.get(video_path.suffix.lower())
    if not content_type:
        logger.error("Formato de vídeo não suportado.")
        raise HTTPException(status_code=400, detail="Formato de vídeo não suportado")

    logger.debug(f"Recuperando conteúdo do vídeo. Token: {token_data}")
    return StreamingResponse(
        generate_video_stream(video_path),
        media_type=content_type
    )
