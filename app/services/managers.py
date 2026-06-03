import asyncio
import json
import os
import re
import shutil
import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import aiohttp
from fastapi import HTTPException
from loguru import logger
from yt_dlp import YoutubeDL

from app.services.configs import (
    AUDIO_DIR,
    VIDEO_DIR,
    audio_mapping,
    video_mapping,
    get_yt_dlp_cookies_opts,
    S3_DELETE_LOCAL_AFTER_UPLOAD,
    STORAGE_BACKEND,
)
from app.db.database import get_db_context
from app.db.models import Audio, Video
from app.db.repositories import AudioRepository, VideoRepository
from app.services.downloaders import get_downloader
from app.services.storage import get_storage

# Detecta deno e node para resolver JS challenges do YouTube
_deno_path = shutil.which("deno") or os.path.expanduser("~/.deno/bin/deno")
_node_path = shutil.which("node") or os.path.expanduser(
    "~/.nvm/versions/node/v20.19.6/bin/node"
)

YDL_JS_RUNTIMES = {}
if _deno_path and os.path.exists(_deno_path):
    YDL_JS_RUNTIMES["deno"] = {"path": _deno_path}
if _node_path and os.path.exists(_node_path):
    YDL_JS_RUNTIMES["node"] = {"path": _node_path}

if not YDL_JS_RUNTIMES:
    logger.warning("Nenhum runtime JS encontrado (deno/node). Downloads podem falhar.")

# Script de challenge solver baixado do GitHub (equivalente a --remote-components ejs:github)
YDL_REMOTE_COMPONENTS = ["ejs:github"]

# YouTube video IDs são sempre 11 caracteres alfanuméricos (inclui _ e -)
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{11}$")


def extract_external_id(url: str) -> tuple:
    """Return ``(source, external_id)`` for ``url``.

    Falls back to a timestamp-based ID if the platform extractor cannot derive one.
    Raises ``ValueError`` if the URL host is not supported.
    """
    downloader = get_downloader(url)  # raises ValueError on unsupported host
    ext_id = downloader.extract_id(url)
    if not ext_id:
        ext_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return downloader.source, ext_id


# v1 scope: VideoStreamManager is intentionally NOT refactored to use the
# Downloader Strategy. It depends on yt-dlp's "best[ext=mp4]" format selector
# to expose a top-level info["url"], which the Strategy's get_info() does not
# guarantee. Streaming remains YouTube-only until a future
# Downloader.build_stream_opts() lands. Instagram playback (when needed)
# would use the downloaded file path via existing /audio/stream / /video/stream
# file-based endpoints.
class VideoStreamManager:
    def __init__(self):
        self.ydl_opts = {
            "format": "best[ext=mp4]",
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": YDL_JS_RUNTIMES,
        }

    async def get_direct_url(self, url: str) -> str:
        """Obtém a URL direta do stream do YouTube"""
        try:
            ydl_opts = {**self.ydl_opts, **get_yt_dlp_cookies_opts()}
            with YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                return info["url"]
        except Exception as e:
            logger.error(f"Erro ao obter URL do YouTube: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Erro ao processar vídeo do YouTube: {str(e)}"
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
                            detail="Erro ao acessar stream do YouTube",
                        )

                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        yield chunk

        except Exception as e:
            logger.error(f"Erro no streaming do YouTube: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Erro no streaming: {str(e)}")


class AudioDownloadManager:
    """Gerencia o download de áudio do YouTube usando SQLite."""

    def __init__(self):
        self.download_dir = AUDIO_DIR
        logger.info(
            f"Gerenciador de download de áudio inicializado com diretório: {self.download_dir}"
        )

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Legacy: returns the external_id for any supported URL.

        Despite the YouTube-flavored name (kept for backward compat with the
        ``/audio/check_exists`` endpoint), this resolves Instagram URLs too.
        """
        try:
            _, ext_id = extract_external_id(url)
            return ext_id
        except ValueError as exc:
            logger.warning(f"URL não suportada para extração de ID: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Erro ao extrair ID externo: {exc}")
            return None

    async def get_audio_info(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """Obtém informações de um áudio pelo ID"""
        async with get_db_context() as session:
            repo = AudioRepository(session)
            audio = await repo.get_by_id(audio_id)
            if audio:
                return audio.to_dict()

            # Fallback: buscar pelo external_id (cobre todas as sources)
            audio = await repo.get_by_external_id(audio_id)
            if audio:
                return audio.to_dict()

        return None

    async def get_audio_by_youtube_id(
        self, external_id: str
    ) -> Optional[Dict[str, Any]]:
        """Obtém informações de um áudio pelo external_id.

        Nome legacy preservado por compat com o endpoint /audio/check_exists.
        A busca usa `external_id` para cobrir todas as sources.
        """
        async with get_db_context() as session:
            repo = AudioRepository(session)
            audio = await repo.get_by_external_id(external_id)
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
        """Registra um áudio para download com status 'downloading'.

        Multi-source: dispara o downloader correto via factory e persiste
        ``source`` + ``external_id``. O ID primário da linha continua sendo
        o ``external_id`` (mantém o mesmo padrão histórico em que ``id == youtube_id``).
        """
        try:
            logger.info(f"Registrando áudio para download: {url}")

            downloader = get_downloader(url)  # raises ValueError on unsupported host
            source = downloader.source

            external_id = downloader.extract_id(url)
            if not external_id:
                # Sintetizar timestamp ID só é seguro para YouTube (histórico).
                # Para outras sources, isso geraria linhas-lixo cujo external_id
                # nunca casa com nada que yt-dlp consiga baixar.
                if source != "youtube":
                    raise ValueError(
                        f"URL não suportada para download ({source}): {url}"
                    )
                external_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Dedup por (source, external_id) — evita falso-positivo cross-platform
            async with get_db_context() as session:
                repo = AudioRepository(session)
                existing = await repo.get_by_external_id(external_id, source=source)

                if existing is not None:
                    if existing.download_status not in ("error", ""):
                        logger.info(
                            f"Áudio já existe (source={source}, ext_id={external_id})"
                        )
                        return existing.id
                    # Reprocessa erro: reseta status
                    logger.info(
                        f"Áudio {existing.id} estava com status '{existing.download_status}', "
                        "resetando para nova tentativa"
                    )
                    await repo.update(
                        existing.id,
                        download_status="downloading",
                        download_progress=0,
                        download_error="",
                    )
                    return existing.id

            # Extrai título sem baixar
            title = f"Video_{external_id}"
            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, downloader.get_info, url)
                title = info.get("title") or title
            except Exception as extract_error:
                logger.warning(f"Erro ao extrair informações: {extract_error}")

            # YouTube preserva populamento de ``youtube_id`` para compat;
            # outras sources deixam essa coluna NULL.
            youtube_id_value = external_id if source == "youtube" else None

            async with get_db_context() as session:
                repo = AudioRepository(session)
                audio = Audio(
                    id=external_id,
                    title=title,
                    name=f"{title}.m4a",
                    source=source,
                    external_id=external_id,
                    youtube_id=youtube_id_value,
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

            logger.info(f"Áudio registrado: id={external_id} source={source}")
            return external_id

        except ValueError as ve:
            logger.error(f"URL não suportada: {ve}")
            raise
        except Exception as e:
            logger.error(f"Erro ao registrar áudio: {e}")
            raise

    async def download_audio_with_status_async(
        self, audio_id: str, url: str, sse_manager=None
    ) -> str:
        """Baixa o áudio e atualiza o status."""
        try:
            logger.info(f"Iniciando download real do áudio {audio_id}: {url}")

            if sse_manager:
                await sse_manager.download_started(
                    audio_id, f"Iniciando download de {url}"
                )

            download_dir = self.download_dir / audio_id
            download_dir.mkdir(exist_ok=True)

            progress_data = {"last_progress": 0}

            def simple_progress_hook(d):
                if d["status"] == "downloading":
                    if d.get("total_bytes"):
                        progress = int(d["downloaded_bytes"] / d["total_bytes"] * 100)
                    elif d.get("total_bytes_estimate"):
                        progress = int(
                            d["downloaded_bytes"] / d["total_bytes_estimate"] * 100
                        )
                    else:
                        progress = 0
                    progress_data["current_progress"] = progress
                    progress_data["status"] = "downloading"
                elif d["status"] == "finished":
                    progress_data["current_progress"] = 95
                    progress_data["status"] = "finished"

            downloader = get_downloader(url)
            ydl_opts = downloader.build_audio_opts(
                output_dir=str(download_dir),
                progress_hook=simple_progress_hook,
            )

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._execute_ydl_download(
                        url, ydl_opts, progress_data, audio_id, sse_manager
                    ),
                )

                info = result["info"]
                original_filename = result["filename"]
            except Exception as download_error:
                error_str = str(download_error)
                logger.error(f"Erro durante download: {error_str}")

                async with get_db_context() as session:
                    repo = AudioRepository(session)
                    await repo.update_download_status(
                        audio_id, status="error", error=error_str[:500]
                    )

                if sse_manager:
                    await sse_manager.download_error(audio_id, f"Erro: {error_str}")

                raise

            filename = Path(original_filename).with_suffix(".m4a")

            if sse_manager:
                await sse_manager.download_progress(
                    audio_id, 100, "Download concluído!"
                )

            # Atualizar no banco
            actual_title = info.get("title", "").strip()
            async with get_db_context() as session:
                repo = AudioRepository(session)
                await repo.complete_download(
                    audio_id=audio_id,
                    path=str(filename.relative_to(self.download_dir.parent)),
                    directory=str(download_dir.relative_to(self.download_dir.parent)),
                    filesize=filename.stat().st_size if filename.exists() else 0,
                )
                # Corrige o título se ficou como fallback (Video_{id})
                if actual_title and actual_title != f"Video_{audio_id}":
                    await repo.update(
                        audio_id,
                        title=actual_title,
                        name=f"{actual_title}.m4a",
                    )

            # Storage strategy hook: upload to S3 if STORAGE_BACKEND=s3,
            # then optionally remove the local file. No-op for local backend.
            relative_path = str(filename.relative_to(self.download_dir.parent))
            await self._upload_to_storage_if_needed(audio_id, filename, relative_path)

            # Atualizar mapeamento em memória
            self._add_audio_mappings(filename, info, audio_id)

            if sse_manager:
                await sse_manager.download_completed(
                    audio_id, f"Download concluído: {filename.name}"
                )

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
        self, audio_id: str, status: str, transcription_path: str = None
    ) -> bool:
        """Atualiza o status de transcrição de um áudio"""
        if status not in ["none", "queued", "started", "ended", "error"]:
            logger.warning(f"Status de transcrição inválido: {status}")
            return False

        async with get_db_context() as session:
            repo = AudioRepository(session)
            result = await repo.update_transcription_status(
                audio_id, status, transcription_path
            )
            if result:
                logger.info(
                    f"Status da transcrição atualizado para '{status}' para áudio {audio_id}"
                )
                return True

        logger.warning(f"Áudio não encontrado: {audio_id}")
        return False

    def _normalize_filename(self, filename: str) -> str:
        """Normaliza um nome de arquivo para ser usado como ID."""
        normalized = re.sub(r"[^\w\s]", " ", filename.lower())
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip().replace(" ", "_")
        return normalized

    def _extract_keywords(self, title: str) -> list:
        """Extrai palavras-chave de um título"""
        normalized = self._normalize_filename(title)
        words = normalized.split("_")
        keywords = [word for word in words if len(word) > 3]
        keywords.append(normalized)
        return keywords

    def _add_audio_mappings(self, filename: Path, info: dict, youtube_id: str) -> None:
        """Adiciona várias formas de ID ao mapeamento de áudio."""
        title = info.get("title", "")

        audio_mapping[youtube_id] = filename
        logger.debug(f"Mapeamento adicionado: '{youtube_id}' -> {filename}")

        file_id = self._normalize_filename(filename.stem)
        audio_mapping[file_id] = filename

        title_id = self._normalize_filename(title)
        if title_id and title_id != file_id:
            audio_mapping[title_id] = filename

        for word in self._extract_keywords(title):
            audio_mapping[word] = filename

    def _execute_ydl_download(
        self, url: str, ydl_opts: dict, progress_data: dict, audio_id: str, sse_manager
    ) -> dict:
        """Executa o download do yt-dlp em thread separada"""
        import threading
        import time

        stop_monitoring = threading.Event()

        def monitor_progress():
            last_progress = 0
            while not stop_monitoring.is_set():
                current_progress = progress_data.get("current_progress", 0)
                if current_progress != last_progress and current_progress > 0:
                    # Atualiza no banco de forma síncrona (em thread separada)
                    import asyncio

                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            self._update_progress_async(audio_id, current_progress)
                        )
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
                return {"info": info, "filename": original_filename}
        finally:
            stop_monitoring.set()
            monitor_thread.join(timeout=1)

    async def _update_progress_async(self, audio_id: str, progress: int):
        """Atualiza o progresso no banco"""
        async with get_db_context() as session:
            repo = AudioRepository(session)
            await repo.update(audio_id, download_progress=progress)

    async def _upload_to_storage_if_needed(
        self, audio_id: str, local_filename: Path, relative_path: str
    ) -> None:
        """Upload the finished audio to the active storage backend.

        For LocalStorage this is a no-op. For S3Storage this PUTs the
        file under key=relative_path, persists `s3_key` + `storage_backend='s3'`
        in the DB, and (if S3_DELETE_LOCAL_AFTER_UPLOAD) deletes the
        local file and its parent directory.

        H1: this method is idempotent. If the row already has
        `storage_backend='s3'` + a `s3_key` that resolves in the bucket, we
        short-circuit before touching S3.

        H2: between the PUT and the DB update, we re-fetch the row in the same
        session to detect a concurrent `delete_audio`. If the row vanished, we
        best-effort delete the just-uploaded S3 object to avoid an orphan.

        M3 (documented, not fixed): when the S3 upload fails, the row keeps
        `download_status='ready'` (local file is OK) AND
        `download_error="S3 upload failed: ..."` (signals the secondary
        issue). Retrying is via re-invoking this method, which is now
        idempotent (H1 short-circuit if the previous attempt succeeded).
        Adding a dedicated `storage_status` column is the proper long-term
        fix but requires a new Alembic-style migration; deferred to v2.
        """
        if STORAGE_BACKEND != "s3":
            return  # LocalStorage: nothing to do

        storage = get_storage()

        # H1: idempotency. If a previous invocation already promoted this row
        # to S3 and the object is reachable, do nothing.
        async with get_db_context() as session:
            repo = AudioRepository(session)
            current = await repo.get_by_id(audio_id)

        if current is not None and current.storage_backend == "s3" and current.s3_key:
            try:
                if await storage.exists(current.s3_key):
                    logger.info(
                        f"Audio {audio_id} already uploaded to s3://.../{current.s3_key}, "
                        f"skipping re-upload (idempotency)."
                    )
                    return
            except Exception as exists_err:
                # head_object failure shouldn't block a re-upload attempt;
                # fall through to PUT (which is itself idempotent on the bucket).
                logger.debug(
                    f"S3 exists() check failed for {current.s3_key}, "
                    f"proceeding with re-upload: {exists_err}"
                )

        try:
            s3_key = await storage.put_file(local_filename, relative_path)
        except Exception as upload_err:
            logger.error(
                f"S3 upload failed for audio {audio_id}: {upload_err}. "
                f"Row remains storage_backend='local'."
            )
            # M3: surfacing the failure via download_error is intentional even
            # though `download_status` stays 'ready'. The local copy is usable;
            # the operator-visible signal here is "S3 promotion did not happen,
            # retry on demand".
            async with get_db_context() as session:
                repo = AudioRepository(session)
                await repo.update(
                    audio_id,
                    download_error=f"S3 upload failed: {str(upload_err)[:480]}",
                )
            return

        # H2: re-fetch in the same session before updating to detect a race
        # with delete_audio. If the row was deleted while we were uploading,
        # best-effort delete the S3 object to prevent an orphan.
        async with get_db_context() as session:
            repo = AudioRepository(session)
            still_present = await repo.get_by_id(audio_id)
            if still_present is None:
                logger.warning(
                    f"Audio {audio_id} row was deleted during S3 upload "
                    f"(orphan key={s3_key}). Best-effort S3 delete."
                )
                try:
                    await storage.delete(s3_key)
                except Exception as orphan_err:
                    logger.warning(
                        f"Orphan S3 cleanup failed for {s3_key}: {orphan_err}"
                    )
                return
            await repo.update(
                audio_id,
                storage_backend="s3",
                s3_key=s3_key,
            )

        if S3_DELETE_LOCAL_AFTER_UPLOAD:
            try:
                if local_filename.exists():
                    local_filename.unlink()
                parent = local_filename.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                logger.info(f"Local copy removed for audio {audio_id} after S3 upload.")
            except Exception as cleanup_err:
                logger.warning(
                    f"Local cleanup failed for audio {audio_id}: {cleanup_err}"
                )

    async def delete_audio(self, audio_id: str) -> bool:
        """Exclui um áudio do banco, S3 (se aplicável) e arquivos locais.

        M4: order is now `local FS -> DB row -> S3`. Rationale: an orphan in
        S3 is recoverable via a sweeper job; an orphan DB row pointing at a
        404 S3 key produces a streaming error with no obvious remediation.
        S3 delete is best-effort and logged.
        """
        try:
            logger.info(f"Iniciando exclusão do áudio: {audio_id}")

            audio_info = await self.get_audio_info(audio_id)
            if not audio_info:
                logger.warning(f"Áudio não encontrado: {audio_id}")
                return False

            # 1) Local filesystem cleanup. Safe even for S3 rows: directory
            # may have been auto-removed at upload time, or kept if
            # S3_DELETE_LOCAL_AFTER_UPLOAD=false.
            audio_dir = self.download_dir / audio_id
            if audio_dir.exists() and audio_dir.is_dir():
                shutil.rmtree(audio_dir)
                logger.info(f"Diretório removido: {audio_dir}")

            if audio_id in audio_mapping:
                del audio_mapping[audio_id]

            # 2) DB row removal — once this commits, the audio is logically gone.
            async with get_db_context() as session:
                repo = AudioRepository(session)
                result = await repo.delete(audio_id)

            # 3) Best-effort S3 delete. After the DB row is gone, an S3 orphan
            # is recoverable (and not user-visible) — never block the delete
            # on this step.
            if audio_info.get("storage_backend") == "s3" and audio_info.get("s3_key"):
                try:
                    storage = get_storage()
                    await storage.delete(audio_info["s3_key"])
                except Exception as s3_err:
                    logger.warning(
                        f"S3 delete failed for {audio_id} "
                        f"(DB+local already cleaned up): {s3_err}"
                    )

            logger.success(f"Áudio excluído com sucesso: {audio_id}")
            return result

        except Exception as e:
            logger.exception(f"Erro ao excluir áudio {audio_id}: {e}")
            raise

    # Mantém compatibilidade com código legado
    def migrate_has_transcription_to_status(self) -> None:
        """Migração não necessária com SQLite - mantida para compatibilidade"""
        logger.info("Migração de has_transcription não necessária com SQLite")

    # Design decision: playlist extraction lives on AudioDownloadManager because playlist
    # metadata feeds the audio download queue. VideoDownloadManager receives an identical
    # copy (Task 3) since both share the same yt-dlp extraction pattern. Future refactor
    # could extract a shared _extract_playlist_info() module-level helper.
    async def extract_playlist_info(self, url: str) -> dict:
        """Extrai informações de uma playlist do YouTube sem baixar.

        Returns:
            {
                "title": str,
                "webpage_url": str,
                "entries": [{"id": str, "title": str, "url": str}, ...]
            }

        Raises ValueError if:
        - URL host is not in the YouTube allowlist
        - yt-dlp returns no information
        - URL yields no entries (e.g. single video URL)

        Runs yt-dlp in executor to avoid blocking the event loop.

        Also propagates yt-dlp exceptions (e.g. DownloadError) after logging.
        """
        # TODO(review): move import urllib.parse to module top-level - code-reviewer, 2026-04-28, Severity: Low
        import urllib.parse

        # NOTE: Playlist support is YouTube-only for v1. Instagram has no
        # native playlist concept that maps cleanly to yt-dlp's flat extractor.
        # Tracked as a non-goal in docs/plans/2026-05-13-instagram-support.md.
        # TODO(review): move _ALLOWED_HOSTS to module-level constant to avoid per-call allocation - code-reviewer, 2026-04-28, Severity: Low
        _ALLOWED_HOSTS = {
            "youtube.com",
            "www.youtube.com",
            "youtu.be",
            "music.youtube.com",
            "m.youtube.com",
        }

        parsed = urllib.parse.urlparse(str(url))
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Esquema de URL não suportado: {parsed.scheme!r}")
        if parsed.username or parsed.password:
            raise ValueError("URL com credenciais embutidas não é permitida.")
        host = parsed.hostname or ""
        if host not in _ALLOWED_HOSTS:
            raise ValueError(
                "Host da URL não está na lista permitida para extração de playlist."
            )

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "js_runtimes": YDL_JS_RUNTIMES,
            "remote_components": YDL_REMOTE_COMPONENTS,
            **get_yt_dlp_cookies_opts(),
        }

        def _extract():
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(str(url), download=False)

        logger.info(f"Extraindo informações de playlist: {url}")

        try:
            loop = asyncio.get_running_loop()
            info = await loop.run_in_executor(None, _extract)
        except Exception as exc:
            logger.error(
                "Erro ao extrair playlist '%s': %s", type(exc).__name__, str(exc)[:200]
            )
            raise

        if info is None:
            raise ValueError("yt-dlp não retornou informações para a URL fornecida.")

        entries_raw = info.get("entries") or []
        if not entries_raw:
            raise ValueError(
                "URL não parece ser uma playlist ou não retornou entradas."
            )

        entries = []
        for entry in entries_raw:
            if entry is None:
                continue
            video_id = entry.get("id") or ""
            if not video_id:
                logger.warning(
                    "Entrada de playlist sem ID ignorada: %s",
                    entry.get("title", "desconhecido"),
                )
                continue
            if not _YOUTUBE_ID_RE.match(video_id):
                logger.warning(
                    "Entrada de playlist com ID inválido ignorada: %s",
                    entry.get("title", "desconhecido"),
                )
                continue
            title = (
                entry.get("title") or entry.get("webpage_title") or f"Video_{video_id}"
            )
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            entries.append({"id": video_id, "title": title, "url": watch_url})

        if not entries:
            raise ValueError(
                "Nenhuma entrada com ID válido encontrada na playlist "
                "(todos os vídeos podem ser privados ou excluídos)."
            )

        logger.info(
            "Playlist '%s': %d entradas encontradas.",
            info.get("title") or "sem título",
            len(entries),
        )

        return {
            "title": info.get("title") or info.get("webpage_title") or "Playlist",
            "webpage_url": info.get("webpage_url") or str(url),
            "entries": entries,
        }


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
        logger.info(
            f"Gerenciador de download de vídeo inicializado com diretório: {self.download_dir}"
        )

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Legacy: returns the external_id for any supported URL."""
        try:
            _, ext_id = extract_external_id(url)
            return ext_id
        except ValueError as exc:
            logger.warning(f"URL não suportada para extração de ID: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Erro ao extrair ID externo: {exc}")
            return None

    async def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Obtém informações de um vídeo pelo ID"""
        async with get_db_context() as session:
            repo = VideoRepository(session)
            video = await repo.get_by_id(video_id)
            if video:
                return video.to_dict()

            # Fallback: buscar pelo external_id (cobre todas as sources)
            video = await repo.get_by_external_id(video_id)
            if video:
                return video.to_dict()

        return None

    async def get_video_by_youtube_id(
        self, external_id: str
    ) -> Optional[Dict[str, Any]]:
        """Obtém informações de um vídeo pelo external_id.

        Nome legacy preservado por compat. A busca usa `external_id` para
        cobrir todas as sources.
        """
        async with get_db_context() as session:
            repo = VideoRepository(session)
            video = await repo.get_by_external_id(external_id)
            if video:
                return video.to_dict()
        return None

    async def get_all_videos(self) -> list:
        """Lista todos os vídeos"""
        async with get_db_context() as session:
            repo = VideoRepository(session)
            videos = await repo.get_all()
            return [v.to_dict() for v in videos]

    async def register_video_for_download(
        self, url: str, resolution: str = "1080p"
    ) -> str:
        """Registra um vídeo para download com status 'downloading'."""
        try:
            logger.info(f"Registrando vídeo para download: {url}")

            downloader = get_downloader(url)
            source = downloader.source

            external_id = downloader.extract_id(url)
            if not external_id:
                if source != "youtube":
                    raise ValueError(
                        f"URL não suportada para download ({source}): {url}"
                    )
                external_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            async with get_db_context() as session:
                repo = VideoRepository(session)
                existing = await repo.get_by_external_id(external_id, source=source)

                if existing is not None:
                    if existing.download_status not in ("error", ""):
                        logger.info(
                            f"Vídeo já existe (source={source}, ext_id={external_id})"
                        )
                        return existing.id
                    logger.info(
                        f"Vídeo {existing.id} estava com status '{existing.download_status}', "
                        "resetando para nova tentativa"
                    )
                    await repo.update(
                        existing.id,
                        download_status="downloading",
                        download_progress=0,
                        download_error="",
                    )
                    return existing.id

            title = f"Video_{external_id}"
            duration = None
            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, downloader.get_info, url)
                title = info.get("title") or title
                duration = info.get("duration")
            except Exception as extract_error:
                logger.warning(f"Erro ao extrair informações: {extract_error}")

            youtube_id_value = external_id if source == "youtube" else None

            async with get_db_context() as session:
                repo = VideoRepository(session)
                video = Video(
                    id=external_id,
                    title=title,
                    name=f"{title}.mp4",
                    source=source,
                    external_id=external_id,
                    youtube_id=youtube_id_value,
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
                )
                await repo.create(video)

            logger.info(f"Vídeo registrado: id={external_id} source={source}")
            return external_id

        except ValueError as ve:
            logger.error(f"URL não suportada: {ve}")
            raise
        except Exception as e:
            logger.error(f"Erro ao registrar vídeo: {e}")
            raise

    async def download_video_with_status_async(
        self, video_id: str, url: str, resolution: str = "1080p", sse_manager=None
    ) -> str:
        """Baixa o vídeo e atualiza o status."""
        try:
            logger.info(f"Iniciando download real do vídeo {video_id}: {url}")

            if sse_manager:
                await sse_manager.download_started(
                    video_id, f"Iniciando download de {url}"
                )

            download_dir = self.download_dir / video_id
            download_dir.mkdir(exist_ok=True)

            progress_data = {"last_progress": 0}

            def simple_progress_hook(d):
                if d["status"] == "downloading":
                    if d.get("total_bytes"):
                        progress = int(d["downloaded_bytes"] / d["total_bytes"] * 100)
                    elif d.get("total_bytes_estimate"):
                        progress = int(
                            d["downloaded_bytes"] / d["total_bytes_estimate"] * 100
                        )
                    else:
                        progress = 0
                    progress_data["current_progress"] = progress
                    progress_data["status"] = "downloading"
                elif d["status"] == "finished":
                    progress_data["current_progress"] = 95
                    progress_data["status"] = "finished"

            downloader = get_downloader(url)
            ydl_opts = downloader.build_video_opts(
                output_dir=str(download_dir),
                resolution=resolution,
                progress_hook=simple_progress_hook,
            )

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._execute_ydl_download(
                        url, ydl_opts, progress_data, video_id, sse_manager
                    ),
                )

                info = result["info"]
                original_filename = result["filename"]
            except Exception as download_error:
                error_str = str(download_error)
                logger.error(f"Erro durante download: {error_str}")

                async with get_db_context() as session:
                    repo = VideoRepository(session)
                    await repo.update_download_status(
                        video_id, status="error", error=error_str[:500]
                    )

                if sse_manager:
                    await sse_manager.download_error(video_id, f"Erro: {error_str}")

                raise

            # Procura o arquivo mp4 baixado
            filename = Path(original_filename)
            if not filename.suffix == ".mp4":
                # yt-dlp pode ter criado um arquivo com extensão diferente
                mp4_files = list(download_dir.glob("*.mp4"))
                if mp4_files:
                    filename = mp4_files[0]
                else:
                    filename = Path(original_filename).with_suffix(".mp4")

            if sse_manager:
                await sse_manager.download_progress(
                    video_id, 100, "Download concluído!"
                )

            # Obtém a resolução real do vídeo baixado
            actual_resolution = info.get("resolution", resolution)
            duration = info.get("duration")
            actual_title = info.get("title", "").strip()

            # Atualizar no banco
            async with get_db_context() as session:
                repo = VideoRepository(session)
                await repo.complete_download(
                    video_id=video_id,
                    path=str(filename.relative_to(self.download_dir.parent)),
                    directory=str(download_dir.relative_to(self.download_dir.parent)),
                    filesize=filename.stat().st_size if filename.exists() else 0,
                    duration=duration,
                    resolution=actual_resolution,
                )
                # Corrige o título se ficou como fallback (Video_{id})
                if actual_title and actual_title != f"Video_{video_id}":
                    await repo.update(
                        video_id,
                        title=actual_title,
                        name=f"{actual_title}.mp4",
                    )

            # Storage strategy hook: upload to S3 if STORAGE_BACKEND=s3,
            # then optionally remove the local file. No-op for local backend.
            relative_path = str(filename.relative_to(self.download_dir.parent))
            await self._upload_to_storage_if_needed(video_id, filename, relative_path)

            # Atualizar mapeamento em memória
            self._add_video_mappings(filename, info, video_id)

            if sse_manager:
                await sse_manager.download_completed(
                    video_id, f"Download concluído: {filename.name}"
                )

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
        normalized = re.sub(r"[^\w\s]", " ", filename.lower())
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip().replace(" ", "_")
        return normalized

    def _add_video_mappings(self, filename: Path, info: dict, youtube_id: str) -> None:
        """Adiciona várias formas de ID ao mapeamento de vídeo."""
        title = info.get("title", "")

        video_mapping[youtube_id] = filename
        logger.debug(f"Mapeamento de vídeo adicionado: '{youtube_id}' -> {filename}")

        file_id = self._normalize_filename(filename.stem)
        video_mapping[file_id] = filename

        title_id = self._normalize_filename(title)
        if title_id and title_id != file_id:
            video_mapping[title_id] = filename

    def _execute_ydl_download(
        self, url: str, ydl_opts: dict, progress_data: dict, video_id: str, sse_manager
    ) -> dict:
        """Executa o download do yt-dlp em thread separada"""
        import threading
        import time

        stop_monitoring = threading.Event()

        def monitor_progress():
            last_progress = 0
            while not stop_monitoring.is_set():
                current_progress = progress_data.get("current_progress", 0)
                if current_progress != last_progress and current_progress > 0:
                    # Atualiza no banco de forma síncrona (em thread separada)
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            self._update_progress_async(video_id, current_progress)
                        )
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
                return {"info": info, "filename": original_filename}
        finally:
            stop_monitoring.set()
            monitor_thread.join(timeout=1)

    async def _update_progress_async(self, video_id: str, progress: int):
        """Atualiza o progresso no banco"""
        async with get_db_context() as session:
            repo = VideoRepository(session)
            await repo.update(video_id, download_progress=progress)

    async def _upload_to_storage_if_needed(
        self, video_id: str, local_filename: Path, relative_path: str
    ) -> None:
        """Upload the finished video to the active storage backend.

        Mirrors AudioDownloadManager._upload_to_storage_if_needed. See that
        method's docstring for the full semantics (H1 idempotency, H2 race
        protection, M3 error-channel rationale).
        """
        if STORAGE_BACKEND != "s3":
            return

        storage = get_storage()

        # H1: idempotency.
        async with get_db_context() as session:
            repo = VideoRepository(session)
            current = await repo.get_by_id(video_id)

        if current is not None and current.storage_backend == "s3" and current.s3_key:
            try:
                if await storage.exists(current.s3_key):
                    logger.info(
                        f"Video {video_id} already uploaded to s3://.../{current.s3_key}, "
                        f"skipping re-upload (idempotency)."
                    )
                    return
            except Exception as exists_err:
                logger.debug(
                    f"S3 exists() check failed for {current.s3_key}, "
                    f"proceeding with re-upload: {exists_err}"
                )

        try:
            s3_key = await storage.put_file(local_filename, relative_path)
        except Exception as upload_err:
            logger.error(
                f"S3 upload failed for video {video_id}: {upload_err}. "
                f"Row remains storage_backend='local'."
            )
            # M3: see audio counterpart for rationale.
            async with get_db_context() as session:
                repo = VideoRepository(session)
                await repo.update(
                    video_id,
                    download_error=f"S3 upload failed: {str(upload_err)[:480]}",
                )
            return

        # H2: detect concurrent delete via same-session re-fetch.
        async with get_db_context() as session:
            repo = VideoRepository(session)
            still_present = await repo.get_by_id(video_id)
            if still_present is None:
                logger.warning(
                    f"Video {video_id} row was deleted during S3 upload "
                    f"(orphan key={s3_key}). Best-effort S3 delete."
                )
                try:
                    await storage.delete(s3_key)
                except Exception as orphan_err:
                    logger.warning(
                        f"Orphan S3 cleanup failed for {s3_key}: {orphan_err}"
                    )
                return
            await repo.update(
                video_id,
                storage_backend="s3",
                s3_key=s3_key,
            )

        if S3_DELETE_LOCAL_AFTER_UPLOAD:
            try:
                if local_filename.exists():
                    local_filename.unlink()
                parent = local_filename.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                logger.info(f"Local copy removed for video {video_id} after S3 upload.")
            except Exception as cleanup_err:
                logger.warning(
                    f"Local cleanup failed for video {video_id}: {cleanup_err}"
                )

    async def delete_video(self, video_id: str) -> bool:
        """Exclui um vídeo do banco, S3 (se aplicável) e arquivos locais.

        M4: order is local FS -> DB row -> S3 (best-effort). See
        AudioDownloadManager.delete_audio for rationale.
        """
        try:
            logger.info(f"Iniciando exclusão do vídeo: {video_id}")

            video_info = await self.get_video_info(video_id)
            if not video_info:
                logger.warning(f"Vídeo não encontrado: {video_id}")
                return False

            # 1) Local filesystem cleanup.
            video_dir = self.download_dir / video_id
            if video_dir.exists() and video_dir.is_dir():
                shutil.rmtree(video_dir)
                logger.info(f"Diretório removido: {video_dir}")

            if video_id in video_mapping:
                del video_mapping[video_id]

            # 2) DB row removal.
            async with get_db_context() as session:
                repo = VideoRepository(session)
                result = await repo.delete(video_id)

            # 3) Best-effort S3 delete.
            if video_info.get("storage_backend") == "s3" and video_info.get("s3_key"):
                try:
                    storage = get_storage()
                    await storage.delete(video_info["s3_key"])
                except Exception as s3_err:
                    logger.warning(
                        f"S3 delete failed for {video_id} "
                        f"(DB+local already cleaned up): {s3_err}"
                    )

            logger.success(f"Vídeo excluído com sucesso: {video_id}")
            return result

        except Exception as e:
            logger.exception(f"Erro ao excluir vídeo {video_id}: {e}")
            raise

    async def update_transcription_status(
        self, video_id: str, status: str, transcription_path: str = None
    ) -> bool:
        """Atualiza o status de transcrição de um vídeo"""
        if status not in ["none", "queued", "started", "ended", "error"]:
            logger.warning(f"Status de transcrição inválido: {status}")
            return False

        async with get_db_context() as session:
            repo = VideoRepository(session)
            result = await repo.update_transcription_status(
                video_id, status, transcription_path
            )
            if result:
                logger.info(
                    f"Status da transcrição atualizado para '{status}' para vídeo {video_id}"
                )
                return True

        logger.warning(f"Vídeo não encontrado: {video_id}")
        return False

    # Design decision: playlist extraction lives on VideoDownloadManager (identical to
    # AudioDownloadManager.extract_playlist_info) because both managers need to extract
    # YouTube playlist metadata using the same yt-dlp flat-extract pattern. A shared
    # module-level helper is a future refactor opportunity (see TODO in AudioDownloadManager).
    async def extract_playlist_info(self, url: str) -> dict:
        """Extrai informações de uma playlist do YouTube sem baixar.

        Returns:
            {
                "title": str,
                "webpage_url": str,
                "entries": [{"id": str, "title": str, "url": str}, ...]
            }

        Raises ValueError if:
        - URL host is not in the YouTube allowlist
        - yt-dlp returns no information
        - URL yields no entries (e.g. single video URL)

        Runs yt-dlp in executor to avoid blocking the event loop.

        Also propagates yt-dlp exceptions (e.g. DownloadError) after logging.
        """
        # TODO(review): move import urllib.parse to module top-level - code-reviewer, 2026-04-28, Severity: Low
        import urllib.parse

        # NOTE: Playlist support is YouTube-only for v1. Instagram has no
        # native playlist concept that maps cleanly to yt-dlp's flat extractor.
        # Tracked as a non-goal in docs/plans/2026-05-13-instagram-support.md.
        # TODO(review): move _ALLOWED_HOSTS to module-level constant to avoid per-call allocation - code-reviewer, 2026-04-28, Severity: Low
        _ALLOWED_HOSTS = {
            "youtube.com",
            "www.youtube.com",
            "youtu.be",
            "music.youtube.com",
            "m.youtube.com",
        }

        parsed = urllib.parse.urlparse(str(url))
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Esquema de URL não suportado: {parsed.scheme!r}")
        if parsed.username or parsed.password:
            raise ValueError("URL com credenciais embutidas não é permitida.")
        host = parsed.hostname or ""
        if host not in _ALLOWED_HOSTS:
            raise ValueError(
                "Host da URL não está na lista permitida para extração de playlist."
            )

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "js_runtimes": YDL_JS_RUNTIMES,
            "remote_components": YDL_REMOTE_COMPONENTS,
            **get_yt_dlp_cookies_opts(),
        }

        def _extract():
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(str(url), download=False)

        logger.info(f"Extraindo informações de playlist: {url}")

        try:
            loop = asyncio.get_running_loop()
            info = await loop.run_in_executor(None, _extract)
        except Exception as exc:
            logger.error(
                "Erro ao extrair playlist '%s': %s", type(exc).__name__, str(exc)[:200]
            )
            raise

        if info is None:
            raise ValueError("yt-dlp não retornou informações para a URL fornecida.")

        entries_raw = info.get("entries") or []
        if not entries_raw:
            raise ValueError(
                "URL não parece ser uma playlist ou não retornou entradas."
            )

        entries = []
        for entry in entries_raw:
            if entry is None:
                continue
            video_id = entry.get("id") or ""
            if not video_id:
                logger.warning(
                    "Entrada de playlist sem ID ignorada: %s",
                    entry.get("title", "desconhecido"),
                )
                continue
            if not _YOUTUBE_ID_RE.match(video_id):
                logger.warning(
                    "Entrada de playlist com ID inválido ignorada: %s",
                    entry.get("title", "desconhecido"),
                )
                continue
            title = (
                entry.get("title") or entry.get("webpage_title") or f"Video_{video_id}"
            )
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            entries.append({"id": video_id, "title": title, "url": watch_url})

        if not entries:
            raise ValueError(
                "Nenhuma entrada com ID válido encontrada na playlist "
                "(todos os vídeos podem ser privados ou excluídos)."
            )

        logger.info(
            "Playlist '%s': %d entradas encontradas.",
            info.get("title") or "sem título",
            len(entries),
        )

        return {
            "title": info.get("title") or info.get("webpage_title") or "Playlist",
            "webpage_url": info.get("webpage_url") or str(url),
            "entries": entries,
        }
