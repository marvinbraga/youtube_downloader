"""
Redis Files Adapter - Adaptador para migração gradual de files.py para Redis
Mantém interface idêntica ao sistema atual enquanto usa Redis como backend
"""

import asyncio
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Union, List, Dict

from fastapi import HTTPException
from loguru import logger

from app.models.video import VideoSource, SortOption
from app.models.audio import AudioSource
from app.services.configs import VIDEO_DIR, JSON_CONFIG_PATH, video_mapping, AUDIO_DIR, audio_mapping
from app.services.redis_audio_manager import redis_audio_manager
from app.services.redis_video_manager import redis_video_manager
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
    """
    Carrega a configuração de vídeos do arquivo JSON.
    Mantém compatibilidade com sistema atual.
    """
    use_redis = os.getenv('USE_REDIS', 'true').lower() == 'true'
    
    if use_redis:
        return asyncio.run(_load_json_videos_redis())
    else:
        return _load_json_videos_original()


async def _load_json_videos_redis() -> List[Dict]:
    """Versão Redis para carregar vídeos"""
    try:
        videos = await redis_video_manager.get_videos_by_source(VideoSource.YOUTUBE)
        
        # Atualizar mapeamento em memória para compatibilidade
        for video in videos:
            video_id = video.get('id')
            url = video.get('url')
            if video_id and url:
                video_mapping[video_id] = url
        
        return videos
    except Exception as e:
        logger.error(f"Erro ao carregar vídeos do Redis: {str(e)}")
        return []


def _load_json_videos_original() -> List[Dict]:
    """Versão original JSON para carregar vídeos"""
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
    """
    Escaneia o diretório de vídeos e combina com os vídeos remotos.
    Adaptado para usar Redis quando habilitado.
    """
    use_redis = os.getenv('USE_REDIS', 'true').lower() == 'true'
    
    if use_redis:
        return asyncio.run(_scan_video_directory_redis(sort_by))
    else:
        return _scan_video_directory_original(sort_by)


async def _scan_video_directory_redis(sort_by: SortOption = SortOption.NONE) -> List[Dict]:
    """Versão Redis para scan de vídeos"""
    try:
        video_list = await redis_video_manager.scan_video_directory(sort_by)
        
        # Atualizar mapeamento em memória para compatibilidade
        video_mapping.clear()
        for video in video_list:
            video_id = video.get('id')
            if video.get('source') == VideoSource.LOCAL.value:
                # Para vídeos locais, mapear para o Path
                path = video.get('path')
                if video_id and path:
                    video_mapping[video_id] = VIDEO_DIR / path
            elif video.get('source') == VideoSource.YOUTUBE.value:
                # Para vídeos remotos, mapear para URL
                url = video.get('url')
                if video_id and url:
                    video_mapping[video_id] = url
        
        return video_list
    except Exception as e:
        logger.error(f"Erro no scan de vídeos Redis: {str(e)}")
        return []


def _scan_video_directory_original(sort_by: SortOption = SortOption.NONE) -> List[Dict]:
    """Versão original para scan de vídeos"""
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
    Carrega os dados de áudio, adaptado para usar Redis quando habilitado.
    Mantém interface idêntica ao sistema atual.
    """
    use_redis = os.getenv('USE_REDIS', 'true').lower() == 'true'
    
    if use_redis:
        return asyncio.run(_load_json_audios_redis())
    else:
        return _load_json_audios_original()


async def _load_json_audios_redis() -> Dict:
    """Versão Redis para carregar áudios"""
    try:
        # Obter todos os áudios do Redis
        audios = await redis_audio_manager.get_all_audios()
        
        # Construir mappings para compatibilidade
        mappings = {}
        
        for audio in audios:
            audio_id = audio.get("id", "")
            path = audio.get("path", "")
            
            if audio_id and path:
                full_path = AUDIO_DIR.parent / path
                audio_mapping[audio_id] = full_path
                mappings[audio_id] = path
                
                # Adicionar mapeamentos por palavras-chave
                keywords = audio.get("keywords", [])
                if isinstance(keywords, list):
                    for keyword in keywords:
                        audio_mapping[keyword] = full_path
                        mappings[keyword] = path
        
        return {
            "audios": audios,
            "mappings": mappings
        }
    except Exception as e:
        logger.error(f"Erro ao carregar áudios do Redis: {str(e)}")
        return {"audios": [], "mappings": {}}


def _load_json_audios_original() -> Dict:
    """Função obsoleta - sistema não usa mais audios.json"""
    logger.warning("_load_json_audios_original() called but audios.json is no longer used")
    return {"audios": [], "mappings": {}}


def scan_audio_directory() -> List[Dict]:
    """
    Escaneia o diretório de áudios e retorna informações dos arquivos.
    Adaptado para usar Redis quando habilitado.
    """
    use_redis = os.getenv('USE_REDIS', 'true').lower() == 'true'
    
    if use_redis:
        return asyncio.run(_scan_audio_directory_redis())
    else:
        return _scan_audio_directory_original()


async def _scan_audio_directory_redis() -> List[Dict]:
    """Versão Redis para scan de áudios"""
    try:
        # Limpar mapeamento em memória
        audio_mapping.clear()
        
        # Obter todos os áudios do Redis
        redis_audios = await redis_audio_manager.get_all_audios()
        audio_list = []
        
        for audio in redis_audios:
            try:
                # Verificar se o arquivo existe
                audio_path_str = audio.get("path", "")
                if not audio_path_str:
                    continue
                
                audio_path = AUDIO_DIR.parent / audio_path_str
                if not audio_path.exists():
                    logger.warning(f"Arquivo de áudio não encontrado no caminho: {audio_path}")
                    # Remover do Redis se arquivo não existe mais
                    await redis_audio_manager.delete_audio(audio["id"])
                    continue
                
                # Obter informações básicas do arquivo
                stats = audio_path.stat()
                
                # Verificar existência de arquivo de transcrição
                transcription_path = ""
                has_transcription = False
                
                # Primeira verificação: campo no Redis
                transcription_status = audio.get("transcription_status", "none")
                if transcription_status == "ended" and audio.get("transcription_path"):
                    transcription_file = AUDIO_DIR.parent / audio["transcription_path"]
                    if transcription_file.exists():
                        has_transcription = True
                        transcription_path = audio["transcription_path"]
                        logger.debug(f"Transcrição encontrada no Redis: {transcription_path}")
                    else:
                        # Atualizar status no Redis se arquivo não existe mais
                        await redis_audio_manager.update_transcription_status(audio["id"], "none")
                
                # Segunda verificação: arquivo .md associado
                if not has_transcription:
                    md_file = audio_path.with_suffix(".md")
                    if md_file.exists():
                        has_transcription = True
                        transcription_path = str(md_file.relative_to(AUDIO_DIR.parent))
                        logger.debug(f"Transcrição encontrada por arquivo associado: {transcription_path}")
                        
                        # Atualizar Redis com a nova transcrição encontrada
                        await redis_audio_manager.update_transcription_status(
                            audio["id"], "ended", transcription_path
                        )
                
                # Montar informações do áudio
                audio_info = {
                    "id": audio["id"],
                    "name": audio.get("title", audio_path.stem),
                    "path": audio["path"],
                    "format": audio.get("format", "m4a"),
                    "created_date": audio.get("created_date", datetime.fromtimestamp(stats.st_ctime).isoformat()),
                    "modified_date": audio.get("modified_date", datetime.fromtimestamp(stats.st_mtime).isoformat()),
                    "size": stats.st_size,
                    "has_transcription": has_transcription,
                    "transcription_path": transcription_path,
                    "youtube_id": audio.get("youtube_id", ""),
                    "url": audio.get("url", ""),
                    "source": AudioSource.YOUTUBE if audio.get("url") else AudioSource.LOCAL,
                    "keywords": audio.get("keywords", [])
                }
                
                audio_list.append(audio_info)
                
                # Adicionar ao mapeamento em memória
                audio_mapping[audio["id"]] = audio_path
                
                # Se houve mudanças na transcrição, atualizar Redis
                redis_has_transcription = audio.get("transcription_status") == "ended"
                redis_transcription_path = audio.get("transcription_path", "")
                
                if (has_transcription != redis_has_transcription or 
                    transcription_path != redis_transcription_path):
                    
                    updates = {
                        "transcription_status": "ended" if has_transcription else "none",
                        "transcription_path": transcription_path,
                        "has_transcription": "true" if has_transcription else "false",
                        "modified_date": datetime.now().isoformat()
                    }
                    await redis_audio_manager.update_audio(audio["id"], updates)
                    logger.info(f"Atualizado status de transcrição para áudio {audio['id']}: {has_transcription}")
                
            except Exception as e:
                logger.error(f"Erro ao processar áudio {audio.get('id')}: {str(e)}")
                continue
        
        # Ordenar por data de modificação (mais recente primeiro)
        audio_list.sort(key=lambda x: x["modified_date"], reverse=True)
        
        return audio_list
    except Exception as e:
        logger.error(f"Erro no scan de áudios Redis: {str(e)}")
        return []


def _scan_audio_directory_original() -> List[Dict]:
    """Função obsoleta - sistema não usa mais audios.json"""
    logger.warning("_scan_audio_directory_original() called but audios.json is no longer used")
    audio_mapping.clear()
    return []