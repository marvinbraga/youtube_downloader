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
from app.services.files import load_json_audios


class VideoStreamManager:
    def __init__(self):
        self.ydl_opts = {
            'format': 'best[ext=mp4]',  # Preferimos MP4 para compatibilidade
            'quiet': True,
            'no_warnings': True
        }

    async def get_direct_url(self, url: str) -> str:
        """Obtém a URL direta do stream do YouTube"""
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                # Executa a extração de forma assíncrona para não bloquear
                info = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=False)
                )

                # Pega a URL do formato selecionado
                return info['url']
        except Exception as e:
            logger.error(f"Erro ao obter URL do YouTube: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao processar vídeo do YouTube: {str(e)}"
            )

    async def stream_youtube_video(self, url: str):
        """Faz o streaming do vídeo do YouTube"""
        try:
            direct_url = await self.get_direct_url(url)

            async with aiohttp.ClientSession() as session:
                async with session.get(direct_url) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=response.status,
                            detail="Erro ao acessar stream do YouTube"
                        )

                    # Stream em chunks de 1MB
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        yield chunk

        except Exception as e:
            logger.error(f"Erro no streaming do YouTube: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro no streaming: {str(e)}"
            )


class AudioDownloadManager:
    """Gerencia o download de áudio do YouTube."""
    
    def __init__(self):
        """
        Inicializa o gerenciador de download de áudio usando o diretório de áudio configurado
        """
        self.download_dir = AUDIO_DIR
        self.audio_data = self._load_audio_data()
        logger.info(f"Gerenciador de download de áudio inicializado com diretório: {self.download_dir}")
        # Executa a migração automaticamente para garantir que todos os dados estejam atualizados
        self.migrate_has_transcription_to_status()
    
    def _load_audio_data(self) -> Dict[str, Any]:
        """
        Carrega os dados de áudio do arquivo JSON utilizando a função load_json_audios
        
        Returns:
            Dicionário com os dados de áudio
        """
        return load_json_audios()
    
    def _save_audio_data(self) -> None:
        """
        Salva os dados de áudio no arquivo JSON
        """
        try:
            with open(AUDIO_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.audio_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Dados de áudio salvos em: {AUDIO_CONFIG_PATH}")
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo de configuração de áudio: {str(e)}")
    
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
        try:
            logger.info(f"Registrando áudio para download: {url}")
            
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
                    logger.warning(f"Erro ao extrair informações do vídeo, usando título padrão: {str(extract_error)}")
                    # Fallback para um título baseado no ID do YouTube
                    title = f"Video_{youtube_id}"
            
            # Criar entrada no audios.json com status downloading
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
                "download_status": "downloading",  # Novo campo
                "download_progress": 0,  # Novo campo
                "download_error": "",  # Novo campo
                "transcription_status": "none",
                "transcription_path": "",
                "keywords": self._extract_keywords(title)
            }
            
            # Adicionar à lista de áudios
            self.audio_data["audios"].append(audio_metadata)
            
            # Salvar os dados
            self._save_audio_data()
            
            logger.info(f"Áudio registrado com ID: {youtube_id}")
            return youtube_id
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Erro ao registrar áudio: {error_str}")
            
            # Verificar se é um erro de conectividade ou extração
            if "Failed to extract any player response" in error_str or "getaddrinfo failed" in error_str or "Failed to resolve" in error_str:
                # Para problemas de conectividade, registrar o áudio mesmo assim com título genérico
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
                    "download_status": "queued",  # Status que indica que está na fila mas pode ter problemas
                    "download_progress": 0,
                    "download_error": "Problemas de conectividade durante registro",
                    "transcription_status": "none",
                    "transcription_path": "",
                    "keywords": []
                }
                
                self.audio_data["audios"].append(audio_metadata)
                self._save_audio_data()
                
                logger.info(f"Áudio registrado com informações limitadas, ID: {youtube_id}")
                return youtube_id
            else:
                raise
    
    def download_audio(self, url: str) -> str:
        """
        Baixa apenas o áudio de um vídeo do YouTube em alta qualidade.
        Cada download é salvo em um diretório com o ID do YouTube.
        
        Args:
            url: URL do vídeo do YouTube
            
        Returns:
            Caminho do arquivo baixado
        """
        try:
            logger.info(f"Iniciando download de áudio: {url}")
            
            # Primeiro, vamos extrair as informações do vídeo para obter o ID do YouTube
            youtube_id = self.extract_youtube_id(url)
                
            if not youtube_id:
                logger.warning("Não foi possível obter o ID do YouTube, usando data atual como fallback")
                # Fallback para um formato de data se não conseguir obter o ID
                youtube_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Cria um diretório específico usando o ID do YouTube
            download_dir = self.download_dir / youtube_id
            download_dir.mkdir(exist_ok=True)
            
            logger.info(f"Salvando áudio no diretório: {download_dir}")
            
            # Registra a data de criação
            created_date = datetime.datetime.now().isoformat()
            
            # Configurações para download apenas de áudio em alta qualidade
            ydl_opts = {
                # Formato de áudio de alta qualidade
                'format': 'bestaudio/best',
                
                # Diretório e padrão de nome para o arquivo baixado
                'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
                
                # Processador para extrair áudio e converter para m4a
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '192',  # Qualidade do áudio (bitrate)
                }],
                
                # Configurações de rede e extração
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'verbose': True,
                'noplaylist': True,
                
                # Cabeçalhos HTTP para contornar restrições
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'DNT': '1',
                }
            }
            
            # Faz o download do áudio
            with YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                except Exception as download_error:
                    logger.error(f"Erro durante download do yt-dlp: {str(download_error)}")
                    # Se houver erro de conectividade, relançar com informações específicas
                    if "Failed to extract any player response" in str(download_error) or "getaddrinfo failed" in str(download_error):
                        raise HTTPException(
                            status_code=503,
                            detail="Problemas de conectividade. Tente novamente mais tarde."
                        )
                    else:
                        raise
                
                # O arquivo será m4a após o processamento
                original_filename = ydl.prepare_filename(info)
                filename = Path(original_filename).with_suffix('.m4a')
                
                # Preparar metadados do áudio
                audio_metadata = {
                    "id": youtube_id,  # Usamos o ID do YouTube como ID do áudio
                    "title": info.get('title', ''),
                    "youtube_id": youtube_id,
                    "url": url,
                    "path": str(filename.relative_to(self.download_dir.parent)),
                    "directory": str(download_dir.relative_to(self.download_dir.parent)),
                    "created_date": created_date,
                    "modified_date": created_date,
                    "format": "m4a",
                    "filesize": filename.stat().st_size if filename.exists() else 0,
                    "transcription_status": "none",  # Novo campo para status da transcrição: none, started, ended, error
                    "transcription_path": "",
                    "keywords": self._extract_keywords(info.get('title', ''))
                }
                
                # Adicionar à lista de áudios
                self.audio_data["audios"].append(audio_metadata)
                
                # Adicionar aos mapeamentos
                mappings = {}
                mappings[youtube_id] = str(filename)
                mappings[self._normalize_filename(filename.stem)] = str(filename)
                mappings[self._normalize_filename(info.get('title', ''))] = str(filename)
                
                # Atualizar o dicionário de mapeamentos
                self.audio_data["mappings"].update(mappings)
                
                # Salvar os dados
                self._save_audio_data()
                
                # Atualizar o mapeamento em memória
                self._add_audio_mappings(filename, info, youtube_id)
            
            logger.success(f"Download de áudio concluído: {filename}")
            return str(filename)
            
        except Exception as e:
            logger.exception(f"Erro no download de áudio: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro no download de áudio: {str(e)}"
            )
    
    async def download_audio_with_status_async(self, audio_id: str, url: str, sse_manager=None) -> str:
        """
        Baixa o áudio e atualiza o status de um áudio já registrado.
        Versão assíncrona com suporte a eventos SSE.
        
        Args:
            audio_id: ID do áudio registrado
            url: URL do vídeo do YouTube
            sse_manager: Gerenciador SSE para emitir eventos de progresso
            
        Returns:
            Caminho do arquivo baixado
        """
        try:
            logger.info(f"Iniciando download real do áudio {audio_id}: {url}")
            
            # Notificar início via SSE
            if sse_manager:
                await sse_manager.download_started(audio_id, f"Iniciando download de {url}")
            
            # Criar diretório para o download
            download_dir = self.download_dir / audio_id
            download_dir.mkdir(exist_ok=True)
            
            # Criar um callback de progresso simples que será passado para a thread
            progress_data = {'last_progress': 0}
            
            def simple_progress_hook(d):
                """Hook de progresso que não usa asyncio - apenas armazena dados"""
                if d['status'] == 'downloading':
                    # Calcular percentual
                    if d.get('total_bytes'):
                        progress = int(d['downloaded_bytes'] / d['total_bytes'] * 100)
                    elif d.get('total_bytes_estimate'):
                        progress = int(d['downloaded_bytes'] / d['total_bytes_estimate'] * 100)
                    else:
                        progress = 0
                    
                    # Armazenar progresso para uso posterior
                    progress_data['current_progress'] = progress
                    progress_data['status'] = 'downloading'
                
                elif d['status'] == 'finished':
                    progress_data['current_progress'] = 95
                    progress_data['status'] = 'finished'
            
            # Configurações para download apenas de áudio em alta qualidade
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '192',
                }],
                'progress_hooks': [simple_progress_hook],  # Adicionar hook de progresso
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'verbose': True,
                'noplaylist': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'DNT': '1',
                }
            }
            
            # Faz o download do áudio de forma assíncrona
            try:
                # Executar o download em thread separada para não bloquear
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._execute_ydl_download(url, ydl_opts, progress_data, audio_id, sse_manager)
                )
                
                # O arquivo será m4a após o processamento
                info = result['info']
                original_filename = result['filename']
            except Exception as download_error:
                error_str = str(download_error)
                logger.error(f"Erro durante download assíncrono do yt-dlp: {error_str}")
                
                # Atualizar status no áudio para erro
                for i, audio in enumerate(self.audio_data["audios"]):
                    if audio["id"] == audio_id:
                        self.audio_data["audios"][i].update({
                            "download_status": "error",
                            "download_error": error_str[:500],  # Limitar tamanho do erro
                            "modified_date": datetime.datetime.now().isoformat()
                        })
                        break
                self._save_audio_data()
                
                # Notificar erro via SSE
                if sse_manager:
                    await sse_manager.download_error(audio_id, f"Erro: {error_str}")
                
                # Se houver erro de conectividade, relançar com informações específicas
                if "Failed to extract any player response" in error_str or "getaddrinfo failed" in error_str:
                    raise Exception("Problemas de conectividade. Tente novamente mais tarde.")
                else:
                    raise
            
            filename = Path(original_filename).with_suffix('.m4a')
            
            # Notificar progresso final via SSE
            if sse_manager:
                await sse_manager.download_progress(audio_id, 100, "Download concluído!")
            
            # Atualizar o áudio existente com os dados completos
            for i, audio in enumerate(self.audio_data["audios"]):
                if audio["id"] == audio_id:
                    # Atualizar campos após download completo
                    self.audio_data["audios"][i].update({
                        "path": str(filename.relative_to(self.download_dir.parent)),
                        "directory": str(download_dir.relative_to(self.download_dir.parent)),
                        "filesize": filename.stat().st_size if filename.exists() else 0,
                        "download_status": "ready",  # Marcar como pronto
                        "download_progress": 100,
                        "modified_date": datetime.datetime.now().isoformat()
                    })
                    break
            
            # Adicionar aos mapeamentos
            mappings = {}
            mappings[audio_id] = str(filename)
            mappings[self._normalize_filename(filename.stem)] = str(filename)
            mappings[self._normalize_filename(info.get('title', ''))] = str(filename)
            
            # Atualizar o dicionário de mapeamentos
            self.audio_data["mappings"].update(mappings)
            
            # Salvar os dados
            self._save_audio_data()
            
            # Atualizar o mapeamento em memória
            self._add_audio_mappings(filename, info, audio_id)
            
            # Notificar conclusão via SSE
            if sse_manager:
                await sse_manager.download_completed(audio_id, f"Download concluído: {filename.name}")
            
            logger.success(f"Download de áudio concluído: {filename}")
            return str(filename)
            
        except Exception as e:
            logger.exception(f"Erro no download de áudio: {str(e)}")
            
            # Notificar erro via SSE
            if sse_manager:
                await sse_manager.download_error(audio_id, str(e))
            
            # Atualizar status para erro
            for i, audio in enumerate(self.audio_data["audios"]):
                if audio["id"] == audio_id:
                    self.audio_data["audios"][i].update({
                        "download_status": "error",
                        "download_error": str(e)
                    })
                    break
            
            self._save_audio_data()
            raise
    
    def get_audio_info(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém informações de um áudio pelo ID
        
        Args:
            audio_id: ID do áudio
            
        Returns:
            Dicionário com informações do áudio ou None se não encontrado
        """
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
                self._save_audio_data()
                
                # Log de sucesso
                logger.info(f"Status da transcrição atualizado para '{status}' para áudio {audio_id}")
                if transcription_path:
                    logger.info(f"Caminho da transcrição: {transcription_path}")
                
                return True
                
        # Se não encontrou o áudio
        logger.warning(f"Áudio não encontrado para atualização do status de transcrição: {audio_id}")
        return False
    
    def _normalize_filename(self, filename: str) -> str:
        """
        Normaliza um nome de arquivo para ser usado como ID.
        Remove caracteres especiais e converte para minúsculas.
        
        Args:
            filename: Nome do arquivo
            
        Returns:
            Nome normalizado
        """
        # Remove caracteres especiais, deixando apenas letras, números e espaços
        normalized = re.sub(r'[^\w\s]', ' ', filename.lower())
        # Substitui espaços múltiplos por um único espaço
        normalized = re.sub(r'\s+', ' ', normalized)
        # Substituir espaços por underscores para um ID mais limpo
        normalized = normalized.strip().replace(' ', '_')
        return normalized
    
    def _extract_keywords(self, title: str) -> List[str]:
        """
        Extrai palavras-chave de um título para facilitar a busca
        
        Args:
            title: Título do áudio
            
        Returns:
            Lista de palavras-chave
        """
        # Normaliza o título
        normalized = self._normalize_filename(title)
        
        # Extrai as palavras
        words = normalized.split('_')
        
        # Filtra palavras muito curtas
        keywords = [word for word in words if len(word) > 3]
        
        # Adiciona o título normalizado completo
        keywords.append(normalized)
        
        return keywords
    
    def _add_audio_mappings(self, filename: Path, info: dict, youtube_id: str) -> None:
        """
        Adiciona várias formas de ID ao mapeamento de áudio.
        Isso aumenta as chances de encontrar o arquivo mais tarde.
        
        Args:
            filename: Caminho do arquivo de áudio
            info: Informações do vídeo obtidas do yt-dlp
            youtube_id: ID do vídeo do YouTube
        """
        # Mapeamentos básicos
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
                
                # Outra verificação: Se tem caminho de transcrição mas status não é "ended"
                if audio.get("transcription_path") and audio.get("transcription_status") != "ended":
                    path = Path(AUDIO_DIR.parent / audio["transcription_path"])
                    if path.exists():
                        audio["transcription_status"] = "ended"
                        changes_made = True
                        logger.debug(f"Ajustando status para 'ended' para áudio {audio.get('id')} que já tem transcrição")
            
            if changes_made:
                logger.info("Migração de dados concluída com sucesso. Salvando alterações.")
                self._save_audio_data()
            else:
                logger.info("Nenhuma alteração necessária durante a migração.")
        except Exception as e:
            logger.error(f"Erro durante a migração de dados: {str(e)}")
    
    def _execute_ydl_download(self, url: str, ydl_opts: dict, progress_data: dict, audio_id: str, sse_manager) -> dict:
        """Executa o download do yt-dlp em thread separada (método síncrono)"""
        import threading
        import time
        
        # Thread para monitorar progresso e enviar atualizações
        stop_monitoring = threading.Event()
        
        def monitor_progress():
            last_progress = 0
            while not stop_monitoring.is_set():
                current_progress = progress_data.get('current_progress', 0)
                if current_progress != last_progress and current_progress > 0:
                    # Atualizar no arquivo JSON
                    for i, audio in enumerate(self.audio_data["audios"]):
                        if audio["id"] == audio_id:
                            self.audio_data["audios"][i]["download_progress"] = current_progress
                            break
                    self._save_audio_data()
                    last_progress = current_progress
                
                time.sleep(1)  # Check a cada segundo
        
        # Iniciar thread de monitoramento
        monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        monitor_thread.start()
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # Preparar nome do arquivo para retorno
                original_filename = ydl.prepare_filename(info)
                return {
                    'info': info,
                    'filename': original_filename
                }
        finally:
            # Parar thread de monitoramento
            stop_monitoring.set()
            monitor_thread.join(timeout=1)
