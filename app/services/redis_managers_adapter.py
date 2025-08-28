"""
Redis Managers Adapter - Adaptador para migração gradual de managers.py para Redis
Mantém interface idêntica ao sistema atual enquanto usa Redis como backend
"""

import asyncio
import os
import re
import json
import datetime
from pathlib import Path
from typing import Optional, Dict, List, Union, Any

import aiohttp
from fastapi import HTTPException
from loguru import logger
from yt_dlp import YoutubeDL

from app.services.configs import AUDIO_DIR, audio_mapping, AUDIO_CONFIG_PATH
from app.services.redis_audio_manager import redis_audio_manager
from app.services.redis_connection import get_redis_client
from app.services.locks import audio_file_lock


class RedisAudioDownloadManager:
    """
    Adaptador do AudioDownloadManager que usa Redis como backend.
    Mantém a interface exata do sistema atual.
    """
    
    def __init__(self):
        """
        Inicializa o gerenciador de download de áudio usando Redis
        """
        self.download_dir = AUDIO_DIR
        self.redis_manager = redis_audio_manager
        logger.info(f"Gerenciador de download de áudio Redis inicializado com diretório: {self.download_dir}")
        
        # Flag para controlar se está usando Redis ou fallback para JSON
        self.use_redis = os.getenv('USE_REDIS', 'true').lower() == 'true'
        
        if self.use_redis:
            logger.info("Usando Redis como backend para áudios")
        else:
            logger.info("Usando JSON como backend para áudios (modo fallback)")
            # Carregar dados do sistema atual como fallback
            self.audio_data = self._load_audio_data_json()
            self.migrate_has_transcription_to_status()
    
    def _load_audio_data_json(self) -> Dict[str, Any]:
        """
        Carrega dados de áudio do JSON (fallback)
        """
        try:
            from app.services.files import load_json_audios
            with audio_file_lock:
                return load_json_audios()
        except Exception as e:
            logger.error(f"Erro ao carregar dados JSON: {str(e)}")
            return {"audios": [], "mappings": {}}
    
    def _save_audio_data_json(self) -> None:
        """
        Salva dados de áudio no JSON (fallback)
        """
        if not hasattr(self, 'audio_data'):
            return
        
        with audio_file_lock:
            try:
                temp_path = Path(str(AUDIO_CONFIG_PATH) + '.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(self.audio_data, f, ensure_ascii=False, indent=2)
                temp_path.replace(AUDIO_CONFIG_PATH)
                logger.debug(f"Dados de áudio salvos em: {AUDIO_CONFIG_PATH}")
            except Exception as e:
                logger.error(f"Erro ao salvar arquivo JSON: {str(e)}")
                temp_path = Path(str(AUDIO_CONFIG_PATH) + '.tmp')
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except:
                        pass
    
    async def _load_audio_data_redis(self) -> Dict[str, Any]:
        """
        Carrega dados de áudio do Redis e ajusta formato para compatibilidade
        """
        try:
            audios = await self.redis_manager.get_all_audios()
            
            # Processar cada áudio para compatibilidade com o formato esperado
            processed_audios = []
            mappings = {}
            
            for audio in audios:
                # Criar cópia do áudio com campos ajustados
                processed_audio = dict(audio)
                
                # Adicionar campo 'name' baseado no 'title' (compatibilidade com frontend)
                if 'title' in processed_audio and 'name' not in processed_audio:
                    processed_audio['name'] = processed_audio['title']
                
                # Converter campos numéricos se necessário
                if 'filesize' in processed_audio and isinstance(processed_audio['filesize'], str):
                    try:
                        processed_audio['size'] = int(processed_audio['filesize'])
                    except ValueError:
                        processed_audio['size'] = 0
                
                # Converter campos boolean
                if 'has_transcription' in processed_audio:
                    has_transcription = processed_audio['has_transcription']
                    if isinstance(has_transcription, str):
                        processed_audio['has_transcription'] = has_transcription.lower() == 'true'
                
                # Adicionar source field (compatibilidade)
                if 'url' in processed_audio and processed_audio.get('url'):
                    processed_audio['source'] = 'YOUTUBE'
                else:
                    processed_audio['source'] = 'LOCAL'
                
                processed_audios.append(processed_audio)
                
                # Construir mappings para compatibilidade
                audio_id = audio.get('id')
                path = audio.get('path')
                if audio_id and path:
                    mappings[audio_id] = path
                    # Adicionar keywords também
                    for keyword in audio.get('keywords', []):
                        if keyword:
                            mappings[keyword] = path
            
            logger.debug(f"Processados {len(processed_audios)} áudios do Redis com campos de compatibilidade")
            
            return {
                "audios": processed_audios,
                "mappings": mappings
            }
        except Exception as e:
            logger.error(f"Erro ao carregar dados Redis: {str(e)}")
            return {"audios": [], "mappings": {}}
    
    async def _save_audio_data_redis(self, audio_data: Dict[str, Any]) -> None:
        """
        Salva dados de áudio no Redis
        """
        try:
            # Este método não é necessário pois as operações individuais já salvam no Redis
            pass
        except Exception as e:
            logger.error(f"Erro ao salvar dados Redis: {str(e)}")
    
    def extract_youtube_id(self, url: str) -> Optional[str]:
        """
        Extrai o ID do YouTube de uma URL
        
        Args:
            url: URL do vídeo do YouTube
            
        Returns:
            ID do YouTube ou None se não for possível extrair
        """
        try:
            # Primeiro, tenta extrair o ID usando expressões regulares
            youtube_id = None
            
            # Padrão para URLs no formato https://www.youtube.com/watch?v=VIDEO_ID
            match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)', url)
            if match:
                youtube_id = match.group(1)
            
            # Se não encontrou com regex, tenta usando yt-dlp
            if not youtube_id:
                ydl_info_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'skip_download': True,
                    'extract_flat': True
                }
                
                with YoutubeDL(ydl_info_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    youtube_id = info.get('id', '')
            
            return youtube_id
        except Exception as e:
            logger.error(f"Erro ao extrair ID do YouTube: {str(e)}")
            return None
    
    def register_audio_for_download(self, url: str) -> str:
        """
        Registra um áudio para download com status 'downloading'.
        Retorna o ID do áudio registrado.
        
        Args:
            url: URL do vídeo do YouTube
            
        Returns:
            ID do áudio registrado
        """
        # Para compatibilidade temporária, usar versão síncrona simples
        return self._register_audio_for_download_json_simple(url)
    
    def _register_audio_for_download_json_simple(self, url: str) -> str:
        """Versão simplificada para registro rápido"""
        # Extrair ID do YouTube
        youtube_id = self.extract_youtube_id(url)
        if not youtube_id:
            youtube_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"Registro simples de áudio: {youtube_id}")
        return youtube_id
    
    async def register_audio_for_download_async(self, url: str) -> str:
        """
        Versão assíncrona de register_audio_for_download
        
        Args:
            url: URL do vídeo do YouTube
            
        Returns:
            ID do áudio registrado
        """
        if self.use_redis:
            return await self._register_audio_for_download_redis(url)
        else:
            return self._register_audio_for_download_json(url)
    
    async def _register_audio_for_download_redis(self, url: str) -> str:
        """Versão Redis do registro de áudio"""
        try:
            logger.info(f"Registrando áudio para download (Redis): {url}")
            
            # Extrair ID e informações básicas do YouTube
            youtube_id = self.extract_youtube_id(url)
            if not youtube_id:
                youtube_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Usar título temporário - será atualizado durante o download
            title = f"Download_{youtube_id}"
            
            # Criar entrada no Redis com status downloading
            created_date = datetime.datetime.now().isoformat()
            
            audio_metadata = {
                "id": youtube_id,
                "title": title,
                "name": f"{title}.m4a",
                "youtube_id": youtube_id,
                "url": url,
                "path": "",  # Será preenchido após download
                "directory": "",  # Será preenchido após download
                "created_date": created_date,
                "modified_date": created_date,
                "format": "m4a",
                "filesize": 0,
                "download_status": "downloading",  
                "download_progress": 0,  
                "download_error": "",  
                "transcription_status": "none",
                "transcription_path": "",
                "keywords": self._extract_keywords(title)
            }
            
            # Criar no Redis
            await self.redis_manager.create_audio(audio_metadata)
            
            logger.info(f"Áudio registrado com ID: {youtube_id}")
            return youtube_id
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Erro ao registrar áudio: {error_str}")
            
            # Para problemas de conectividade, registrar mesmo assim com título genérico
            if "Failed to extract any player response" in error_str or "getaddrinfo failed" in error_str:
                logger.warning("Problemas de conectividade detectados, registrando áudio com informações limitadas")
                
                created_date = datetime.datetime.now().isoformat()
                title = f"Video_{youtube_id}"
                
                audio_metadata = {
                    "id": youtube_id,
                    "title": title,
                    "name": f"{title}.m4a",
                    "youtube_id": youtube_id,
                    "url": url,
                    "path": "",
                    "directory": "",
                    "created_date": created_date,
                    "modified_date": created_date,
                    "format": "m4a",
                    "filesize": 0,
                    "download_status": "queued", 
                    "download_progress": 0,
                    "download_error": "Problemas de conectividade durante registro",
                    "transcription_status": "none",
                    "transcription_path": "",
                    "keywords": []
                }
                
                await self.redis_manager.create_audio(audio_metadata)
                
                logger.info(f"Áudio registrado com informações limitadas, ID: {youtube_id}")
                return youtube_id
            else:
                raise
    
    def _register_audio_for_download_json(self, url: str) -> str:
        """Versão JSON do registro de áudio (fallback)"""
        try:
            logger.info(f"Registrando áudio para download (JSON): {url}")
            
            # Recarregar dados do arquivo
            self.audio_data = self._load_audio_data_json()
            
            # Extrair ID e informações básicas do YouTube
            youtube_id = self.extract_youtube_id(url)
            if not youtube_id:
                youtube_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Obter informações básicas sem baixar
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', 'Unknown')
                except Exception as extract_error:
                    logger.warning(f"Erro ao extrair informações: {str(extract_error)}")
                    title = f"Video_{youtube_id}"
            
            # Criar entrada no JSON
            created_date = datetime.datetime.now().isoformat()
            
            audio_metadata = {
                "id": youtube_id,
                "title": title,
                "name": f"{title}.m4a",
                "youtube_id": youtube_id,
                "url": url,
                "path": "",
                "directory": "",
                "created_date": created_date,
                "modified_date": created_date,
                "format": "m4a",
                "filesize": 0,
                "download_status": "downloading",
                "download_progress": 0,
                "download_error": "",
                "transcription_status": "none",
                "transcription_path": "",
                "keywords": self._extract_keywords(title)
            }
            
            # Adicionar à lista de áudios
            self.audio_data["audios"].append(audio_metadata)
            
            # Salvar os dados
            self._save_audio_data_json()
            
            logger.info(f"Áudio registrado com ID: {youtube_id}")
            return youtube_id
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Erro ao registrar áudio JSON: {error_str}")
            
            if "Failed to extract any player response" in error_str or "getaddrinfo failed" in error_str:
                created_date = datetime.datetime.now().isoformat()
                title = f"Video_{youtube_id}"
                
                audio_metadata = {
                    "id": youtube_id,
                    "title": title,
                    "name": f"{title}.m4a",
                    "youtube_id": youtube_id,
                    "url": url,
                    "path": "",
                    "directory": "",
                    "created_date": created_date,
                    "modified_date": created_date,
                    "format": "m4a",
                    "filesize": 0,
                    "download_status": "queued",
                    "download_progress": 0,
                    "download_error": "Problemas de conectividade durante registro",
                    "transcription_status": "none",
                    "transcription_path": "",
                    "keywords": []
                }
                
                self.audio_data["audios"].append(audio_metadata)
                self._save_audio_data_json()
                
                logger.info(f"Áudio registrado com informações limitadas, ID: {youtube_id}")
                return youtube_id
            else:
                raise
    
    def get_audio_info(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém informações de um áudio pelo ID
        
        Args:
            audio_id: ID do áudio
            
        Returns:
            Dicionário com informações do áudio ou None se não encontrado
        """
        if self.use_redis:
            return asyncio.run(self._get_audio_info_redis(audio_id))
        else:
            return self._get_audio_info_json(audio_id)
    
    async def _get_audio_info_redis(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """Versão Redis para obter info do áudio"""
        try:
            # Primeiro tenta busca direta por ID
            audio_data = await self.redis_manager.get_audio(audio_id)
            if audio_data:
                return audio_data
            
            # Se não encontrou, tenta busca por keyword
            results = await self.redis_manager.search_by_keyword(audio_id)
            if results:
                return results[0]  # Retorna o primeiro resultado
            
            return None
        except Exception as e:
            logger.error(f"Erro ao obter áudio Redis: {str(e)}")
            return None
    
    def _get_audio_info_json(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """Versão JSON para obter info do áudio"""
        for audio in self.audio_data["audios"]:
            if audio["id"] == audio_id:
                return audio
                
        # Se não encontrou pelo ID exato, procura por keywords ou ID do YouTube
        normalized_id = self._normalize_filename(audio_id)
        for audio in self.audio_data["audios"]:
            # Verificar se o ID normalizado está contido nas keywords
            if normalized_id in audio["keywords"]:
                return audio
            # Verificar se é o ID do YouTube
            if audio_id == audio["youtube_id"]:
                return audio
        
        return None
    
    @property  
    def audio_data(self) -> Dict[str, Any]:
        """
        Propriedade para compatibilidade com código existente.
        NOTA: Para uso em contextos assíncronos, use get_audio_data_async()
        
        Returns:
            Dict com estrutura {"audios": [...], "mappings": {...}}
        """
        if not self.use_redis:
            # Se não está usando Redis, usar JSON
            if not hasattr(self, '_audio_data_cache'):
                self._audio_data_cache = self._load_audio_data_json()
            return self._audio_data_cache
        else:
            # Para Redis, tentar usar dados em cache ou fallback para JSON
            logger.warning("audio_data property accessed in Redis mode. This is not optimal for performance.")
            logger.info("Consider using get_audio_data_async() instead for better performance.")
            
            # Tentar carregar do JSON como fallback
            try:
                return self._load_audio_data_json()
            except Exception as e:
                logger.error(f"Error loading JSON fallback data: {e}")
                return {"audios": [], "mappings": {}}
    
    async def get_audio_data_async(self) -> Dict[str, Any]:
        """
        Método assíncrono para obter dados de áudio.
        Funciona tanto com Redis quanto JSON.
        
        Returns:
            Dict com estrutura {"audios": [...], "mappings": {...}}
        """
        if self.use_redis:
            try:
                return await self._load_audio_data_redis()
            except Exception as e:
                logger.error(f"Erro ao carregar dados Redis: {str(e)}")
                # Fallback para JSON se Redis falhar
                try:
                    return self._load_audio_data_json()
                except Exception as json_error:
                    logger.error(f"Erro ao carregar dados JSON: {str(json_error)}")
                    return {"audios": [], "mappings": {}}
        else:
            return self._load_audio_data_json()
    
    def update_transcription_status(self, audio_id: str, status: str, transcription_path: str = None) -> bool:
        """
        Atualiza o status de transcrição de um áudio
        
        Args:
            audio_id: ID do áudio
            status: Status da transcrição (none, started, ended, error)
            transcription_path: Caminho do arquivo de transcrição (opcional)
            
        Returns:
            True se atualizado com sucesso, False caso contrário
        """
        if self.use_redis:
            return asyncio.run(self._update_transcription_status_redis(audio_id, status, transcription_path))
        else:
            return self._update_transcription_status_json(audio_id, status, transcription_path)
    
    async def _update_transcription_status_redis(self, audio_id: str, status: str, transcription_path: str = None) -> bool:
        """Versão Redis para atualizar status de transcrição"""
        try:
            return await self.redis_manager.update_transcription_status(audio_id, status, transcription_path)
        except Exception as e:
            logger.error(f"Erro ao atualizar status Redis: {str(e)}")
            return False
    
    def _update_transcription_status_json(self, audio_id: str, status: str, transcription_path: str = None) -> bool:
        """Versão JSON para atualizar status de transcrição"""
        # Recarregar dados do arquivo para garantir que temos a versão mais atual
        self.audio_data = self._load_audio_data_json()
        
        for audio in self.audio_data["audios"]:
            if audio["id"] == audio_id:
                # Verifica se o status é válido
                if status not in ["none", "started", "ended", "error"]:
                    logger.warning(f"Status de transcrição inválido: {status}")
                    return False
                
                # Atualiza o status
                audio["transcription_status"] = status
                
                # Atualiza o caminho da transcrição se fornecido
                if transcription_path:
                    audio["transcription_path"] = transcription_path
                
                # Atualiza a data de modificação
                audio["modified_date"] = datetime.datetime.now().isoformat()
                
                # Salva os dados
                self._save_audio_data_json()
                
                logger.info(f"Status da transcrição atualizado para '{status}' para áudio {audio_id}")
                if transcription_path:
                    logger.info(f"Caminho da transcrição: {transcription_path}")
                
                return True
                
        # Se não encontrou o áudio
        logger.warning(f"Áudio não encontrado para atualização do status: {audio_id}")
        return False
    
    def _normalize_filename(self, filename: str) -> str:
        """
        Normaliza um nome de arquivo para ser usado como ID.
        Remove caracteres especiais e converte para minúsculas.
        """
        normalized = re.sub(r'[^\w\s]', ' ', filename.lower())
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip().replace(' ', '_')
        return normalized
    
    def _extract_keywords(self, title: str) -> List[str]:
        """
        Extrai palavras-chave de um título para facilitar a busca
        """
        normalized = self._normalize_filename(title)
        words = normalized.split('_')
        keywords = [word for word in words if len(word) > 3]
        keywords.append(normalized)
        return keywords
    
    def _add_audio_mappings(self, filename: Path, info: dict, youtube_id: str) -> None:
        """
        Adiciona várias formas de ID ao mapeamento de áudio.
        """
        title = info.get('title', '')
        
        # Mapeia pelo ID do YouTube
        audio_mapping[youtube_id] = filename
        logger.debug(f"Mapeamento adicionado (ID YouTube): '{youtube_id}' -> {filename}")
        
        # Mapeia pelo nome do arquivo normalizado
        file_id = self._normalize_filename(filename.stem)
        audio_mapping[file_id] = filename
        logger.debug(f"Mapeamento adicionado: '{file_id}' -> {filename}")
        
        # Mapeia pelo título normalizado
        title_id = self._normalize_filename(title)
        if title_id and title_id != file_id:
            audio_mapping[title_id] = filename
            logger.debug(f"Mapeamento adicional: '{title_id}' -> {filename}")
        
        # Mapeia por partes do título para aumentar as chances de correspondência
        for word in self._extract_keywords(title):
            audio_mapping[word] = filename
            logger.debug(f"Mapeamento para palavra-chave: '{word}' -> {filename}")
    
    def migrate_has_transcription_to_status(self) -> None:
        """
        Migra o campo 'has_transcription' para o novo campo 'transcription_status'.
        Esta é uma função temporária para migração de dados.
        """
        if self.use_redis:
            # No Redis, esta migração é feita automaticamente durante a importação
            return
        
        try:
            logger.info("Iniciando migração de dados 'has_transcription' para 'transcription_status'")
            changes_made = False
            
            for audio in self.audio_data.get("audios", []):
                # Caso 1: Tem o campo antigo mas não o novo
                if "has_transcription" in audio and "transcription_status" not in audio:
                    audio["transcription_status"] = "ended" if audio.get("has_transcription") else "none"
                    changes_made = True
                    logger.debug(f"Migração para áudio {audio.get('id')}: has_transcription={audio.get('has_transcription')} -> transcription_status={audio['transcription_status']}")
                
                # Caso 2: Tem os dois campos (remover o antigo)
                elif "has_transcription" in audio and "transcription_status" in audio:
                    del audio["has_transcription"]
                    changes_made = True
                    logger.debug(f"Removendo campo 'has_transcription' redundante do áudio {audio.get('id')}")
                
                # Caso 3: Não tem o novo campo
                elif "transcription_status" not in audio:
                    audio["transcription_status"] = "none"
                    changes_made = True
                    logger.debug(f"Adicionando 'transcription_status=none' para áudio {audio.get('id')}")
                
                # Verificar se tem transcrição mas status não é "ended"
                if audio.get("transcription_path") and audio.get("transcription_status") != "ended":
                    path = Path(AUDIO_DIR.parent / audio["transcription_path"])
                    if path.exists():
                        audio["transcription_status"] = "ended"
                        changes_made = True
                        logger.debug(f"Ajustando status para 'ended' para áudio {audio.get('id')} que já tem transcrição")
            
            if changes_made:
                logger.info("Migração de dados concluída com sucesso. Salvando alterações.")
                self._save_audio_data_json()
            else:
                logger.info("Nenhuma alteração necessária durante a migração.")
        except Exception as e:
            logger.error(f"Erro durante a migração de dados: {str(e)}")
    
    # Métodos adicionais para manter compatibilidade com sistema atual
    async def download_audio_with_status_async(self, audio_id: str, url: str, sse_manager=None) -> str:
        """
        Método assíncrono para download com status - mantém interface original
        """
        if self.use_redis:
            return await self._download_audio_with_status_async_redis(audio_id, url, sse_manager)
        else:
            # Usar implementação original do sistema atual se necessário
            from app.services.managers import AudioDownloadManager
            original_manager = AudioDownloadManager()
            return await original_manager.download_audio_with_status_async(audio_id, url, sse_manager)
    
    async def _download_audio_with_status_async_redis(self, audio_id: str, url: str, sse_manager=None) -> str:
        """
        Versão Redis do download assíncrono com status
        """
        try:
            logger.info(f"Iniciando download real do áudio {audio_id}: {url}")
            
            # Notificar início via SSE
            if sse_manager:
                await sse_manager.download_started(audio_id, f"Iniciando download de {url}")
            
            # Criar diretório para o download
            download_dir = self.download_dir / audio_id
            download_dir.mkdir(exist_ok=True)
            
            # Configurações para download
            progress_data = {'last_progress': 0}
            
            def simple_progress_hook(d):
                """Hook de progresso simples"""
                if d['status'] == 'downloading':
                    if d.get('total_bytes'):
                        progress = int(d['downloaded_bytes'] / d['total_bytes'] * 100)
                    elif d.get('total_bytes_estimate'):
                        progress = int(d['downloaded_bytes'] / d['total_bytes_estimate'] * 100)
                    else:
                        progress = 0
                    
                    progress_data['current_progress'] = progress
                    progress_data['status'] = 'downloading'
                
                elif d['status'] == 'finished':
                    progress_data['current_progress'] = 95
                    progress_data['status'] = 'finished'
            
            # Configurações do yt-dlp com estratégia robusta para YouTube
            ydl_opts = {
                'format': 'ba[ext=m4a]/ba[ext=webm]/ba[ext=mp4]/ba/b[ext=m4a]/b[ext=webm]/b[ext=mp4]/bestaudio/best',
                'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '192',
                }],
                'progress_hooks': [simple_progress_hook],
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'verbose': True,
                'noplaylist': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1',
                },
                'extractor_args': {
                    'youtube': {
                        'skip': ['dash', 'hls']  # Pula formatos que podem requerer PO token
                    }
                }
            }
            
            # Executar download em thread separada
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._execute_ydl_download_redis(url, ydl_opts, progress_data, audio_id, sse_manager)
                )
                
                info = result['info']
                original_filename = result['filename']
            except Exception as download_error:
                error_str = str(download_error)
                logger.error(f"Erro durante download: {error_str}")
                
                # Atualizar status para erro no Redis
                updates = {
                    "download_status": "error",
                    "download_error": error_str[:500],
                    "modified_date": datetime.datetime.now().isoformat()
                }
                await self.redis_manager.update_audio(audio_id, updates)
                
                if sse_manager:
                    await sse_manager.download_error(audio_id, f"Erro: {error_str}")
                
                raise Exception("Problemas de conectividade. Tente novamente mais tarde.")
            
            filename = Path(original_filename).with_suffix('.m4a')
            
            # Notificar progresso final via SSE
            if sse_manager:
                await sse_manager.download_progress(audio_id, 100, "Download concluído!")
            
            # Atualizar dados no Redis
            updates = {
                "path": str(filename.relative_to(self.download_dir.parent)),
                "directory": str(download_dir.relative_to(self.download_dir.parent)),
                "filesize": filename.stat().st_size if filename.exists() else 0,
                "download_status": "ready",
                "download_progress": 100,
                "modified_date": datetime.datetime.now().isoformat()
            }
            
            await self.redis_manager.update_audio(audio_id, updates)
            
            # Atualizar mapeamento em memória
            self._add_audio_mappings(filename, info, audio_id)
            
            if sse_manager:
                await sse_manager.download_completed(audio_id, f"Download concluído: {filename.name}")
            
            logger.success(f"Download de áudio concluído: {filename}")
            return str(filename)
            
        except Exception as e:
            logger.exception(f"Erro no download de áudio: {str(e)}")
            
            if sse_manager:
                await sse_manager.download_error(audio_id, str(e))
            
            # Atualizar status para erro
            updates = {
                "download_status": "error",
                "download_error": str(e)
            }
            await self.redis_manager.update_audio(audio_id, updates)
            
            raise
    
    def _execute_ydl_download_redis(self, url: str, ydl_opts: dict, progress_data: dict, audio_id: str, sse_manager) -> dict:
        """Executa o download do yt-dlp em thread separada (método síncrono)"""
        import threading
        import time
        
        # Thread para monitorar progresso
        stop_monitoring = threading.Event()
        
        def monitor_progress():
            last_progress = 0
            while not stop_monitoring.is_set():
                current_progress = progress_data.get('current_progress', 0)
                if current_progress != last_progress and current_progress > 0:
                    # Atualizar no Redis de forma assíncrona
                    try:
                        # Criar um novo loop para esta thread
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Atualizar progresso
                        updates = {"download_progress": current_progress}
                        loop.run_until_complete(self.redis_manager.update_audio(audio_id, updates))
                        
                        loop.close()
                    except Exception as e:
                        logger.error(f"Erro ao atualizar progresso: {str(e)}")
                    
                    last_progress = current_progress
                
                time.sleep(1)
        
        # Iniciar thread de monitoramento
        monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        monitor_thread.start()
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                original_filename = ydl.prepare_filename(info)
                return {
                    'info': info,
                    'filename': original_filename
                }
        finally:
            stop_monitoring.set()
            monitor_thread.join(timeout=1)


# Para manter compatibilidade, criar alias para o manager atual
AudioDownloadManager = RedisAudioDownloadManager