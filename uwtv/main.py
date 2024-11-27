import hashlib
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI(title="Video Streaming API")

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração do diretório de vídeos
VIDEO_DIR = Path(__file__).parent.parent / "downloads"
VIDEO_DIR.mkdir(exist_ok=True)

# Dicionário global para armazenar o mapeamento de IDs para caminhos de vídeo
video_mapping: Dict[str, Path] = {}


def generate_video_id(file_path: Path) -> str:
    """
    Gera um ID único para um vídeo baseado em seu caminho completo.
    Usa um hash curto para criar IDs legíveis mas únicos.
    """
    path_str = str(file_path.absolute())
    return hashlib.md5(path_str.encode()).hexdigest()[:8]


def scan_video_directory() -> List[Dict]:
    """
    Faz uma varredura recursiva do diretório de vídeos e cria uma lista
    de dicionários com informações sobre cada vídeo.
    """
    video_mapping.clear()
    video_list = []

    # Extensões de vídeo suportadas
    video_extensions = {'.mp4', '.webm'}

    # Busca recursivamente por arquivos de vídeo
    for video_path in VIDEO_DIR.rglob('*'):
        if video_path.is_file() and video_path.suffix.lower() in video_extensions:
            # Gera um ID único para o vídeo
            video_id = generate_video_id(video_path)

            # Cria o caminho relativo para exibição
            relative_path = video_path.relative_to(VIDEO_DIR)

            # Armazena o mapeamento de ID para caminho real
            video_mapping[video_id] = video_path

            # Adiciona à lista de vídeos
            video_list.append({
                'id': video_id,
                'name': video_path.name,
                'path': str(relative_path),
                'type': video_path.suffix.lower()[1:]  # Remove o ponto da extensão
            })

    return video_list


def generate_video_stream(video_path: Path):
    """
    Gera um stream do arquivo de vídeo em chunks.
    """
    CHUNK_SIZE = 1024 * 1024  # 1MB por chunk

    try:
        with open(video_path, "rb") as video_file:
            while chunk := video_file.read(CHUNK_SIZE):
                yield chunk
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler o arquivo: {str(e)}")


@app.get("/videos")
async def list_videos():
    """
    Lista todos os vídeos disponíveis no diretório e subdiretórios.
    Retorna uma lista com ID, nome e caminho relativo de cada vídeo.
    """
    try:
        videos = scan_video_directory()
        return {"videos": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar vídeos: {str(e)}")


@app.get("/video/{video_id}")
async def stream_video(video_id: str):
    """
    Endpoint para streaming de vídeo usando o ID do vídeo.
    """
    if video_id not in video_mapping:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    video_path = video_mapping[video_id]

    # Determina o content-type baseado na extensão do arquivo
    content_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm'
    }

    content_type = content_types.get(video_path.suffix.lower())
    if not content_type:
        raise HTTPException(status_code=400, detail="Formato de vídeo não suportado")

    return StreamingResponse(
        generate_video_stream(video_path),
        media_type=content_type
    )
