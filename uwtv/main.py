import hashlib
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse


class SortOption(str, Enum):
    """Define as opções de ordenação disponíveis"""
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

video_mapping: Dict[str, Path] = {}


def generate_video_id(file_path: Path) -> str:
    """Gera um ID único para um vídeo baseado em seu caminho"""
    path_str = str(file_path.absolute())
    return hashlib.md5(path_str.encode()).hexdigest()[:8]


def get_video_info(video_path: Path) -> dict:
    """Coleta informações detalhadas sobre um arquivo de vídeo"""
    stats = video_path.stat()
    return {
        'id': generate_video_id(video_path),
        'name': video_path.name,
        'path': str(video_path.relative_to(VIDEO_DIR)),
        'type': video_path.suffix.lower()[1:],
        'created_date': datetime.fromtimestamp(stats.st_ctime).isoformat(),
        'modified_date': datetime.fromtimestamp(stats.st_mtime).isoformat(),
        'size': stats.st_size
    }


def scan_video_directory(sort_by: SortOption = SortOption.NONE) -> List[Dict]:
    """
    Faz uma varredura recursiva do diretório de vídeos e retorna uma lista ordenada
    de acordo com o critério especificado
    """
    video_mapping.clear()
    video_list = []

    video_extensions = {'.mp4', '.webm'}

    for video_path in VIDEO_DIR.rglob('*'):
        if video_path.is_file() and video_path.suffix.lower() in video_extensions:
            video_info = get_video_info(video_path)
            video_mapping[video_info['id']] = video_path
            video_list.append(video_info)

    # Aplica a ordenação conforme solicitado
    if sort_by == SortOption.TITLE:
        video_list.sort(key=lambda x: x['name'].lower())
    elif sort_by == SortOption.DATE:
        video_list.sort(key=lambda x: x['modified_date'], reverse=True)

    return video_list


def generate_video_stream(video_path: Path):
    """Gera um stream do arquivo de vídeo em chunks"""
    CHUNK_SIZE = 1024 * 1024  # 1MB por chunk

    try:
        with open(video_path, "rb") as video_file:
            while chunk := video_file.read(CHUNK_SIZE):
                yield chunk
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler o arquivo: {str(e)}")


@app.get("/videos")
async def list_videos(sort_by: SortOption = Query(SortOption.NONE, description="Opção de ordenação")):
    """
    Lista todos os vídeos disponíveis no diretório e subdiretórios.
    Permite ordenação por título ou data de modificação.
    """
    try:
        videos = scan_video_directory(sort_by)
        return {"videos": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar vídeos: {str(e)}")


@app.get("/video/{video_id}")
async def stream_video(video_id: str):
    """Endpoint para streaming de vídeo usando o ID"""
    if video_id not in video_mapping:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    video_path = video_mapping[video_id]

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
