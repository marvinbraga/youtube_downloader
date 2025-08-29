import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Union, List, Dict

from fastapi import HTTPException
from loguru import logger

from app.models.video import VideoSource, SortOption
from app.models.audio import AudioSource
from app.services.configs import VIDEO_DIR, JSON_CONFIG_PATH, video_mapping, AUDIO_DIR, audio_mapping
from app.services.locks import audio_file_lock


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
        'url': None
    }


def load_json_videos() -> List[Dict]:
    """Carrega a configuração de vídeos do arquivo JSON"""
    try:
        if JSON_CONFIG_PATH.exists():
            with open(JSON_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Validação básica dos dados
            for video in data["videos"]:
                if 'url' in video:
                    video['source'] = VideoSource.YOUTUBE
                    video['id'] = generate_video_id(video['url'])
                    video_mapping[video['id']] = video['url']
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


def generate_audio_stream(audio_path: Path):
    """Gera o stream de áudio em chunks"""
    CHUNK_SIZE = 1024 * 1024  # 1MB por chunk
    try:
        with open(audio_path, "rb") as audio_file:
            while chunk := audio_file.read(CHUNK_SIZE):
                yield chunk
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler o arquivo de áudio: {str(e)}")


def load_json_audios() -> Dict:
    """
    Função obsoleta - sistema agora usa apenas Redis para dados de áudio
    
    Returns:
        Dicionário vazio (para compatibilidade)
    """
    logger.warning("load_json_audios() called but audios.json is no longer used. Returning empty data.")
    return {"audios": [], "mappings": {}}


def scan_audio_directory() -> List[Dict]:
    """
    Escaneia o diretório de áudios usando apenas dados do Redis
    Sistema não usa mais audios.json
    
    Returns:
        Lista vazia - use RedisAudioDownloadManager.get_audio_data_async() para dados reais
    """
    audio_mapping.clear()
    
    # Log de aviso para migração
    logger.warning("scan_audio_directory() called but audios.json is no longer used. Use Redis-based methods instead.")
    
    # Verificar se há integração Redis ativa
    try:
        from app.services.integration_patch import is_redis_integration_active
        if is_redis_integration_active():
            logger.info("Redis integration is active. Use RedisAudioDownloadManager.get_audio_data_async() for audio data.")
    except ImportError:
        logger.error("Redis integration not available. Audio functionality may be limited.")
    
    return []