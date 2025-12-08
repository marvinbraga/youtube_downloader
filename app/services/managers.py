import asyncio
import json
import re
import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import aiohttp
from fastapi import HTTPException
from loguru import logger
from yt_dlp import YoutubeDL

from app.services.configs import AUDIO_DIR, VIDEO_DIR, audio_mapping, video_mapping
from app.db.database import get_db_context
from app.db.models import Audio, Video
from app.db.repositories import AudioRepository, VideoRepository


class VideoStreamManager:
    def __init__(self):
        self.ydl_opts = {
            'format': 'best[ext=mp4]',
            'quiet': True,
            'no_warnings': True
        }

    async def get_direct_url(self, url: str) -> str:
        """Obtém a URL direta do stream do YouTube"""
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=False)
                )
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

                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        yield chunk

        except Exception as e:
            logger.error(f"Erro no streaming do YouTube: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro no streaming: {str(e)}"
            )


class AudioDownloadManager:
    """Gerencia o download de áudio do YouTube usando SQLite."""

    def __init__(self):
        self.download_dir = AUDIO_DIR
        logger.info(f"Gerenciador de download de áudio inicializado com diretório: {self.download_dir}")

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Extrai o ID do YouTube de uma URL"""
        try:
            youtube_id = None

            match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)', url)
            if match:
                youtube_id = match.group(1)

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

    async def get_audio_info(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """Obtém informações de um áudio pelo ID"""
        async with get_db_context() as session:
            repo = AudioRepository(session)
            audio = await repo.get_by_id(audio_id)
            if audio:
                return audio.to_dict()

            # Tenta buscar pelo youtube_id
            audio = await repo.get_by_youtube_id(audio_id)
            if audio:
                return audio.to_dict()

        return None

    async def get_audio_by_youtube_id(self, youtube_id: str) -> Optional[Dict[str, Any]]:
        """Obtém informações de um áudio pelo ID do YouTube"""
        async with get_db_context() as session:
            repo = AudioRepository(session)
            audio = await repo.get_by_youtube_id(youtube_id)
            if audio:
                return audio.to_dict()
        return None

    async def get_all_audios(self) -> list:
        """Lista todos os áudios"""
        async with get_db_context() as session:
            repo = AudioRepository(session)
            audios = await repo.get_all()
            return [a.to_dict() for a in audios]

    async def register_audio_for_download(self, url: str) -> str:
        """Registra um áudio para download com status 'downloading'."""
        try:
            logger.info(f"Registrando áudio para download: {url}")

            youtube_id = self.extract_youtube_id(url)
            if not youtube_id:
                youtube_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Verifica se já existe
            existing = await self.get_audio_by_youtube_id(youtube_id)
            if existing:
                logger.info(f"Áudio já existe com ID: {youtube_id}")
                return youtube_id

            # Obter informações básicas sem baixar
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }

            title = f"Video_{youtube_id}"
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', title)
            except Exception as extract_error:
                logger.warning(f"Erro ao extrair informações: {str(extract_error)}")

            # Criar entrada no banco
            async with get_db_context() as session:
                repo = AudioRepository(session)

                audio = Audio(
                    id=youtube_id,
                    title=title,
                    name=f"{title}.m4a",
                    youtube_id=youtube_id,
                    url=url,
                    path="",
                    directory="",
                    format="m4a",
                    filesize=0,
                    download_status="downloading",
                    download_progress=0,
                    download_error="",
                    transcription_status="none",
                    transcription_path="",
                    keywords=json.dumps(self._extract_keywords(title)),
                )

                await repo.create(audio)

            logger.info(f"Áudio registrado com ID: {youtube_id}")
            return youtube_id

        except Exception as e:
            error_str = str(e)
            logger.error(f"Erro ao registrar áudio: {error_str}")
            raise

    async def download_audio_with_status_async(self, audio_id: str, url: str, sse_manager=None) -> str:
        """Baixa o áudio e atualiza o status."""
        try:
            logger.info(f"Iniciando download real do áudio {audio_id}: {url}")

            if sse_manager:
                await sse_manager.download_started(audio_id, f"Iniciando download de {url}")

            download_dir = self.download_dir / audio_id
            download_dir.mkdir(exist_ok=True)

            progress_data = {'last_progress': 0}

            def simple_progress_hook(d):
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

            ydl_opts = {
                'format': 'bestaudio/best',
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
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'verbose': True,
                'noplaylist': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'DNT': '1',
                }
            }

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._execute_ydl_download(url, ydl_opts, progress_data, audio_id, sse_manager)
                )

                info = result['info']
                original_filename = result['filename']
            except Exception as download_error:
                error_str = str(download_error)
                logger.error(f"Erro durante download: {error_str}")

                async with get_db_context() as session:
                    repo = AudioRepository(session)
                    await repo.update_download_status(
                        audio_id,
                        status="error",
                        error=error_str[:500]
                    )

                if sse_manager:
                    await sse_manager.download_error(audio_id, f"Erro: {error_str}")

                raise

            filename = Path(original_filename).with_suffix('.m4a')

            if sse_manager:
                await sse_manager.download_progress(audio_id, 100, "Download concluído!")

            # Atualizar no banco
            async with get_db_context() as session:
                repo = AudioRepository(session)
                await repo.complete_download(
                    audio_id=audio_id,
                    path=str(filename.relative_to(self.download_dir.parent)),
                    directory=str(download_dir.relative_to(self.download_dir.parent)),
                    filesize=filename.stat().st_size if filename.exists() else 0
                )

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

            async with get_db_context() as session:
                repo = AudioRepository(session)
                await repo.update_download_status(audio_id, "error", error=str(e))

            raise

    async def update_transcription_status(
        self,
        audio_id: str,
        status: str,
        transcription_path: str = None
    ) -> bool:
        """Atualiza o status de transcrição de um áudio"""
        if status not in ["none", "started", "ended", "error"]:
            logger.warning(f"Status de transcrição inválido: {status}")
            return False

        async with get_db_context() as session:
            repo = AudioRepository(session)
            result = await repo.update_transcription_status(audio_id, status, transcription_path)
            if result:
                logger.info(f"Status da transcrição atualizado para '{status}' para áudio {audio_id}")
                return True

        logger.warning(f"Áudio não encontrado: {audio_id}")
        return False

    def _normalize_filename(self, filename: str) -> str:
        """Normaliza um nome de arquivo para ser usado como ID."""
        normalized = re.sub(r'[^\w\s]', ' ', filename.lower())
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip().replace(' ', '_')
        return normalized

    def _extract_keywords(self, title: str) -> list:
        """Extrai palavras-chave de um título"""
        normalized = self._normalize_filename(title)
        words = normalized.split('_')
        keywords = [word for word in words if len(word) > 3]
        keywords.append(normalized)
        return keywords

    def _add_audio_mappings(self, filename: Path, info: dict, youtube_id: str) -> None:
        """Adiciona várias formas de ID ao mapeamento de áudio."""
        title = info.get('title', '')

        audio_mapping[youtube_id] = filename
        logger.debug(f"Mapeamento adicionado: '{youtube_id}' -> {filename}")

        file_id = self._normalize_filename(filename.stem)
        audio_mapping[file_id] = filename

        title_id = self._normalize_filename(title)
        if title_id and title_id != file_id:
            audio_mapping[title_id] = filename

        for word in self._extract_keywords(title):
            audio_mapping[word] = filename

    def _execute_ydl_download(self, url: str, ydl_opts: dict, progress_data: dict, audio_id: str, sse_manager) -> dict:
        """Executa o download do yt-dlp em thread separada"""
        import threading
        import time

        stop_monitoring = threading.Event()

        def monitor_progress():
            last_progress = 0
            while not stop_monitoring.is_set():
                current_progress = progress_data.get('current_progress', 0)
                if current_progress != last_progress and current_progress > 0:
                    # Atualiza no banco de forma síncrona (em thread separada)
                    import asyncio
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._update_progress_async(audio_id, current_progress))
                        loop.close()
                    except Exception as e:
                        logger.debug(f"Erro ao atualizar progresso: {e}")
                    last_progress = current_progress
                time.sleep(1)

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

    async def _update_progress_async(self, audio_id: str, progress: int):
        """Atualiza o progresso no banco"""
        async with get_db_context() as session:
            repo = AudioRepository(session)
            await repo.update(audio_id, download_progress=progress)

    async def delete_audio(self, audio_id: str) -> bool:
        """Exclui um áudio do banco de dados e remove os arquivos físicos."""
        try:
            logger.info(f"Iniciando exclusão do áudio: {audio_id}")

            # Obtém informações do áudio antes de excluir
            audio_info = await self.get_audio_info(audio_id)
            if not audio_info:
                logger.warning(f"Áudio não encontrado: {audio_id}")
                return False

            # Remove o diretório físico do áudio
            audio_dir = self.download_dir / audio_id
            if audio_dir.exists() and audio_dir.is_dir():
                import shutil
                shutil.rmtree(audio_dir)
                logger.info(f"Diretório removido: {audio_dir}")

            # Remove do mapeamento em memória
            if audio_id in audio_mapping:
                del audio_mapping[audio_id]

            # Remove do banco de dados
            async with get_db_context() as session:
                repo = AudioRepository(session)
                result = await repo.delete(audio_id)

            logger.success(f"Áudio excluído com sucesso: {audio_id}")
            return result

        except Exception as e:
            logger.error(f"Erro ao excluir áudio {audio_id}: {str(e)}")
            raise

    # Mantém compatibilidade com código legado
    def migrate_has_transcription_to_status(self) -> None:
        """Migração não necessária com SQLite - mantida para compatibilidade"""
        logger.info("Migração de has_transcription não necessária com SQLite")


class VideoDownloadManager:
    """Gerencia o download de vídeo do YouTube usando SQLite."""

    RESOLUTION_MAP = {
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        "best": "bestvideo+bestaudio/best",
    }

    def __init__(self):
        self.download_dir = VIDEO_DIR
        logger.info(f"Gerenciador de download de vídeo inicializado com diretório: {self.download_dir}")

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Extrai o ID do YouTube de uma URL"""
        try:
            youtube_id = None

            match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)', url)
            if match:
                youtube_id = match.group(1)

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

    async def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Obtém informações de um vídeo pelo ID"""
        async with get_db_context() as session:
            repo = VideoRepository(session)
            video = await repo.get_by_id(video_id)
            if video:
                return video.to_dict()

            # Tenta buscar pelo youtube_id
            video = await repo.get_by_youtube_id(video_id)
            if video:
                return video.to_dict()

        return None

    async def get_video_by_youtube_id(self, youtube_id: str) -> Optional[Dict[str, Any]]:
        """Obtém informações de um vídeo pelo ID do YouTube"""
        async with get_db_context() as session:
            repo = VideoRepository(session)
            video = await repo.get_by_youtube_id(youtube_id)
            if video:
                return video.to_dict()
        return None

    async def get_all_videos(self) -> list:
        """Lista todos os vídeos"""
        async with get_db_context() as session:
            repo = VideoRepository(session)
            videos = await repo.get_all()
            return [v.to_dict() for v in videos]

    async def register_video_for_download(self, url: str, resolution: str = "1080p") -> str:
        """Registra um vídeo para download com status 'downloading'."""
        try:
            logger.info(f"Registrando vídeo para download: {url}")

            youtube_id = self.extract_youtube_id(url)
            if not youtube_id:
                youtube_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Verifica se já existe
            existing = await self.get_video_by_youtube_id(youtube_id)
            if existing:
                logger.info(f"Vídeo já existe com ID: {youtube_id}")
                return youtube_id

            # Obter informações básicas sem baixar
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }

            title = f"Video_{youtube_id}"
            duration = None
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', title)
                    duration = info.get('duration')
            except Exception as extract_error:
                logger.warning(f"Erro ao extrair informações: {str(extract_error)}")

            # Criar entrada no banco
            async with get_db_context() as session:
                repo = VideoRepository(session)

                video = Video(
                    id=youtube_id,
                    title=title,
                    name=f"{title}.mp4",
                    youtube_id=youtube_id,
                    url=url,
                    path="",
                    directory="",
                    format="mp4",
                    filesize=0,
                    duration=duration,
                    resolution=resolution,
                    download_status="downloading",
                    download_progress=0,
                    download_error="",
                    source="youtube",
                )

                await repo.create(video)

            logger.info(f"Vídeo registrado com ID: {youtube_id}")
            return youtube_id

        except Exception as e:
            error_str = str(e)
            logger.error(f"Erro ao registrar vídeo: {error_str}")
            raise

    async def download_video_with_status_async(
        self,
        video_id: str,
        url: str,
        resolution: str = "1080p",
        sse_manager=None
    ) -> str:
        """Baixa o vídeo e atualiza o status."""
        try:
            logger.info(f"Iniciando download real do vídeo {video_id}: {url}")

            if sse_manager:
                await sse_manager.download_started(video_id, f"Iniciando download de {url}")

            download_dir = self.download_dir / video_id
            download_dir.mkdir(exist_ok=True)

            progress_data = {'last_progress': 0}

            def simple_progress_hook(d):
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

            # Seleciona o formato baseado na resolução
            format_str = self.RESOLUTION_MAP.get(resolution, self.RESOLUTION_MAP["1080p"])

            ydl_opts = {
                'format': format_str,
                'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'progress_hooks': [simple_progress_hook],
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'verbose': True,
                'noplaylist': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'DNT': '1',
                }
            }

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._execute_ydl_download(url, ydl_opts, progress_data, video_id, sse_manager)
                )

                info = result['info']
                original_filename = result['filename']
            except Exception as download_error:
                error_str = str(download_error)
                logger.error(f"Erro durante download: {error_str}")

                async with get_db_context() as session:
                    repo = VideoRepository(session)
                    await repo.update_download_status(
                        video_id,
                        status="error",
                        error=error_str[:500]
                    )

                if sse_manager:
                    await sse_manager.download_error(video_id, f"Erro: {error_str}")

                raise

            # Procura o arquivo mp4 baixado
            filename = Path(original_filename)
            if not filename.suffix == '.mp4':
                # yt-dlp pode ter criado um arquivo com extensão diferente
                mp4_files = list(download_dir.glob('*.mp4'))
                if mp4_files:
                    filename = mp4_files[0]
                else:
                    filename = Path(original_filename).with_suffix('.mp4')

            if sse_manager:
                await sse_manager.download_progress(video_id, 100, "Download concluído!")

            # Obtém a resolução real do vídeo baixado
            actual_resolution = info.get('resolution', resolution)
            duration = info.get('duration')

            # Atualizar no banco
            async with get_db_context() as session:
                repo = VideoRepository(session)
                await repo.complete_download(
                    video_id=video_id,
                    path=str(filename.relative_to(self.download_dir.parent)),
                    directory=str(download_dir.relative_to(self.download_dir.parent)),
                    filesize=filename.stat().st_size if filename.exists() else 0,
                    duration=duration,
                    resolution=actual_resolution
                )

            # Atualizar mapeamento em memória
            self._add_video_mappings(filename, info, video_id)

            if sse_manager:
                await sse_manager.download_completed(video_id, f"Download concluído: {filename.name}")

            logger.success(f"Download de vídeo concluído: {filename}")
            return str(filename)

        except Exception as e:
            logger.exception(f"Erro no download de vídeo: {str(e)}")

            if sse_manager:
                await sse_manager.download_error(video_id, str(e))

            async with get_db_context() as session:
                repo = VideoRepository(session)
                await repo.update_download_status(video_id, "error", error=str(e))

            raise

    def _normalize_filename(self, filename: str) -> str:
        """Normaliza um nome de arquivo para ser usado como ID."""
        normalized = re.sub(r'[^\w\s]', ' ', filename.lower())
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip().replace(' ', '_')
        return normalized

    def _add_video_mappings(self, filename: Path, info: dict, youtube_id: str) -> None:
        """Adiciona várias formas de ID ao mapeamento de vídeo."""
        title = info.get('title', '')

        video_mapping[youtube_id] = filename
        logger.debug(f"Mapeamento de vídeo adicionado: '{youtube_id}' -> {filename}")

        file_id = self._normalize_filename(filename.stem)
        video_mapping[file_id] = filename

        title_id = self._normalize_filename(title)
        if title_id and title_id != file_id:
            video_mapping[title_id] = filename

    def _execute_ydl_download(self, url: str, ydl_opts: dict, progress_data: dict, video_id: str, sse_manager) -> dict:
        """Executa o download do yt-dlp em thread separada"""
        import threading
        import time

        stop_monitoring = threading.Event()

        def monitor_progress():
            last_progress = 0
            while not stop_monitoring.is_set():
                current_progress = progress_data.get('current_progress', 0)
                if current_progress != last_progress and current_progress > 0:
                    # Atualiza no banco de forma síncrona (em thread separada)
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._update_progress_async(video_id, current_progress))
                        loop.close()
                    except Exception as e:
                        logger.debug(f"Erro ao atualizar progresso: {e}")
                    last_progress = current_progress
                time.sleep(1)

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

    async def _update_progress_async(self, video_id: str, progress: int):
        """Atualiza o progresso no banco"""
        async with get_db_context() as session:
            repo = VideoRepository(session)
            await repo.update(video_id, download_progress=progress)

    async def delete_video(self, video_id: str) -> bool:
        """Exclui um vídeo do banco de dados e remove os arquivos físicos."""
        try:
            logger.info(f"Iniciando exclusão do vídeo: {video_id}")

            # Obtém informações do vídeo antes de excluir
            video_info = await self.get_video_info(video_id)
            if not video_info:
                logger.warning(f"Vídeo não encontrado: {video_id}")
                return False

            # Remove o diretório físico do vídeo
            video_dir = self.download_dir / video_id
            if video_dir.exists() and video_dir.is_dir():
                import shutil
                shutil.rmtree(video_dir)
                logger.info(f"Diretório removido: {video_dir}")

            # Remove do mapeamento em memória
            if video_id in video_mapping:
                del video_mapping[video_id]

            # Remove do banco de dados
            async with get_db_context() as session:
                repo = VideoRepository(session)
                result = await repo.delete(video_id)

            logger.success(f"Vídeo excluído com sucesso: {video_id}")
            return result

        except Exception as e:
            logger.error(f"Erro ao excluir vídeo {video_id}: {str(e)}")
            raise

    async def update_transcription_status(
        self,
        video_id: str,
        status: str,
        transcription_path: str = None
    ) -> bool:
        """Atualiza o status de transcrição de um vídeo"""
        if status not in ["none", "started", "ended", "error"]:
            logger.warning(f"Status de transcrição inválido: {status}")
            return False

        async with get_db_context() as session:
            repo = VideoRepository(session)
            result = await repo.update_transcription_status(video_id, status, transcription_path)
            if result:
                logger.info(f"Status da transcrição atualizado para '{status}' para vídeo {video_id}")
                return True

        logger.warning(f"Vídeo não encontrado: {video_id}")
        return False
