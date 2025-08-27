import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Union, List, Dict

from fastapi import HTTPException
from loguru import logger

from app.models.video import VideoSource, SortOption
from app.models.audio import AudioSource
from app.services.configs import VIDEO_DIR, JSON_CONFIG_PATH, video_mapping, AUDIO_DIR, AUDIO_CONFIG_PATH, audio_mapping
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
    Carrega os dados de áudio do arquivo JSON de forma thread-safe
    
    Returns:
        Dicionário com os dados de áudio (contendo 'audios' e 'mappings')
    """
    with audio_file_lock:
        try:
            if AUDIO_CONFIG_PATH.exists():
                with open(AUDIO_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Atualiza o mapeamento em memória com os dados do arquivo
                for audio in data.get("audios", []):
                    audio_id = audio.get("id", "")
                    if audio_id and "path" in audio:
                        audio_mapping[audio_id] = AUDIO_DIR.parent / audio["path"]
                        
                        # Adiciona mapeamentos por palavras-chave
                        for keyword in audio.get("keywords", []):
                            audio_mapping[keyword] = AUDIO_DIR.parent / audio["path"]
                
                # Adiciona mapeamentos específicos se estiverem no arquivo
                for key, path in data.get("mappings", {}).items():
                    audio_mapping[key] = AUDIO_DIR.parent / path
                
                # Ensure mappings key exists for backward compatibility
                if "mappings" not in data:
                    data["mappings"] = {}
                    
                return data
            return {"audios": [], "mappings": {}}
        except Exception as e:
            logger.error(f"Erro ao carregar arquivo de áudios JSON: {str(e)}")
            return {"audios": [], "mappings": {}}


def scan_audio_directory() -> List[Dict]:
    """
    Escaneia o diretório de áudios e retorna informações dos arquivos baseando-se no audios.json
    
    Returns:
        Lista de dicionários com informações dos áudios
    """
    audio_mapping.clear()
    
    # Carrega os dados do JSON
    audio_data = load_json_audios()
    audio_list = []
    
    # Processa cada áudio do JSON, verificando se o arquivo existe
    for audio in audio_data.get("audios", []):
        try:
            # Pular entradas especiais como "stats" que não são arquivos de áudio
            if not audio.get("path") or audio.get("id") == "stats":
                continue
                
            # Verificar se o arquivo existe
            audio_path = AUDIO_DIR.parent / audio["path"]
            if not audio_path.exists():
                logger.warning(f"Arquivo de áudio não encontrado no caminho: {audio_path}")
                continue
            
            # Obtém informações básicas do arquivo
            stats = audio_path.stat()
            
            # Verifica existência de arquivo de transcrição
            transcription_path = ""
            has_transcription = False
            
            # Primeira verificação: campo no JSON
            if audio.get("has_transcription", False) and audio.get("transcription_path"):
                transcription_file = AUDIO_DIR.parent / audio["transcription_path"]
                if transcription_file.exists():
                    has_transcription = True
                    transcription_path = audio["transcription_path"]
                    logger.debug(f"Transcrição encontrada no JSON: {transcription_path}")
                
            # Segunda verificação: arquivo .md associado
            if not has_transcription:
                md_file = audio_path.with_suffix(".md")
                if md_file.exists():
                    has_transcription = True
                    transcription_path = str(md_file.relative_to(AUDIO_DIR.parent))
                    logger.debug(f"Transcrição encontrada por arquivo associado: {transcription_path}")
            
            # Adiciona à lista de áudios
            audio_info = {
                "id": audio["id"],
                "name": audio.get("title", audio_path.stem),
                "path": audio["path"],
                "format": audio.get("format", "m4a"),
                "created_date": audio.get("created_date", datetime.fromtimestamp(stats.st_ctime).isoformat()),
                "modified_date": audio.get("modified_date", datetime.fromtimestamp(stats.st_mtime).isoformat()),
                "size": stats.st_size,
                "has_transcription": has_transcription,  # Usa o valor verificado
                "transcription_path": transcription_path,  # Usa o caminho verificado
                "youtube_id": audio.get("youtube_id", ""),
                "url": audio.get("url", ""),
                "source": AudioSource.YOUTUBE if audio.get("url") else AudioSource.LOCAL,
                "keywords": audio.get("keywords", [])
            }
            
            audio_list.append(audio_info)
            
            # Adiciona ao mapeamento
            audio_mapping[audio["id"]] = audio_path
            
            # Se houver discrepância, atualize o arquivo JSON
            if has_transcription != audio.get("has_transcription", False) or transcription_path != audio.get("transcription_path", ""):
                # Encontra o áudio no array original e atualiza
                for a in audio_data["audios"]:
                    if a["id"] == audio["id"]:
                        a["has_transcription"] = has_transcription
                        a["transcription_path"] = transcription_path
                        a["modified_date"] = datetime.now().isoformat()
                        break
                
                # Salva as alterações no JSON de forma thread-safe
                with audio_file_lock:
                    # Escrever primeiro para arquivo temporário para operação atômica
                    temp_path = Path(str(AUDIO_CONFIG_PATH) + '.tmp')
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        json.dump(audio_data, f, ensure_ascii=False, indent=2)
                    
                    # Renomear arquivo temporário para o arquivo final (operação atômica)
                    temp_path.replace(AUDIO_CONFIG_PATH)
                logger.info(f"Atualizado status de transcrição para áudio {audio['id']}: {has_transcription}")
                
        except Exception as e:
            logger.error(f"Erro ao processar áudio {audio.get('id')}: {str(e)}")
            continue
    
    # Ordena por data de modificação (mais recente primeiro)
    audio_list.sort(key=lambda x: x["modified_date"], reverse=True)
    
    return audio_list