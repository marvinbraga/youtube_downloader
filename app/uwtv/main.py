# main.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from loguru import logger
import uuid

# Configura logging antes de qualquer outro import
from app.core.logging import setup_logging

setup_logging(level="INFO")

from app.models.video import TokenData, ClientAuth, SortOption
from app.models.audio import (
    AudioDownloadRequest,
    VideoDownloadRequest,
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionProvider,
    PlaylistDownloadRequest,
    PlaylistTaskItem,
    PlaylistDownloadResponse,
)
from app.models.folder import (
    FolderCreate,
    FolderUpdate,
    FolderResponse,
    FolderTreeResponse,
    FolderWithItemsResponse,
    FolderPathResponse,
    MoveItemRequest,
    BulkMoveRequest,
    AlbumResponse,
    AlbumDetailResponse,
)
from app.services.configs import (
    video_mapping,
    AUDIO_DIR,
    audio_mapping,
    DOWNLOADS_DIR,
    TRANSCRIPTION_CONCURRENCY,
    DEFAULT_TRANSCRIPTION_PROVIDER,
    DEFAULT_TRANSCRIPTION_LANGUAGE,
)
from app.services.storage import (
    get_storage,
)  # L1: hoisted from per-endpoint lazy imports.
from app.services.files import (
    scan_video_directory,
    generate_video_stream,
    generate_audio_stream,
)
from app.services.managers import (
    VideoStreamManager,
    AudioDownloadManager,
    VideoDownloadManager,
)
from app.services.securities import (
    AUTHORIZED_CLIENTS,
    create_access_token,
    verify_token,
    verify_token_sync,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.services.transcription.service import TranscriptionService
from app.services.downloaders import is_playlist_url
from app.services.sse_manager import sse_manager
from app.services.download_queue import download_queue, DownloadTask
from app.db.database import init_db, migrate_json_to_sqlite, get_db_context
from app.db.models import Folder
from app.db.repositories import FolderRepository, AudioRepository, VideoRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    # Startup
    logger.info("Inicializando banco de dados SQLite...")
    await init_db()

    # Migrar dados do JSON se existirem
    logger.info("Verificando migração de dados JSON -> SQLite...")
    await migrate_json_to_sqlite()

    # Configurar callbacks da fila de downloads
    download_queue.on_download_started = on_download_started_callback
    download_queue.on_download_progress = on_download_progress_callback
    download_queue.on_download_completed = on_download_completed_callback
    download_queue.on_download_failed = on_download_failed_callback
    download_queue.on_download_cancelled = on_download_cancelled_callback

    # Validate cookie configuration at startup
    try:
        from app.services.configs import get_yt_dlp_cookies_opts

        get_yt_dlp_cookies_opts()
        logger.info("Cookie configuration validated successfully.")
    except ValueError as exc:
        logger.error(f"Invalid cookie configuration, cannot start: {exc}")
        raise RuntimeError(f"Invalid cookie configuration: {exc}") from exc

    # Validate storage configuration at startup
    try:
        from app.services.configs import validate_storage_config

        validate_storage_config()
        # Warm the storage cache: eager-init the singleton during startup so
        # the first request never races on the bare if-check in get_storage().
        storage = get_storage()
        logger.info(f"Storage configuration validated. Backend: {storage.backend_name}")
    except ValueError as exc:
        logger.error(f"Invalid storage configuration, cannot start: {exc}")
        raise RuntimeError(f"Invalid storage configuration: {exc}") from exc

    # Iniciar processamento da fila
    download_queue.start_processing()

    logger.info(
        f"Fila de transcrição: limite de {TRANSCRIPTION_CONCURRENCY} simultâneas"
    )

    # Recuperação de fila no startup: re-enfileira transcrições órfãs. O
    # _transcription_executor (módulo-level) já existe neste ponto e o banco já
    # foi inicializado/migrado acima — pré-requisitos para a recuperação.
    await recover_pending_transcriptions()

    logger.info("Aplicação iniciada com sucesso!")
    yield

    # Shutdown
    logger.info("Encerrando aplicação...")
    # Encerra o executor de transcrições sem bloquear o shutdown nem vazar
    # threads: cancela tarefas ainda enfileiradas e não aguarda as em execução.
    _transcription_executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="Video Streaming API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instâncias globais dos gerenciadores
stream_manager = VideoStreamManager()
audio_manager = AudioDownloadManager()
video_manager = VideoDownloadManager()

# Executor dedicado às transcrições. Limita quantas rodam em paralelo
# (TRANSCRIPTION_CONCURRENCY, default 2): apenas N workers existem, o restante
# das tarefas submetidas aguarda na fila interna do executor sem ocupar threads
# extras do pool padrão do Starlette. Isso evita o pico de memória que vinha
# matando o processo do servidor quando várias transcrições rodavam juntas.
_transcription_executor = ThreadPoolExecutor(
    max_workers=TRANSCRIPTION_CONCURRENCY,
    thread_name_prefix="transcribe",
)

MAX_PLAYLIST_ENTRIES = 200


# ---------------------------------------------------------------------------
# Núcleo reutilizável de enfileiramento de transcrição
# ---------------------------------------------------------------------------
#
# Tanto o endpoint POST /audio/transcribe quanto a recuperação de fila no
# startup precisam montar e submeter a MESMA tarefa de transcrição (resolução
# do caminho da mídia incl. S3 -> tempfile, checagem de cancelamento, escrita
# de status, submit ao executor dedicado). Para evitar duplicação, essa lógica
# vive em ``enqueue_transcription``. O endpoint mantém suas respostas HTTP
# (already-in-progress, already-ended, 404) inalteradas, mapeando o
# ``EnqueueOutcome`` retornado.


class EnqueueOutcome(str, Enum):
    """Resultado de uma tentativa de (re)enfileirar uma transcrição."""

    SUBMITTED = "submitted"  # tarefa submetida ao executor (status "queued")
    ALREADY_ENDED = "already_ended"  # já transcrito; nada a fazer (idempotente)
    IN_PROGRESS = "in_progress"  # já "queued"/"started"; não re-submeter
    NOT_FOUND = "not_found"  # arquivo/registro não encontrado


@dataclass
class EnqueueResult:
    """Retorno de ``enqueue_transcription``.

    ``transcription_file`` é o caminho .md resolvido (relativo a DOWNLOADS_DIR
    materializado em Path absoluto) quando aplicável — o endpoint o devolve ao
    cliente tal como antes.
    """

    outcome: EnqueueOutcome
    transcription_file: Optional[Path] = None
    detail: Optional[str] = None


async def _resolve_media_path(
    info: Dict[str, Any],
) -> Path:
    """Resolve o caminho local da mídia a partir do registro (áudio/vídeo).

    Para registros S3, materializa o objeto em um tempfile (o chamador é
    responsável por removê-lo após o uso — a closure de transcrição faz isso no
    ``finally``). Para registros locais, valida a existência em disco.
    """
    if info.get("storage_backend") == "s3" and info.get("s3_key"):
        storage = get_storage()
        media_path = await storage.download_to_temp(info["s3_key"])
        logger.info(
            f"Mídia S3 materializada em tempfile para transcrição: {media_path}"
        )
        return Path(media_path)
    media_path = DOWNLOADS_DIR / info["path"]
    if not media_path.exists():
        raise FileNotFoundError(str(media_path))
    return media_path


def _build_transcribe_task(
    *,
    audio_info: Optional[Dict[str, Any]],
    video_info: Optional[Dict[str, Any]],
    media_path: Path,
    media_is_tempfile: bool,
    transcription_file: Path,
    provider: str,
    language: str,
):
    """Monta a closure ``transcribe_task`` (mesma lógica do handler original).

    Parametriza ``provider``/``language`` para que a recuperação possa usar os
    defaults sem um pedido HTTP. O ciclo de status e a checagem de cancelamento
    (``_is_cancelled``) são preservados; o tempfile S3 é limpo no ``finally``.
    """
    _audio_info = audio_info
    _video_info = video_info
    _media_path = media_path
    _media_is_tempfile = media_is_tempfile

    def transcribe_task():
        def _is_cancelled() -> bool:
            """Re-lê o status corrente; se for 'none', considera cancelado.

            Fecha o caminho mais frequente da race em que o usuário pediu
            cancelamento (DELETE /audio/transcription/{id}) enquanto o worker
            estava executando. Ainda existe uma pequena janela entre este check
            e o write subsequente, mas ela é estreita o bastante para ser
            aceitável.
            """
            try:
                if _audio_info:
                    info = asyncio.run(audio_manager.get_audio_info(_audio_info["id"]))
                elif _video_info:
                    info = asyncio.run(video_manager.get_video_info(_video_info["id"]))
                else:
                    return False
                return (info or {}).get("transcription_status") == "none"
            except Exception:
                return False

        try:
            # Cancelamento de enfileiradas: se o usuário cancelou (status "none"
            # via DELETE /audio/transcription/{id}) enquanto a tarefa esperava na
            # fila do executor, abortar sem processar. O `finally` ainda roda e
            # limpa o tempfile S3, se houver.
            if _is_cancelled():
                logger.info(
                    "Transcrição cancelada enquanto enfileirada; abortando antes de iniciar."
                )
                return

            # Worker pegou a tarefa de fato: agora sim vira "started".
            if _audio_info:
                asyncio.run(
                    audio_manager.update_transcription_status(
                        _audio_info["id"], "started"
                    )
                )
            elif _video_info:
                asyncio.run(
                    video_manager.update_transcription_status(
                        _video_info["id"], "started"
                    )
                )

            resolved_provider = TranscriptionProvider(provider)

            docs = TranscriptionService.transcribe_audio(
                file_path=str(_media_path),
                provider=resolved_provider,
                language=language,
            )

            if docs:
                output_path = str(transcription_file)
                transcription_path = TranscriptionService.save_transcription(
                    docs, output_path
                )

                if _is_cancelled():
                    # Usuário cancelou enquanto o worker rodava — limpa o arquivo
                    # recém-escrito e não regrava o status.
                    try:
                        Path(transcription_path).unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning(
                            f"Cancelado: falha ao remover {transcription_path}: {e}"
                        )
                    logger.info(
                        f"Transcrição cancelada pelo usuário; arquivo removido: {transcription_path}"
                    )
                elif _audio_info:
                    rel_path = Path(transcription_path).relative_to(DOWNLOADS_DIR)
                    asyncio.run(
                        audio_manager.update_transcription_status(
                            _audio_info["id"], "ended", str(rel_path)
                        )
                    )
                    logger.success(f"Transcrição concluída: {output_path}")
                elif _video_info:
                    rel_path = Path(transcription_path).relative_to(DOWNLOADS_DIR)
                    asyncio.run(
                        video_manager.update_transcription_status(
                            _video_info["id"], "ended", str(rel_path)
                        )
                    )
                    logger.success(f"Transcrição concluída: {output_path}")
            else:
                if _is_cancelled():
                    logger.info(
                        "Transcrição cancelada pelo usuário (sem conteúdo gerado)"
                    )
                elif _audio_info:
                    asyncio.run(
                        audio_manager.update_transcription_status(
                            _audio_info["id"], "error"
                        )
                    )
                elif _video_info:
                    asyncio.run(
                        video_manager.update_transcription_status(
                            _video_info["id"], "error"
                        )
                    )
                if not _is_cancelled():
                    logger.error("Falha na transcrição: nenhum conteúdo gerado")
        except Exception as e:
            if _is_cancelled():
                logger.info(f"Transcrição cancelada pelo usuário (após erro): {e}")
            elif _audio_info:
                asyncio.run(
                    audio_manager.update_transcription_status(
                        _audio_info["id"], "error"
                    )
                )
                logger.exception(f"Erro na tarefa de transcrição: {str(e)}")
            elif _video_info:
                asyncio.run(
                    video_manager.update_transcription_status(
                        _video_info["id"], "error"
                    )
                )
                logger.exception(f"Erro na tarefa de transcrição: {str(e)}")
        finally:
            # Quando a mídia foi materializada do S3 em /tmp, remove o tempfile
            # após a transcrição terminar (sucesso OU erro).
            if _media_is_tempfile:
                try:
                    Path(_media_path).unlink(missing_ok=True)
                    logger.debug(f"Tempfile S3 removido: {_media_path}")
                except Exception as cleanup_err:
                    logger.warning(
                        f"Falha ao remover tempfile S3 {_media_path}: {cleanup_err}"
                    )

    return transcribe_task


async def enqueue_transcription(
    file_id: str,
    provider: str,
    language: str,
    *,
    is_video: bool = False,
    force: bool = False,
) -> EnqueueResult:
    """Resolve, prepara e submete a transcrição de ``file_id`` ao executor.

    Núcleo reutilizado pelo endpoint POST /audio/transcribe e pela recuperação
    de fila no startup. NÃO levanta HTTPException (pode rodar fora de um
    contexto HTTP) — sinaliza o resultado via ``EnqueueResult.outcome``.

    Comportamento:
      * Resolve o registro (áudio primeiro; depois vídeo). ``is_video`` é uma
        dica usada apenas pela recuperação, que já sabe a origem; o endpoint não
        a fornece e a resolução padrão (áudio→vídeo→busca) é mantida.
      * Idempotência: se já "ended" com arquivo presente -> ``ALREADY_ENDED``
        (vale mesmo com ``force=True``; nunca re-transcreve o que já terminou).
      * Se já "queued"/"started" -> ``IN_PROGRESS`` (o endpoint devolve
        "processing"). A recuperação no startup passa ``force=True`` para PULAR
        essa guarda: itens órfãos estão justamente em "queued"/"started", e sem
        o bypass o re-enfileiramento seria um no-op silencioso (a tarefa nunca
        chegaria ao ``submit``).
      * Caso contrário (ou ``force=True``): marca "queued", monta a task e
        submete ao executor; retorna ``SUBMITTED`` com o ``transcription_file``.
    """
    audio_info: Optional[Dict[str, Any]] = None
    video_info: Optional[Dict[str, Any]] = None
    media_path: Optional[Path] = None

    # Resolução do registro. ``is_video`` permite à recuperação pular direto
    # para o vídeo; o endpoint não passa a dica e mantém a ordem áudio->vídeo.
    if not is_video:
        audio_info = await audio_manager.get_audio_info(file_id)
    if audio_info is None:
        video_info = await video_manager.get_video_info(file_id)

    if audio_info:
        info = audio_info
    elif video_info:
        info = video_info
    else:
        info = None

    if info is not None:
        try:
            media_path = await _resolve_media_path(info)
        except FileNotFoundError as exc:
            # Preserva a mensagem por tipo (áudio/vídeo) do handler original.
            kind = "áudio" if audio_info else "vídeo"
            detail = f"Arquivo de {kind} não encontrado: {exc}"
            logger.error(detail)
            return EnqueueResult(EnqueueOutcome.NOT_FOUND, detail=detail)

        transcription_status = info.get("transcription_status", "none")

        if transcription_status == "ended" and info.get("transcription_path"):
            transcription_path = DOWNLOADS_DIR / info["transcription_path"]
            if transcription_path.exists():
                logger.info(f"Transcrição já existe: {transcription_path}")
                if info.get("storage_backend") == "s3" and media_path is not None:
                    _cleanup_tempfile(media_path)
                return EnqueueResult(
                    EnqueueOutcome.ALREADY_ENDED,
                    transcription_file=transcription_path,
                )
        elif transcription_status in ("started", "queued") and not force:
            logger.info(f"Transcrição já está em andamento para: {file_id}")
            if info.get("storage_backend") == "s3" and media_path is not None:
                _cleanup_tempfile(media_path)
            return EnqueueResult(EnqueueOutcome.IN_PROGRESS)
        elif transcription_status == "error":
            logger.warning("Erro anterior na transcrição. Tentando novamente.")
    else:
        # Sem registro: tenta localizar o arquivo por busca no disco local.
        try:
            media_path = await TranscriptionService.find_audio_file(file_id)
            logger.debug(f"Arquivo encontrado por busca: {media_path}")
        except FileNotFoundError:
            logger.error(f"Arquivo de áudio/vídeo não encontrado: '{file_id}'")
            return EnqueueResult(
                EnqueueOutcome.NOT_FOUND,
                detail=f"Arquivo de áudio/vídeo não encontrado: {file_id}",
            )

    if media_path is None:  # garantido pelos ramos acima; guarda explícita
        raise RuntimeError(f"media_path não resolvido para file_id={file_id}")

    # Caminho do .md derivado da coluna `path` do registro (sempre relativa a
    # DOWNLOADS_DIR), pois para registros S3 media_path é um /tmp/... e os
    # irmãos dele não ficam sob DOWNLOADS_DIR. Fallback (sem registro):
    # media_path é um arquivo real em disco sob DOWNLOADS_DIR.
    if audio_info and audio_info.get("path"):
        transcription_file = DOWNLOADS_DIR / Path(audio_info["path"]).with_suffix(".md")
    elif video_info and video_info.get("path"):
        transcription_file = DOWNLOADS_DIR / Path(video_info["path"]).with_suffix(".md")
    else:
        transcription_file = media_path.with_suffix(".md")

    media_is_tempfile = bool(
        (audio_info and audio_info.get("storage_backend") == "s3")
        or (video_info and video_info.get("storage_backend") == "s3")
    )

    if transcription_file.exists():
        logger.info(f"Transcrição já existe: {transcription_file}")
        if media_is_tempfile:
            _cleanup_tempfile(media_path)
        rel_path = str(transcription_file.relative_to(DOWNLOADS_DIR))
        if audio_info:
            await audio_manager.update_transcription_status(
                audio_info["id"], "ended", rel_path
            )
        elif video_info:
            await video_manager.update_transcription_status(
                video_info["id"], "ended", rel_path
            )
        return EnqueueResult(
            EnqueueOutcome.ALREADY_ENDED, transcription_file=transcription_file
        )

    # Garante o diretório de saída (o dir-pai da mídia pode ter sido limpo após
    # upload para S3).
    transcription_file.parent.mkdir(parents=True, exist_ok=True)

    # Enfileiramento: o item entra como "queued". O status só vira "started"
    # dentro de transcribe_task, quando um worker do executor pega a tarefa.
    if audio_info:
        await audio_manager.update_transcription_status(audio_info["id"], "queued")
    elif video_info:
        await video_manager.update_transcription_status(video_info["id"], "queued")

    transcribe_task = _build_transcribe_task(
        audio_info=audio_info,
        video_info=video_info,
        media_path=media_path,
        media_is_tempfile=media_is_tempfile,
        transcription_file=transcription_file,
        provider=provider,
        language=language,
    )

    # Submete ao executor dedicado. Se já houver TRANSCRIPTION_CONCURRENCY
    # transcrições rodando, esta aguarda na fila interna do executor.
    _transcription_executor.submit(transcribe_task)

    return EnqueueResult(
        EnqueueOutcome.SUBMITTED, transcription_file=transcription_file
    )


def _cleanup_tempfile(path: Path) -> None:
    """Remove um tempfile S3 best-effort, logando falhas sem propagar."""
    try:
        Path(path).unlink(missing_ok=True)
    except Exception as cleanup_err:
        logger.warning(f"Falha ao remover tempfile S3 {path}: {cleanup_err}")


# Estados de transcrição que ficam órfãos quando o servidor reinicia: a fila
# vivia só na memória do executor, então itens "queued" (esperando) e "started"
# (que estavam rodando) nunca mais progridem após um restart.
_PENDING_TRANSCRIPTION_STATES = ["queued", "started"]


async def recover_pending_transcriptions() -> int:
    """Re-enfileira transcrições órfãs no startup.

    Busca áudios E vídeos com ``transcription_status`` em ("queued","started").
    Para cada item:
      * Se estava "started" (estava rodando quando o servidor caiu), reseta para
        "queued" — o ciclo de status volta a queued -> started -> ended/error.
      * Chama ``enqueue_transcription`` com os defaults
        ``DEFAULT_TRANSCRIPTION_PROVIDER`` / ``DEFAULT_TRANSCRIPTION_LANGUAGE``
        (provider/idioma NÃO são persistidos por item).

    Idempotência: itens já "ended" não são selecionados pela query, e a própria
    ``enqueue_transcription`` retorna ``ALREADY_ENDED`` se o arquivo .md já
    existir, sem re-submeter. Erros são tratados por item — uma falha não aborta
    o startup nem impede a recuperação dos demais. Retorna quantos itens foram
    de fato re-submetidos.
    """
    provider = DEFAULT_TRANSCRIPTION_PROVIDER
    language = DEFAULT_TRANSCRIPTION_LANGUAGE

    try:
        async with get_db_context() as session:
            audio_repo = AudioRepository(session)
            video_repo = VideoRepository(session)
            pending_audios = await audio_repo.get_by_transcription_status(
                _PENDING_TRANSCRIPTION_STATES
            )
            pending_videos = await video_repo.get_by_transcription_status(
                _PENDING_TRANSCRIPTION_STATES
            )
            # Materializa apenas os campos necessários antes de fechar a sessão.
            audio_items = [(a.id, a.transcription_status) for a in pending_audios]
            video_items = [(v.id, v.transcription_status) for v in pending_videos]
    except Exception as exc:
        logger.exception(
            f"Recuperação de fila: falha ao listar transcrições pendentes: {exc}"
        )
        return 0

    total_pending = len(audio_items) + len(video_items)
    if total_pending == 0:
        logger.info("Recuperação de fila: nenhuma transcrição pendente encontrada.")
        return 0

    logger.info(
        f"Recuperação de fila: {total_pending} transcrição(ões) pendente(s) "
        f"encontrada(s) ({len(audio_items)} áudio, {len(video_items)} vídeo). "
        f"Usando defaults provider='{provider}', language='{language}'."
    )

    recovered = 0

    async def _recover_one(file_id: str, status: str, *, is_video: bool) -> None:
        nonlocal recovered
        kind = "vídeo" if is_video else "áudio"
        try:
            # started -> queued: o worker que rodava sumiu com o restart.
            if status == "started":
                if is_video:
                    await video_manager.update_transcription_status(file_id, "queued")
                else:
                    await audio_manager.update_transcription_status(file_id, "queued")
                logger.info(
                    f"Recuperação de fila: {kind} {file_id} resetado de 'started' "
                    f"para 'queued'."
                )

            # force=True: o item está em "queued"/"started" (é exatamente o que
            # define um órfão); sem o bypass da guarda in-progress o
            # re-enfileiramento seria um no-op silencioso.
            result = await enqueue_transcription(
                file_id,
                provider=provider,
                language=language,
                is_video=is_video,
                force=True,
            )
            if result.outcome is EnqueueOutcome.SUBMITTED:
                recovered += 1
                logger.info(
                    f"Recuperação de fila: {kind} {file_id} re-submetido ao executor."
                )
            else:
                logger.info(
                    f"Recuperação de fila: {kind} {file_id} pulado "
                    f"(outcome={result.outcome.value})."
                )
        except Exception as exc:
            logger.exception(
                f"Recuperação de fila: falha ao re-enfileirar {kind} {file_id}: {exc}"
            )

    for file_id, status in audio_items:
        await _recover_one(file_id, status, is_video=False)
    for file_id, status in video_items:
        await _recover_one(file_id, status, is_video=True)

    logger.info(
        f"Recuperação de fila: {recovered} transcrições re-enfileiradas no startup."
    )
    return recovered


# Callbacks da fila de downloads
async def on_download_started_callback(task: DownloadTask):
    await sse_manager.download_started(
        task.audio_id, f"Download iniciado na fila (posição: {task.priority})"
    )


async def on_download_progress_callback(task: DownloadTask, progress: int):
    await sse_manager.download_progress(task.audio_id, progress)


async def on_download_completed_callback(task: DownloadTask):
    await sse_manager.download_completed(task.audio_id, "Download concluído pela fila")


async def on_download_failed_callback(task: DownloadTask, error: str):
    await sse_manager.download_error(task.audio_id, error)


async def on_download_cancelled_callback(task: DownloadTask):
    await sse_manager.download_error(task.audio_id, "Download cancelado pelo usuário")


@app.post("/auth/token", response_model=TokenData)
async def login_for_access_token(client: ClientAuth):
    """Endpoint para autenticação do cliente"""
    if (
        client.client_id not in AUTHORIZED_CLIENTS
        or AUTHORIZED_CLIENTS[client.client_id]["secret"] != client.client_secret
    ):
        logger.error("Credenciais inválidas.")
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": client.client_id}, expires_delta=access_token_expires
    )

    result = {"access_token": access_token, "token_type": "bearer"}
    logger.debug(f"Credenciais: {result}")
    return result


@app.get("/videos")
async def list_videos(
    sort_by: SortOption = Query(SortOption.NONE),
    token_data: dict = Depends(verify_token),
):
    """Lista todos os vídeos (requer autenticação)"""
    logger.debug(f"Listando vídeos. Token: {token_data}")
    try:
        videos = scan_video_directory(sort_by)
        return {"videos": videos}
    except Exception as e:
        logger.error(f"Erro ao listar vídeos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar vídeos: {str(e)}")


@app.get("/video/list-downloads")
async def list_video_downloads(token_data: dict = Depends(verify_token)):
    """Lista todos os vídeos baixados"""
    try:
        logger.debug("Listando vídeos do banco de dados")

        videos = await video_manager.get_all_videos()

        logger.info(f"Encontrados {len(videos)} vídeos")
        return {"videos": videos}
    except Exception as e:
        logger.exception(f"Erro ao listar vídeos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar vídeos: {str(e)}")


@app.get("/video/{video_id}")
async def stream_video(video_id: str, token_data: dict = Depends(verify_token)):
    """Stream de vídeo (legacy mapping fast-path; falls back to DB for S3 rows)."""
    # L3: `video_mapping` is an in-memory dict populated by VideoDownloadManager
    # at download time. It's a fast path for the common case (local backend,
    # session-warm). When the lookup misses we fall through to the DB, which:
    #   (a) handles S3-backed rows (no mapping entry by design — we redirect),
    #   (b) handles process-restart cases (mapping is lost; DB is the source of
    #       truth), and
    #   (c) handles stale mappings pointing at a deleted/missing file.
    # Net effect: the mapping is a cache; the DB is the system of record.
    if video_id in video_mapping:
        video_source = video_mapping[video_id]

        if isinstance(video_source, str) and video_source.startswith("http"):
            logger.debug(f"Iniciando streaming do YouTube: {video_source}")
            return StreamingResponse(
                stream_manager.stream_youtube_video(video_source),
                media_type="video/mp4",
            )

        video_path = video_source
        content_types = {".mp4": "video/mp4", ".webm": "video/webm"}
        content_type = content_types.get(video_path.suffix.lower())
        if not content_type:
            logger.error("Formato de vídeo não suportado.")
            raise HTTPException(
                status_code=400, detail="Formato de vídeo não suportado"
            )
        return StreamingResponse(
            generate_video_stream(video_path), media_type=content_type
        )

    # Not in mapping — could be an S3-backed row. Look it up in the DB.
    video_info = await video_manager.get_video_info(video_id)
    if not video_info:
        video_info = await video_manager.get_video_by_youtube_id(video_id)
    if not video_info:
        logger.error("Vídeo não encontrado.")
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    backend = video_info.get("storage_backend", "local")
    if backend == "s3" and video_info.get("s3_key"):
        storage = get_storage()
        url = await storage.get_url(
            video_info["s3_key"], filename=video_info.get("name")
        )
        return RedirectResponse(url=url, status_code=302)

    # Local row that wasn't yet mapped — serve directly from disk.
    relative_path = video_info.get("path", "")
    video_path = DOWNLOADS_DIR / relative_path
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    content_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
    }
    content_type = content_types.get(video_path.suffix.lower(), "video/mp4")
    return StreamingResponse(generate_video_stream(video_path), media_type=content_type)


@app.get("/audios/{audio_id}/stream/")
async def stream_audio(audio_id: str, token_data: dict = Depends(verify_token)):
    """Streaming de áudio (legacy mapping fast-path; falls back to DB for S3 rows)."""
    try:
        logger.debug(f"Solicitado streaming do áudio: {audio_id}")

        # L3: `audio_mapping` is an in-memory cache populated by
        # AudioDownloadManager at download time. Same semantics as
        # `video_mapping` (see stream_video for the full note): a fast path
        # for local files in a warm process, with graceful fallback to the DB
        # for S3-backed rows, post-restart lookups, and stale-mapping cases.
        if audio_id in audio_mapping:
            audio_path = audio_mapping[audio_id]
            if audio_path.exists():
                content_type = "audio/mp4"
                suffix = audio_path.suffix.lower()
                if suffix == ".m4a":
                    content_type = "audio/mp4"
                elif suffix == ".mp3":
                    content_type = "audio/mpeg"
                elif suffix == ".wav":
                    content_type = "audio/wav"
                elif suffix == ".ogg":
                    content_type = "audio/ogg"
                logger.info(
                    f"Streaming áudio local {audio_id}: {audio_path} ({content_type})"
                )
                return StreamingResponse(
                    generate_audio_stream(audio_path), media_type=content_type
                )
            logger.warning(
                f"Mapeamento aponta para arquivo inexistente: {audio_path}; "
                f"caindo no DB para resolução."
            )

        # Not in mapping (or stale mapping) — look up in DB.
        audio_info = await audio_manager.get_audio_info(audio_id)
        if not audio_info:
            logger.warning(f"Áudio não encontrado no mapeamento nem no DB: {audio_id}")
            raise HTTPException(status_code=404, detail="Áudio não encontrado")

        backend = audio_info.get("storage_backend", "local")
        if backend == "s3" and audio_info.get("s3_key"):
            storage = get_storage()
            url = await storage.get_url(
                audio_info["s3_key"], filename=audio_info.get("name")
            )
            return RedirectResponse(url=url, status_code=302)

        # Local row, not in mapping (rare — should only happen if mapping
        # wasn't rebuilt after app restart). Serve from disk.
        audio_file_path = AUDIO_DIR.parent / audio_info["path"]
        if not audio_file_path.exists():
            raise HTTPException(
                status_code=404, detail="Arquivo de áudio não encontrado"
            )
        content_type = "audio/mp4"
        suffix = audio_file_path.suffix.lower()
        if suffix == ".mp3":
            content_type = "audio/mpeg"
        elif suffix == ".wav":
            content_type = "audio/wav"
        return StreamingResponse(
            generate_audio_stream(audio_file_path), media_type=content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao fazer streaming do áudio {audio_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao fazer streaming do áudio: {str(e)}",
        )


@app.get("/audio/check_exists")
async def check_audio_exists(
    youtube_url: str, token_data: dict = Depends(verify_token)
):
    """Verifica se um áudio de um vídeo do YouTube já foi baixado"""
    try:
        logger.info(f"Verificando se áudio já existe para URL: {youtube_url}")

        youtube_id = audio_manager.extract_youtube_id(youtube_url)

        if not youtube_id:
            logger.warning(
                f"Não foi possível extrair o ID do YouTube da URL: {youtube_url}"
            )
            return {"exists": False, "message": "URL inválida ou não reconhecida"}

        # Busca no banco de dados
        audio_info = await audio_manager.get_audio_by_youtube_id(youtube_id)

        if not audio_info:
            logger.info(f"Áudio com ID '{youtube_id}' não encontrado no sistema")
            return {"exists": False, "message": "Áudio não encontrado no sistema"}

        download_status = audio_info.get("download_status", "unknown")

        if download_status not in ["ready", "completed"]:
            logger.info(
                f"Áudio com ID '{youtube_id}' existe mas não foi baixado. Status: {download_status}"
            )
            return {
                "exists": False,
                "message": f"Áudio existe mas não foi baixado completamente (status: {download_status})",
                "audio_info": audio_info,
            }

        # Verifica se o arquivo existe
        if audio_info.get("path"):
            audio_file_path = AUDIO_DIR.parent / audio_info["path"]
            if not audio_file_path.exists():
                logger.warning(f"Arquivo não encontrado: {audio_file_path}")
                return {
                    "exists": False,
                    "message": "Áudio registrado mas arquivo não encontrado",
                    "audio_info": audio_info,
                }

            file_size = audio_file_path.stat().st_size
            if file_size == 0:
                logger.warning(f"Arquivo vazio: {audio_file_path}")
                return {
                    "exists": False,
                    "message": "Áudio existe mas o arquivo está vazio",
                    "audio_info": audio_info,
                }
        else:
            logger.warning("Áudio sem caminho definido")
            return {
                "exists": False,
                "message": "Áudio registrado mas caminho não definido",
                "audio_info": audio_info,
            }

        logger.info(f"Áudio com ID '{youtube_id}' já existe e foi baixado")
        return {
            "exists": True,
            "message": "Este áudio já foi baixado com sucesso",
            "audio_info": audio_info,
        }

    except Exception as e:
        logger.exception(f"Erro ao verificar existência do áudio: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao verificar existência do áudio: {str(e)}"
        )


@app.post("/audio/download")
async def download_audio(
    request: AudioDownloadRequest,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(verify_token),
):
    """Faz o download apenas do áudio de um vídeo do YouTube"""
    # Guarda fora do try: HTTPException é subclasse de Exception e seria
    # reembrulhada como 500 pelo handler abaixo se levantada dentro dele.
    if is_playlist_url(str(request.url)):
        raise HTTPException(
            status_code=400,
            detail=(
                "URL de playlist detectada. Use o endpoint POST /audio/playlist "
                "para baixar playlists."
            ),
        )

    try:
        logger.info(f"Solicitação de download de áudio: {request.url}")

        # Registra o áudio com status 'downloading'
        try:
            audio_id = await audio_manager.register_audio_for_download(str(request.url))
            logger.info(f"Áudio registrado com ID: {audio_id}")
        except Exception as e:
            logger.error(f"Erro ao registrar áudio: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Erro ao registrar áudio: {str(e)}"
            )

        # Adicionar à fila de downloads
        task_id = await download_queue.add_download(
            audio_id=audio_id,
            url=str(request.url),
            high_quality=request.high_quality,
            priority=0,
        )

        return {
            "status": "processando",
            "message": "O áudio foi registrado e adicionado à fila de downloads",
            "audio_id": audio_id,
            "task_id": task_id,
            "url": str(request.url),
        }
    except Exception as e:
        logger.exception(f"Erro ao iniciar download de áudio: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao iniciar download de áudio: {str(e)}"
        )


@app.post("/audio/playlist", response_model=PlaylistDownloadResponse)
async def download_audio_playlist(
    request: PlaylistDownloadRequest,
    token_data: dict = Depends(verify_token),
):
    try:
        logger.info(f"Audio playlist download requested: {request.url}")

        try:
            playlist_info = await audio_manager.extract_playlist_info(str(request.url))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        entries = playlist_info["entries"]
        playlist_title = playlist_info["title"]
        playlist_url = playlist_info["webpage_url"]
        cover_url = playlist_info.get("thumbnail")
        if not cover_url and entries:
            cover_url = f"https://i.ytimg.com/vi/{entries[0]['id']}/hqdefault.jpg"
        artist = playlist_info.get("uploader")
        external_playlist_id = playlist_info.get("playlist_id")

        if len(entries) > MAX_PLAYLIST_ENTRIES:
            raise HTTPException(
                status_code=400,
                detail=f"A playlist tem {len(entries)} itens; o máximo permitido é {MAX_PLAYLIST_ENTRIES}.",
            )

        logger.info(f"Playlist '{playlist_title}' found with {len(entries)} entries")

        async with get_db_context() as session:
            folder_repo = FolderRepository(session)
            folder = Folder(
                name=playlist_title[:255],
                description="Playlist",
                icon="playlist",
                kind="album",
                source_url=playlist_url,
                external_playlist_id=external_playlist_id,
                cover_url=cover_url,
                artist=(artist[:500] if artist else None),
            )
            created_folder = await folder_repo.create(folder)
            folder_id = created_folder.id

        logger.info(f"Album folder created: {folder_id} ('{playlist_title}')")

        tasks: List[PlaylistTaskItem] = []
        queued_count = 0
        skipped_count = 0
        failed_count = 0

        for track_number, entry in enumerate(entries, start=1):
            video_id = entry["id"]
            title = entry["title"]
            watch_url = entry["url"]

            existing = await audio_manager.get_audio_by_youtube_id(video_id)
            already_exists = existing is not None and existing.get(
                "download_status", ""
            ) not in ("error", "")

            if already_exists and request.skip_existing:
                async with get_db_context() as session:
                    repo = AudioRepository(session)
                    update_kwargs = {"track_number": track_number}
                    if existing.get("folder_id") is None:
                        update_kwargs["folder_id"] = folder_id
                    await repo.update(existing["id"], **update_kwargs)

                tasks.append(
                    PlaylistTaskItem(
                        item_id=existing["id"],
                        youtube_id=video_id,
                        item_type="audio",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=True,
                    )
                )
                skipped_count += 1
                logger.debug(f"Skipped existing audio: {video_id}")
                continue

            try:
                audio_id = await audio_manager.register_audio_for_download(watch_url)
            except Exception as reg_err:
                logger.error("Failed to register {}: {}", video_id, str(reg_err)[:200])
                tasks.append(
                    PlaylistTaskItem(
                        item_id=None,
                        youtube_id=video_id,
                        item_type="audio",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=False,
                    )
                )
                failed_count += 1
                continue

            try:
                async with get_db_context() as session:
                    repo = AudioRepository(session)
                    await repo.update(
                        audio_id, folder_id=folder_id, track_number=track_number
                    )

                task_id = await download_queue.add_download(
                    audio_id=audio_id,
                    url=watch_url,
                    high_quality=request.high_quality,
                    priority=0,
                )

                tasks.append(
                    PlaylistTaskItem(
                        item_id=audio_id,
                        youtube_id=video_id,
                        item_type="audio",
                        task_id=task_id,
                        title=title,
                        url=watch_url,
                        skipped=False,
                    )
                )
                queued_count += 1
            except Exception as post_err:
                logger.error(
                    "Post-registration failure for {}: {}",
                    video_id,
                    str(post_err)[:200],
                )
                try:
                    async with get_db_context() as session:
                        repo = AudioRepository(session)
                        await repo.update_download_status(audio_id, "error")
                except Exception:
                    pass
                tasks.append(
                    PlaylistTaskItem(
                        item_id=None,
                        youtube_id=video_id,
                        item_type="audio",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=False,
                    )
                )
                failed_count += 1

        logger.info(
            f"Playlist '{playlist_title}': {queued_count} queued, "
            f"{skipped_count} skipped, folder={folder_id}"
        )

        return PlaylistDownloadResponse(
            playlist_title=playlist_title,
            playlist_url=playlist_url,
            folder_id=folder_id,
            total_items=len(entries),
            queued_items=queued_count,
            skipped_items=skipped_count,
            failed_items=failed_count,
            tasks=tasks,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error processing audio playlist: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar a playlist. Verifique os logs do servidor.",
        )


@app.post("/video/download")
async def download_video(
    request: VideoDownloadRequest,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(verify_token),
):
    """Faz o download de um vídeo do YouTube"""
    try:
        logger.info(
            f"Solicitação de download de vídeo: {request.url} (resolução: {request.resolution})"
        )

        # Registra o vídeo com status 'downloading'
        try:
            video_id = await video_manager.register_video_for_download(
                str(request.url), resolution=request.resolution
            )
            logger.info(f"Vídeo registrado com ID: {video_id}")
        except Exception as e:
            logger.error(f"Erro ao registrar vídeo: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Erro ao registrar vídeo: {str(e)}"
            )

        # Inicia o download em background
        background_tasks.add_task(
            video_manager.download_video_with_status_async,
            video_id,
            str(request.url),
            request.resolution,
            sse_manager,
        )

        return {
            "status": "processando",
            "message": "O vídeo foi registrado e o download foi iniciado",
            "video_id": video_id,
            "resolution": request.resolution,
            "url": str(request.url),
        }
    except Exception as e:
        logger.exception(f"Erro ao iniciar download de vídeo: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao iniciar download de vídeo: {str(e)}"
        )


@app.post("/video/playlist", response_model=PlaylistDownloadResponse)
async def download_video_playlist(
    request: PlaylistDownloadRequest,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(verify_token),
):
    try:
        logger.info(f"Video playlist download requested: {request.url}")

        try:
            playlist_info = await video_manager.extract_playlist_info(str(request.url))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        entries = playlist_info["entries"]
        playlist_title = playlist_info["title"]
        playlist_url = playlist_info["webpage_url"]
        cover_url = playlist_info.get("thumbnail")
        if not cover_url and entries:
            cover_url = f"https://i.ytimg.com/vi/{entries[0]['id']}/hqdefault.jpg"
        artist = playlist_info.get("uploader")
        external_playlist_id = playlist_info.get("playlist_id")

        if len(entries) > MAX_PLAYLIST_ENTRIES:
            raise HTTPException(
                status_code=400,
                detail=f"A playlist tem {len(entries)} itens; o máximo permitido é {MAX_PLAYLIST_ENTRIES}.",
            )

        logger.info(
            f"Video playlist '{playlist_title}' found with {len(entries)} entries"
        )

        async with get_db_context() as session:
            folder_repo = FolderRepository(session)
            folder = Folder(
                name=playlist_title[:255],
                description="Playlist",
                icon="playlist",
                kind="playlist",
                source_url=playlist_url,
                external_playlist_id=external_playlist_id,
                cover_url=cover_url,
                artist=(artist[:500] if artist else None),
            )
            created_folder = await folder_repo.create(folder)
            folder_id = created_folder.id

        logger.info(f"Video playlist folder created: {folder_id} ('{playlist_title}')")

        tasks: List[PlaylistTaskItem] = []
        to_download: List[dict] = []
        skipped_count = 0
        failed_count = 0

        for entry in entries:
            video_id = entry["id"]
            title = entry["title"]
            watch_url = entry["url"]

            existing = await video_manager.get_video_by_youtube_id(video_id)
            already_exists = existing is not None and existing.get(
                "download_status", ""
            ) not in ("error", "")

            if already_exists and request.skip_existing:
                if existing.get("folder_id") is None:
                    async with get_db_context() as session:
                        repo = VideoRepository(session)
                        await repo.update_folder(existing["id"], folder_id)

                tasks.append(
                    PlaylistTaskItem(
                        item_id=existing["id"],
                        youtube_id=video_id,
                        item_type="video",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=True,
                    )
                )
                skipped_count += 1
                logger.debug(f"Skipped existing video: {video_id}")
                continue

            try:
                registered_id = await video_manager.register_video_for_download(
                    watch_url, resolution=request.resolution
                )
            except Exception as reg_err:
                logger.error(
                    "Failed to register video {}: {}", video_id, str(reg_err)[:200]
                )
                tasks.append(
                    PlaylistTaskItem(
                        item_id=None,
                        youtube_id=video_id,
                        item_type="video",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=False,
                    )
                )
                failed_count += 1
                continue

            try:
                async with get_db_context() as session:
                    repo = VideoRepository(session)
                    await repo.update_folder(registered_id, folder_id)

                tasks.append(
                    PlaylistTaskItem(
                        item_id=registered_id,
                        youtube_id=video_id,
                        item_type="video",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=False,
                    )
                )
                to_download.append(
                    {
                        "video_id": registered_id,
                        "url": watch_url,
                        "resolution": request.resolution,
                    }
                )
            except Exception as post_err:
                logger.error(
                    "Post-registration failure for video {}: {}",
                    video_id,
                    str(post_err)[:200],
                )
                try:
                    async with get_db_context() as session:
                        repo = VideoRepository(session)
                        await repo.update_download_status(registered_id, "error")
                except Exception:
                    pass
                tasks.append(
                    PlaylistTaskItem(
                        item_id=None,
                        youtube_id=video_id,
                        item_type="video",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=False,
                    )
                )
                failed_count += 1

        queued_count = len(to_download)

        async def _download_playlist_serially(items: list):
            for item in items:
                try:
                    await video_manager.download_video_with_status_async(
                        item["video_id"],
                        item["url"],
                        resolution=item["resolution"],
                        sse_manager=sse_manager,
                    )
                    logger.success(f"Playlist video done: {item['video_id']}")
                except Exception as exc:
                    logger.error(
                        "Playlist video failed: {} — {}",
                        item["video_id"],
                        str(exc)[:200],
                    )

        if to_download:
            background_tasks.add_task(_download_playlist_serially, to_download)

        logger.info(
            f"Video playlist '{playlist_title}': {queued_count} scheduled, "
            f"{skipped_count} skipped, folder={folder_id}"
        )

        return PlaylistDownloadResponse(
            playlist_title=playlist_title,
            playlist_url=playlist_url,
            folder_id=folder_id,
            total_items=len(entries),
            queued_items=queued_count,
            skipped_items=skipped_count,
            failed_items=failed_count,
            tasks=tasks,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error processing video playlist: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar a playlist. Verifique os logs do servidor.",
        )


@app.get("/video/download-status/{video_id}")
async def get_video_download_status(
    video_id: str, token_data: dict = Depends(verify_token)
):
    """Obtém o status de download de um vídeo"""
    try:
        video_info = await video_manager.get_video_info(video_id)

        if not video_info:
            raise HTTPException(
                status_code=404, detail=f"Vídeo não encontrado: {video_id}"
            )

        return {
            "video_id": video_id,
            "download_status": video_info.get("download_status", "unknown"),
            "download_progress": video_info.get("download_progress", 0),
            "download_error": video_info.get("download_error", ""),
            "resolution": video_info.get("resolution", ""),
            "duration": video_info.get("duration"),
            "filesize": video_info.get("filesize", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter status de download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter status: {str(e)}")


@app.get("/video/stream/{video_id}")
async def stream_downloaded_video(
    video_id: str, token_data: dict = Depends(verify_token)
):
    """Streaming de vídeo baixado (local) ou redirect para S3 presigned."""
    try:
        logger.debug(f"Solicitado streaming do vídeo: {video_id}")

        video_info = await video_manager.get_video_by_youtube_id(video_id)
        if not video_info:
            # Fallback: maybe the path param is the row id, not the YouTube id.
            video_info = await video_manager.get_video_info(video_id)

        if not video_info:
            logger.warning(f"Vídeo não encontrado: {video_id}")
            raise HTTPException(status_code=404, detail="Vídeo não encontrado")

        if video_info.get("download_status") != "ready":
            logger.warning(f"Vídeo ainda não está pronto: {video_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Vídeo ainda não está pronto. Status: {video_info.get('download_status')}",
            )

        backend = video_info.get("storage_backend", "local")

        if backend == "s3":
            s3_key = video_info.get("s3_key")
            if not s3_key:
                logger.error(f"S3 row sem s3_key: {video_id}")
                raise HTTPException(status_code=500, detail="Row S3 sem s3_key")
            storage = get_storage()
            url = await storage.get_url(s3_key, filename=video_info.get("name"))
            logger.info(f"Redirecting video {video_id} to S3 presigned URL")
            return RedirectResponse(url=url, status_code=302)

        # Local backend (legacy behavior)
        relative_path = video_info.get("path", "")
        video_path = DOWNLOADS_DIR / relative_path

        if not video_path.exists():
            logger.error(f"Arquivo de vídeo não encontrado: {video_path}")
            raise HTTPException(
                status_code=404, detail="Arquivo de vídeo não encontrado"
            )

        content_types = {
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
        }
        content_type = content_types.get(video_path.suffix.lower(), "video/mp4")

        logger.info(f"Iniciando streaming local do vídeo: {video_path}")
        return StreamingResponse(
            generate_video_stream(video_path), media_type=content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao fazer streaming do vídeo {video_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao fazer streaming do vídeo: {str(e)}",
        )


@app.get("/audio/list")
async def list_audio_files(token_data: dict = Depends(verify_token)):
    """Lista todos os arquivos de áudio disponíveis"""
    try:
        logger.debug("Listando arquivos de áudio do banco de dados")

        # Usa o gerenciador que agora consulta o SQLite
        audio_files = await audio_manager.get_all_audios()

        logger.info(f"Encontrados {len(audio_files)} arquivos de áudio")
        return {"audio_files": audio_files}
    except Exception as e:
        logger.exception(f"Erro ao listar arquivos de áudio: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao listar arquivos de áudio: {str(e)}"
        )


@app.post("/audio/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    request: TranscriptionRequest,
    token_data: dict = Depends(verify_token),
):
    """Transcreve um arquivo de áudio ou vídeo.

    Delegação fina ao núcleo reutilizável ``enqueue_transcription`` — o mesmo
    usado pela recuperação de fila no startup. As respostas HTTP (processing,
    success, 404) são preservadas exatamente como antes.
    """
    try:
        logger.info(f"Solicitação de transcrição para arquivo ID: '{request.file_id}'")

        result = await enqueue_transcription(
            request.file_id,
            provider=request.provider.value,
            language=request.language,
        )

        if result.outcome is EnqueueOutcome.NOT_FOUND:
            raise HTTPException(
                status_code=404,
                detail=result.detail
                or f"Arquivo de áudio/vídeo não encontrado: {request.file_id}",
            )

        if result.outcome is EnqueueOutcome.IN_PROGRESS:
            return TranscriptionResponse(
                file_id=request.file_id,
                transcription_path="",
                status="processing",
                message="A transcrição já está em andamento",
            )

        if result.outcome is EnqueueOutcome.ALREADY_ENDED:
            return TranscriptionResponse(
                file_id=request.file_id,
                transcription_path=str(result.transcription_file),
                status="success",
                message="Transcrição já existe",
            )

        # SUBMITTED
        return TranscriptionResponse(
            file_id=request.file_id,
            transcription_path=str(result.transcription_file),
            status="processing",
            message="A transcrição foi enfileirada",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao iniciar transcrição: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao iniciar transcrição: {str(e)}"
        )


@app.get("/audio/transcription/{file_id}")
async def get_transcription(file_id: str, token_data: dict = Depends(verify_token)):
    """Obtém o arquivo de transcrição"""
    try:
        logger.info(f"Solicitação de obtenção de transcrição para ID: {file_id}")

        audio_info = await audio_manager.get_audio_info(file_id)

        if audio_info and audio_info.get("transcription_status") == "ended":
            transcription_path = DOWNLOADS_DIR / audio_info["transcription_path"]

            if transcription_path.exists():
                logger.debug(f"Transcrição encontrada: {transcription_path}")
                return FileResponse(
                    path=transcription_path,
                    media_type="text/markdown",
                    filename=transcription_path.name,
                )
            else:
                logger.warning(
                    f"Caminho de transcrição não existe: {transcription_path}"
                )

        # C1 fix: also try video_info before falling back to find_audio_file (which,
        # for S3-backed rows, downloads to /tmp and would produce a /tmp/.md path
        # that never matches the deterministic on-disk transcript location).
        video_info = await video_manager.get_video_info(file_id)
        if video_info and video_info.get("transcription_status") == "ended":
            transcription_path = DOWNLOADS_DIR / video_info["transcription_path"]
            if transcription_path.exists():
                logger.debug(f"Transcrição encontrada: {transcription_path}")
                return FileResponse(
                    path=transcription_path,
                    media_type="text/markdown",
                    filename=transcription_path.name,
                )

        try:
            audio_file = await TranscriptionService.find_audio_file(file_id)
            # C1 fix: derive transcript path from the row's `path` column when available
            # (deterministic under DOWNLOADS_DIR). Only fall back to `audio_file.with_suffix`
            # when there's no row — that branch is local-only (find_audio_file scanned disk).
            media_is_tempfile = False
            if audio_info and audio_info.get("path"):
                transcription_file = DOWNLOADS_DIR / Path(
                    audio_info["path"]
                ).with_suffix(".md")
                if audio_info.get("storage_backend") == "s3":
                    media_is_tempfile = True
            elif video_info and video_info.get("path"):
                transcription_file = DOWNLOADS_DIR / Path(
                    video_info["path"]
                ).with_suffix(".md")
                if video_info.get("storage_backend") == "s3":
                    media_is_tempfile = True
            else:
                transcription_file = audio_file.with_suffix(".md")

            # M1 fix: if find_audio_file pulled the media from S3 into /tmp, clean
            # up immediately — the media file is not needed by this endpoint, only
            # the (already-on-disk) transcript is read below.
            if media_is_tempfile:
                try:
                    Path(audio_file).unlink(missing_ok=True)
                except Exception as cleanup_err:
                    logger.warning(
                        f"Falha ao remover tempfile S3 {audio_file}: {cleanup_err}"
                    )

            if not transcription_file.exists():
                logger.error(f"Transcrição não encontrada para: {file_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Transcrição não encontrada para: {file_id}",
                )

            logger.debug(f"Transcrição encontrada: {transcription_file}")

            if audio_info and audio_info.get("transcription_status") != "ended":
                rel_path = str(transcription_file.relative_to(DOWNLOADS_DIR))
                await audio_manager.update_transcription_status(
                    audio_info["id"], "ended", rel_path
                )

        except FileNotFoundError:
            transcription_files = list(AUDIO_DIR.glob("**/*.md"))

            matching_transcriptions = []
            for tf in transcription_files:
                if TranscriptionService.calculate_similarity(file_id, tf.stem) > 0.3:
                    matching_transcriptions.append(tf)

            if not matching_transcriptions:
                logger.error(f"Arquivo não encontrado: {file_id}")
                raise HTTPException(
                    status_code=404, detail=f"Arquivo não encontrado: {file_id}"
                )

            transcription_file = matching_transcriptions[0]
            logger.debug(f"Transcrição encontrada por busca: {transcription_file}")

            if audio_info:
                rel_path = str(transcription_file.relative_to(DOWNLOADS_DIR))
                await audio_manager.update_transcription_status(
                    audio_info["id"], "ended", rel_path
                )

        return FileResponse(
            path=transcription_file,
            media_type="text/markdown",
            filename=transcription_file.name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter transcrição: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter transcrição: {str(e)}"
        )


@app.get("/audio/stream/{audio_id}")
async def stream_audio_file(audio_id: str, token: str = Query(None)):
    """Servir áudio (local FileResponse) ou redirect para S3 presigned."""
    try:
        if token:
            try:
                verify_token_sync(token)
            except Exception as e:
                logger.warning(f"Token inválido: {str(e)}")
                raise HTTPException(status_code=403, detail="Token inválido")

        logger.debug(f"Solicitado stream do áudio: {audio_id}")

        audio = await audio_manager.get_audio_info(audio_id)
        if not audio:
            logger.warning(f"Áudio não encontrado: {audio_id}")
            raise HTTPException(status_code=404, detail="Áudio não encontrado")

        backend = audio.get("storage_backend", "local")

        if backend == "s3":
            s3_key = audio.get("s3_key")
            if not s3_key:
                logger.error(f"S3 row sem s3_key: {audio_id}")
                raise HTTPException(status_code=500, detail="Row S3 sem s3_key")
            storage = get_storage()
            url = await storage.get_url(s3_key, filename=audio.get("name"))
            logger.info(f"Redirecting audio {audio_id} to S3 presigned URL")
            return RedirectResponse(url=url, status_code=302)

        # Local backend
        audio_file_path = AUDIO_DIR.parent / audio["path"]
        if not audio_file_path.exists():
            logger.warning(f"Arquivo não encontrado: {audio_file_path}")
            raise HTTPException(
                status_code=404, detail="Arquivo de áudio não encontrado"
            )

        content_type = "audio/mp4"
        if audio_file_path.suffix.lower() == ".m4a":
            content_type = "audio/mp4"
        elif audio_file_path.suffix.lower() == ".mp3":
            content_type = "audio/mpeg"
        elif audio_file_path.suffix.lower() == ".wav":
            content_type = "audio/wav"

        logger.info(
            f"Servindo áudio local {audio_id}: {audio_file_path} ({content_type})"
        )
        return FileResponse(
            path=str(audio_file_path),
            media_type=content_type,
            filename=f"{audio['name']}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao servir áudio {audio_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao servir áudio: {str(e)}")


@app.get("/audio/transcription_status/{file_id}")
async def get_transcription_status(
    file_id: str, token_data: dict = Depends(verify_token)
):
    """Obtém o status atual da transcrição de áudio ou vídeo"""
    try:
        logger.info(f"Solicitação de status de transcrição para ID: {file_id}")

        # Primeiro tenta buscar como áudio
        audio_info = await audio_manager.get_audio_info(file_id)
        media_info = None
        media_type = None

        if audio_info:
            media_info = audio_info
            media_type = "audio"
        else:
            # Se não encontrou como áudio, tenta como vídeo
            video_info = await video_manager.get_video_info(file_id)
            if video_info:
                media_info = video_info
                media_type = "video"

        if not media_info:
            logger.warning(f"Áudio/vídeo não encontrado: {file_id}")
            raise HTTPException(
                status_code=404, detail=f"Áudio/vídeo não encontrado: {file_id}"
            )

        transcription_status = media_info.get("transcription_status", "none")

        transcription_path = None
        if transcription_status == "ended" and media_info.get("transcription_path"):
            transcription_path = media_info["transcription_path"]

        return {
            "file_id": file_id,
            "status": transcription_status,
            "transcription_path": transcription_path,
            "media_type": media_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter status da transcrição: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter status da transcrição: {str(e)}"
        )


@app.delete("/audio/transcription/{file_id}")
async def delete_transcription(file_id: str, token_data: dict = Depends(verify_token)):
    """Exclui ou cancela a transcrição de um áudio.

    Aceita qualquer status diferente de "none" — permite limpar transcrições
    travadas em "started" (processo morto sem finalizar) ou em "error".
    """
    try:
        logger.info(f"Solicitação de exclusão de transcrição para ID: {file_id}")

        audio_info = await audio_manager.get_audio_info(file_id)

        if not audio_info:
            logger.warning(f"Áudio não encontrado: {file_id}")
            raise HTTPException(
                status_code=404, detail=f"Áudio não encontrado: {file_id}"
            )

        transcription_status = audio_info.get("transcription_status", "none")
        transcription_path = audio_info.get("transcription_path")

        if transcription_status == "none":
            logger.warning(f"Sem transcrição para excluir: {file_id}")
            raise HTTPException(
                status_code=404, detail=f"Transcrição não encontrada para: {file_id}"
            )

        if transcription_path:
            full_path = AUDIO_DIR.parent / transcription_path
            if full_path.exists():
                full_path.unlink()
                logger.info(f"Arquivo de transcrição removido: {full_path}")
            else:
                logger.warning(f"Arquivo de transcrição não existe: {full_path}")

        # Reseta o status (passa string vazia porque a coluna é NOT NULL)
        await audio_manager.update_transcription_status(file_id, "none", "")

        action = (
            "cancelada" if transcription_status in ("started", "queued") else "excluída"
        )
        logger.success(f"Transcrição {action} com sucesso para: {file_id}")

        return {
            "status": "success",
            "message": f"Transcrição {action} com sucesso",
            "file_id": file_id,
            "previous_status": transcription_status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao excluir transcrição: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao excluir transcrição: {str(e)}"
        )


# Busca em transcrições

# Cap defensivo: arquivos maiores que isso são pulados na busca de conteúdo.
# Transcrições reais raramente passam de 1-2 MB; 5 MB cobre folga e evita
# que um .md corrompido ou anômalo carregue muita RAM por requisição.
MAX_TRANSCRIPTION_SEARCH_BYTES = 5 * 1024 * 1024
MAX_TRANSCRIPTION_SEARCH_RESULTS = 100
SNIPPET_RADIUS = 80


def _build_snippet(text: str, term_lower: str, term_len: int) -> tuple[str, int]:
    """Conta ocorrências e devolve snippet HTML-escapado com <mark> ao redor
    da primeira ocorrência (case-insensitive).
    """
    import html as _html

    lower = text.lower()
    count = lower.count(term_lower)
    if count == 0:
        return "", 0

    idx = lower.find(term_lower)
    start = max(0, idx - SNIPPET_RADIUS)
    end = min(len(text), idx + term_len + SNIPPET_RADIUS)
    before = _html.escape(text[start:idx])
    match = _html.escape(text[idx : idx + term_len])
    after = _html.escape(text[idx + term_len : end])
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    snippet = f"{prefix}{before}<mark>{match}</mark>{after}{suffix}"
    return snippet, count


@app.get("/transcription/search")
async def search_transcriptions(
    q: str = Query(..., min_length=2, max_length=200, description="Termo de busca"),
    kind: str = Query(
        "all", regex="^(all|audio|video)$", description="Filtrar por tipo de mídia"
    ),
    token_data: dict = Depends(verify_token),
):
    """Busca dentro do conteúdo dos arquivos de transcrição (.md).

    Itera sobre áudios e vídeos com transcrição concluída e procura ``q``
    case-insensitive no texto. Retorna até 100 resultados com snippet curto.
    """
    try:
        term = q.strip()
        if len(term) < 2:
            raise HTTPException(
                status_code=400,
                detail="Termo de busca muito curto (mínimo 2 caracteres)",
            )
        term_lower = term.lower()
        term_len = len(term)

        results: list[dict] = []
        scanned = 0

        async def _scan(items: list, media_type: str) -> None:
            nonlocal scanned
            for item in items:
                file_id = item.get("id")
                if not file_id:
                    continue
                status = item.get("transcription_status")
                rel_path = item.get("transcription_path")
                if status != "ended" or not rel_path:
                    continue
                full_path = DOWNLOADS_DIR / rel_path
                try:
                    if not full_path.exists() or not full_path.is_file():
                        continue
                    size = full_path.stat().st_size
                    if size > MAX_TRANSCRIPTION_SEARCH_BYTES:
                        logger.warning(
                            f"Transcrição {full_path} excede {MAX_TRANSCRIPTION_SEARCH_BYTES} bytes; pulando"
                        )
                        continue
                    text = await asyncio.to_thread(
                        full_path.read_text, encoding="utf-8", errors="replace"
                    )
                    scanned += 1
                except OSError as e:
                    logger.warning(f"Falha ao ler transcrição {full_path}: {e}")
                    continue

                snippet, count = _build_snippet(text, term_lower, term_len)
                if count == 0:
                    continue
                results.append(
                    {
                        "file_id": file_id,
                        "media_type": media_type,
                        "title": item.get("title") or item.get("name") or "",
                        "snippet": snippet,
                        "match_count": count,
                    }
                )

        # Coleta de TODOS os matches em ambos os tipos antes do sort/cap, para
        # evitar o viés audio-first que esconderia matches de vídeo quando
        # áudios sozinhos já fossem suficientes para preencher o cap.
        if kind in ("all", "audio"):
            audios = await audio_manager.get_all_audios()
            await _scan(audios, "audio")
        if kind in ("all", "video"):
            videos = await video_manager.get_all_videos()
            await _scan(videos, "video")

        total_matches = len(results)
        results.sort(key=lambda r: r["match_count"], reverse=True)
        truncated = total_matches > MAX_TRANSCRIPTION_SEARCH_RESULTS
        if truncated:
            results = results[:MAX_TRANSCRIPTION_SEARCH_RESULTS]

        logger.info(
            f"Busca em transcrições: q='{term}' kind={kind} scanned={scanned} "
            f"matches={total_matches} truncated={truncated}"
        )

        return {
            "query": term,
            "kind": kind,
            "scanned": scanned,
            "truncated": truncated,
            "total_matches": total_matches,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro na busca de transcrições: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na busca: {e}")


# SSE e status de download


@app.get("/audio/download-events")
async def download_events_stream(
    token: str = Query(None, description="Token de autenticação"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """Stream de eventos SSE para atualizações de download"""
    auth_token = None
    if authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:]
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(status_code=403, detail="Token de autenticação necessário")

    try:
        verify_token_sync(auth_token)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Token inválido")

    client_id = str(uuid.uuid4())

    async def event_generator():
        try:
            queue = await sse_manager.connect(client_id)

            while True:
                event_data = await queue.get()
                yield event_data

        except asyncio.CancelledError:
            logger.info(f"Stream SSE cancelado para cliente {client_id}")
        finally:
            sse_manager.disconnect(client_id)

    return EventSourceResponse(event_generator())


@app.get("/audio/download-status/{audio_id}")
async def get_download_status(audio_id: str, token_data: dict = Depends(verify_token)):
    """Obtém o status atual de um download específico"""
    try:
        audio_info = await audio_manager.get_audio_info(audio_id)
        sse_status = sse_manager.get_download_status(audio_id)

        if not audio_info and not sse_status:
            raise HTTPException(
                status_code=404, detail=f"Áudio não encontrado: {audio_id}"
            )

        # Banco de dados é a fonte da verdade
        db_status = (
            audio_info.get("download_status", "unknown") if audio_info else "unknown"
        )
        db_progress = audio_info.get("download_progress", 0) if audio_info else 0
        db_error = audio_info.get("download_error", "") if audio_info else ""

        status = {
            "audio_id": audio_id,
            "download_status": db_status,
            "download_progress": db_progress,
            "download_error": db_error,
            "live_updates": sse_status is not None,
        }

        # Só usa SSE se o banco ainda não marcou como pronto/erro
        # e o SSE tem informação mais recente de progresso
        if sse_status and db_status not in ["ready", "completed", "error"]:
            sse_progress = sse_status.get("progress", 0)
            sse_stat = sse_status.get("status", "")

            # SSE completed significa que deve estar pronto no banco em breve
            if sse_stat == "completed":
                status["download_status"] = "ready"
                status["download_progress"] = 100
            elif sse_progress > db_progress:
                # SSE tem progresso mais recente
                status["download_progress"] = sse_progress

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter status do download: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter status do download: {str(e)}"
        )


@app.delete("/audio/{audio_id}")
async def delete_audio(audio_id: str, token_data: dict = Depends(verify_token)):
    """Exclui um áudio do banco de dados e remove os arquivos físicos"""
    try:
        result = await audio_manager.delete_audio(audio_id)
        if result:
            return {
                "status": "success",
                "message": f"Áudio {audio_id} excluído com sucesso",
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"Áudio não encontrado: {audio_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao excluir áudio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao excluir áudio: {str(e)}")


@app.delete("/video/{video_id}")
async def delete_video(video_id: str, token_data: dict = Depends(verify_token)):
    """Exclui um vídeo do banco de dados e remove os arquivos físicos"""
    try:
        result = await video_manager.delete_video(video_id)
        if result:
            return {
                "status": "success",
                "message": f"Vídeo {video_id} excluído com sucesso",
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"Vídeo não encontrado: {video_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao excluir vídeo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao excluir vídeo: {str(e)}")


# Endpoints para gerenciamento da fila


@app.get("/downloads/queue/status")
async def get_queue_status(token_data: dict = Depends(verify_token)):
    """Obtém o status atual da fila de downloads"""
    try:
        status = await download_queue.get_queue_status()
        return status
    except Exception as e:
        logger.exception(f"Erro ao obter status da fila: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter status da fila: {str(e)}"
        )


@app.get("/downloads/queue/tasks")
async def get_queue_tasks(
    status: Optional[str] = None,
    audio_id: Optional[str] = None,
    token_data: dict = Depends(verify_token),
):
    """Lista tasks na fila com filtros opcionais"""
    try:
        if audio_id:
            tasks = await download_queue.get_tasks_by_audio_id(audio_id)
        else:
            async with download_queue.queue_lock:
                tasks = list(download_queue.tasks.values())

        if status:
            tasks = [task for task in tasks if task.status == status]

        task_list = []
        for task in tasks:
            task_dict = {
                "id": task.id,
                "audio_id": task.audio_id,
                "url": task.url,
                "high_quality": task.high_quality,
                "status": task.status,
                "priority": task.priority,
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat()
                if task.completed_at
                else None,
                "error_message": task.error_message,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "next_retry_at": task.next_retry_at.isoformat()
                if task.next_retry_at
                else None,
                "progress": task.progress,
            }
            task_list.append(task_dict)

        return {"tasks": task_list}

    except Exception as e:
        logger.exception(f"Erro ao listar tasks da fila: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao listar tasks da fila: {str(e)}"
        )


@app.post("/downloads/queue/cancel/{task_id}")
async def cancel_download_task(task_id: str, token_data: dict = Depends(verify_token)):
    """Cancela um download específico na fila"""
    try:
        success = await download_queue.cancel_download(task_id)

        if success:
            return {
                "success": True,
                "message": f"Download {task_id} cancelado com sucesso",
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"Task {task_id} não encontrada"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao cancelar download: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao cancelar download: {str(e)}"
        )


@app.post("/downloads/queue/retry/{task_id}")
async def retry_download_task(task_id: str, token_data: dict = Depends(verify_token)):
    """Força retry de um download falhado"""
    try:
        task = await download_queue.get_task_status(task_id)

        if not task:
            raise HTTPException(
                status_code=404, detail=f"Task {task_id} não encontrada"
            )

        if task.status != "failed":
            raise HTTPException(
                status_code=400, detail=f"Task {task_id} não está em estado de falha"
            )

        async with download_queue.queue_lock:
            task.status = "queued"
            task.error_message = None
            task.next_retry_at = None

        return {"success": True, "message": f"Download {task_id} recolocado na fila"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao fazer retry do download: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao fazer retry do download: {str(e)}"
        )


@app.delete("/downloads/queue/cleanup")
async def cleanup_queue(
    max_age_hours: int = 24, token_data: dict = Depends(verify_token)
):
    """Remove tasks antigas da fila para limpeza"""
    try:
        await download_queue.cleanup_old_tasks(max_age_hours)
        return {
            "success": True,
            "message": f"Limpeza da fila concluída (tasks mais antigas que {max_age_hours}h)",
        }

    except Exception as e:
        logger.exception(f"Erro ao limpar fila: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao limpar fila: {str(e)}")


# ============================================================================
# ENDPOINTS DE PASTAS (FOLDERS)
# ============================================================================


@app.get("/albums", response_model=List[AlbumResponse])
async def list_albums(token_data: dict = Depends(verify_token)):
    """Lista álbuns (pastas kind=album) com contagem de faixas."""
    try:
        async with get_db_context() as session:
            folder_repo = FolderRepository(session)
            albums = await folder_repo.get_albums()
            result = []
            for album in albums:
                counts = await folder_repo.count_items(album.id)
                ready = await folder_repo.count_ready_audios(album.id)
                data = album.to_dict()
                data["track_count"] = counts["audios"]
                data["ready_count"] = ready
                result.append(AlbumResponse(**data))
            return result
    except Exception as e:
        logger.error(f"Erro ao listar álbuns: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar álbuns: {str(e)}")


@app.get("/albums/{folder_id}", response_model=AlbumDetailResponse)
async def get_album(folder_id: str, token_data: dict = Depends(verify_token)):
    """Detalhe do álbum com faixas ordenadas por track_number."""
    try:
        async with get_db_context() as session:
            folder_repo = FolderRepository(session)
            audio_repo = AudioRepository(session)

            folder = await folder_repo.get_by_id(folder_id)
            if not folder:
                raise HTTPException(
                    status_code=404, detail=f"Álbum não encontrado: {folder_id}"
                )
            if (folder.kind or "folder") != "album":
                raise HTTPException(
                    status_code=404, detail=f"Pasta não é um álbum: {folder_id}"
                )

            tracks = await audio_repo.get_by_folder(folder_id)
            counts = await folder_repo.count_items(folder_id)
            ready = await folder_repo.count_ready_audios(folder_id)
            data = folder.to_dict()
            data["track_count"] = counts["audios"]
            data["ready_count"] = ready
            data["tracks"] = [t.to_dict() for t in tracks]
            return AlbumDetailResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter álbum: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter álbum: {str(e)}")


@app.post("/folders", response_model=FolderResponse)
async def create_folder(
    folder_data: FolderCreate, token_data: dict = Depends(verify_token)
):
    """Cria uma nova pasta"""
    try:
        logger.info(f"Criando pasta: {folder_data.name}")

        async with get_db_context() as session:
            repo = FolderRepository(session)

            # Verifica se a pasta pai existe (se fornecida)
            if folder_data.parent_id:
                parent = await repo.get_by_id(folder_data.parent_id)
                if not parent:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Pasta pai não encontrada: {folder_data.parent_id}",
                    )

            # Cria a pasta
            folder = Folder(
                name=folder_data.name,
                parent_id=folder_data.parent_id,
                description=folder_data.description,
                color=folder_data.color,
                icon=folder_data.icon,
            )
            created = await repo.create(folder)
            logger.success(f"Pasta criada: {created.id}")
            return FolderResponse(**created.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao criar pasta: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar pasta: {str(e)}")


@app.get("/folders/root", response_model=List[FolderResponse])
async def list_root_folders(token_data: dict = Depends(verify_token)):
    """Lista apenas pastas raiz (sem parent)"""
    try:
        async with get_db_context() as session:
            repo = FolderRepository(session)
            root_folders = await repo.get_root_folders()
            return [FolderResponse(**f.to_dict()) for f in root_folders]

    except Exception as e:
        logger.exception(f"Erro ao listar pastas raiz: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao listar pastas raiz: {str(e)}"
        )


@app.get("/folders/{folder_id}/children", response_model=List[FolderResponse])
async def list_folder_children(
    folder_id: str, token_data: dict = Depends(verify_token)
):
    """Lista subpastas de uma pasta"""
    try:
        async with get_db_context() as session:
            repo = FolderRepository(session)

            # Verifica se a pasta existe
            folder = await repo.get_by_id(folder_id)
            if not folder:
                raise HTTPException(
                    status_code=404, detail=f"Pasta não encontrada: {folder_id}"
                )

            children = await repo.get_children(folder_id)
            return [FolderResponse(**f.to_dict()) for f in children]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao listar subpastas: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao listar subpastas: {str(e)}"
        )


@app.get("/folders/{folder_id}/items")
async def get_folder_items(folder_id: str, token_data: dict = Depends(verify_token)):
    """Lista itens (áudios e vídeos) de uma pasta"""
    try:
        async with get_db_context() as session:
            folder_repo = FolderRepository(session)
            audio_repo = AudioRepository(session)
            video_repo = VideoRepository(session)

            # Verifica se a pasta existe
            folder = await folder_repo.get_by_id(folder_id)
            if not folder:
                raise HTTPException(
                    status_code=404, detail=f"Pasta não encontrada: {folder_id}"
                )

            audios = await audio_repo.get_by_folder(folder_id)
            videos = await video_repo.get_by_folder(folder_id)

            return {
                "audios": [a.to_dict() for a in audios],
                "videos": [v.to_dict() for v in videos],
                "item_count": len(audios) + len(videos),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao listar itens da pasta: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao listar itens da pasta: {str(e)}"
        )


@app.get("/folders", response_model=List[FolderTreeResponse])
async def list_folders(
    tree: bool = Query(True, description="Retornar como árvore hierárquica"),
    token_data: dict = Depends(verify_token),
):
    """Lista todas as pastas"""
    try:
        async with get_db_context() as session:
            repo = FolderRepository(session)

            if tree:
                # Retorna apenas pastas raiz com filhos
                root_folders = await repo.get_root_folders()
                result = []

                async def build_tree(folder: Folder) -> dict:
                    children = await repo.get_children(folder.id)
                    item_counts = await repo.count_items(folder.id)
                    folder_dict = folder.to_dict()
                    folder_dict["children"] = [
                        await build_tree(child) for child in children
                    ]
                    folder_dict["item_count"] = item_counts["total"]
                    return folder_dict

                for folder in root_folders:
                    result.append(await build_tree(folder))

                return result
            else:
                # Retorna lista plana
                folders = await repo.get_all()
                return [FolderResponse(**f.to_dict()) for f in folders]

    except Exception as e:
        logger.exception(f"Erro ao listar pastas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar pastas: {str(e)}")


@app.get("/folders/{folder_id}", response_model=FolderWithItemsResponse)
async def get_folder(
    folder_id: str,
    include_items: bool = Query(
        True, description="Incluir itens (áudios/vídeos) da pasta"
    ),
    token_data: dict = Depends(verify_token),
):
    """Obtém detalhes de uma pasta"""
    try:
        async with get_db_context() as session:
            folder_repo = FolderRepository(session)
            folder = await folder_repo.get_by_id(folder_id)

            if not folder:
                raise HTTPException(
                    status_code=404, detail=f"Pasta não encontrada: {folder_id}"
                )

            result = folder.to_dict()

            if include_items:
                audio_repo = AudioRepository(session)
                video_repo = VideoRepository(session)

                audios = await audio_repo.get_by_folder(folder_id)
                videos = await video_repo.get_by_folder(folder_id)

                result["audios"] = [a.to_dict() for a in audios]
                result["videos"] = [v.to_dict() for v in videos]
                result["item_count"] = len(audios) + len(videos)
            else:
                result["audios"] = []
                result["videos"] = []
                result["item_count"] = 0

            return FolderWithItemsResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter pasta: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter pasta: {str(e)}")


@app.get("/folders/{folder_id}/path", response_model=FolderPathResponse)
async def get_folder_path(folder_id: str, token_data: dict = Depends(verify_token)):
    """Obtém o caminho completo de uma pasta (breadcrumb)"""
    try:
        async with get_db_context() as session:
            repo = FolderRepository(session)
            path = await repo.get_path(folder_id)

            if not path:
                raise HTTPException(
                    status_code=404, detail=f"Pasta não encontrada: {folder_id}"
                )

            return FolderPathResponse(
                path=[FolderResponse(**f.to_dict()) for f in path],
                full_path=" / ".join([f.name for f in path]),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter caminho da pasta: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao obter caminho da pasta: {str(e)}"
        )


@app.put("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str, folder_data: FolderUpdate, token_data: dict = Depends(verify_token)
):
    """Atualiza uma pasta"""
    try:
        async with get_db_context() as session:
            repo = FolderRepository(session)
            folder = await repo.get_by_id(folder_id)

            if not folder:
                raise HTTPException(
                    status_code=404, detail=f"Pasta não encontrada: {folder_id}"
                )

            # Verifica se a nova pasta pai existe e não cria ciclo
            if folder_data.parent_id is not None:
                if folder_data.parent_id == folder_id:
                    raise HTTPException(
                        status_code=400, detail="Uma pasta não pode ser pai de si mesma"
                    )

                if folder_data.parent_id != "":
                    parent = await repo.get_by_id(folder_data.parent_id)
                    if not parent:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Pasta pai não encontrada: {folder_data.parent_id}",
                        )

                    # Verifica se não está tentando mover para um descendente
                    path = await repo.get_path(folder_data.parent_id)
                    if any(f.id == folder_id for f in path):
                        raise HTTPException(
                            status_code=400,
                            detail="Não é possível mover pasta para um descendente",
                        )

            # Prepara dados de atualização
            update_data = {}
            if folder_data.name is not None:
                update_data["name"] = folder_data.name
            if folder_data.parent_id is not None:
                update_data["parent_id"] = (
                    folder_data.parent_id if folder_data.parent_id != "" else None
                )
            if folder_data.description is not None:
                update_data["description"] = folder_data.description
            if folder_data.color is not None:
                update_data["color"] = folder_data.color
            if folder_data.icon is not None:
                update_data["icon"] = folder_data.icon

            if update_data:
                updated = await repo.update(folder_id, **update_data)
                logger.info(f"Pasta atualizada: {folder_id}")
                return FolderResponse(**updated.to_dict())

            return FolderResponse(**folder.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao atualizar pasta: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao atualizar pasta: {str(e)}"
        )


@app.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    force: bool = Query(False, description="Forçar exclusão mesmo com itens"),
    token_data: dict = Depends(verify_token),
):
    """Exclui uma pasta"""
    try:
        async with get_db_context() as session:
            repo = FolderRepository(session)
            folder = await repo.get_by_id(folder_id)

            if not folder:
                raise HTTPException(
                    status_code=404, detail=f"Pasta não encontrada: {folder_id}"
                )

            # Verifica se tem subpastas
            if await repo.has_children(folder_id):
                raise HTTPException(
                    status_code=400,
                    detail="Não é possível excluir pasta com subpastas. Exclua as subpastas primeiro.",
                )

            # Verifica se tem itens
            if not force and await repo.has_items(folder_id):
                raise HTTPException(
                    status_code=400,
                    detail="Não é possível excluir pasta com itens. Use force=true ou mova os itens.",
                )

            # Se force=true, move itens para a pasta pai (ou raiz)
            if force:
                audio_repo = AudioRepository(session)
                video_repo = VideoRepository(session)

                audios = await audio_repo.get_by_folder(folder_id)
                for audio in audios:
                    await audio_repo.update_folder(audio.id, folder.parent_id)

                videos = await video_repo.get_by_folder(folder_id)
                for video in videos:
                    await video_repo.update_folder(video.id, folder.parent_id)

            await repo.delete(folder_id)
            logger.info(f"Pasta excluída: {folder_id}")

            return {"message": "Pasta excluída com sucesso", "folder_id": folder_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao excluir pasta: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao excluir pasta: {str(e)}")


@app.get("/folders/root/items")
async def get_root_items(token_data: dict = Depends(verify_token)):
    """Lista itens sem pasta (raiz)"""
    try:
        async with get_db_context() as session:
            audio_repo = AudioRepository(session)
            video_repo = VideoRepository(session)

            audios = await audio_repo.get_by_folder(None)
            videos = await video_repo.get_by_folder(None)

            return {
                "audios": [a.to_dict() for a in audios],
                "videos": [v.to_dict() for v in videos],
                "item_count": len(audios) + len(videos),
            }

    except Exception as e:
        logger.exception(f"Erro ao listar itens raiz: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao listar itens raiz: {str(e)}"
        )


@app.put("/audio/{audio_id}/folder")
async def move_audio_to_folder(
    audio_id: str, request: MoveItemRequest, token_data: dict = Depends(verify_token)
):
    """Move um áudio para uma pasta"""
    try:
        async with get_db_context() as session:
            audio_repo = AudioRepository(session)
            folder_repo = FolderRepository(session)

            # Verifica se o áudio existe
            audio = await audio_repo.get_by_id(audio_id)
            if not audio:
                raise HTTPException(
                    status_code=404, detail=f"Áudio não encontrado: {audio_id}"
                )

            # Verifica se a pasta destino existe
            if request.folder_id:
                folder = await folder_repo.get_by_id(request.folder_id)
                if not folder:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Pasta não encontrada: {request.folder_id}",
                    )

            # Move o áudio
            await audio_repo.update_folder(audio_id, request.folder_id)
            logger.info(f"Áudio {audio_id} movido para pasta {request.folder_id}")

            return {
                "message": "Áudio movido com sucesso",
                "audio_id": audio_id,
                "folder_id": request.folder_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao mover áudio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao mover áudio: {str(e)}")


@app.put("/video/{video_id}/folder")
async def move_video_to_folder(
    video_id: str, request: MoveItemRequest, token_data: dict = Depends(verify_token)
):
    """Move um vídeo para uma pasta"""
    try:
        async with get_db_context() as session:
            video_repo = VideoRepository(session)
            folder_repo = FolderRepository(session)

            # Verifica se o vídeo existe
            video = await video_repo.get_by_id(video_id)
            if not video:
                raise HTTPException(
                    status_code=404, detail=f"Vídeo não encontrado: {video_id}"
                )

            # Verifica se a pasta destino existe
            if request.folder_id:
                folder = await folder_repo.get_by_id(request.folder_id)
                if not folder:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Pasta não encontrada: {request.folder_id}",
                    )

            # Move o vídeo
            await video_repo.update_folder(video_id, request.folder_id)
            logger.info(f"Vídeo {video_id} movido para pasta {request.folder_id}")

            return {
                "message": "Vídeo movido com sucesso",
                "video_id": video_id,
                "folder_id": request.folder_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao mover vídeo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao mover vídeo: {str(e)}")


@app.put("/folders/bulk-move")
async def bulk_move_items(
    request: BulkMoveRequest, token_data: dict = Depends(verify_token)
):
    """Move múltiplos itens para uma pasta"""
    try:
        async with get_db_context() as session:
            audio_repo = AudioRepository(session)
            video_repo = VideoRepository(session)
            folder_repo = FolderRepository(session)

            # Verifica se a pasta destino existe
            if request.folder_id:
                folder = await folder_repo.get_by_id(request.folder_id)
                if not folder:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Pasta não encontrada: {request.folder_id}",
                    )

            moved_audios = 0
            moved_videos = 0

            # Move os áudios
            for audio_id in request.audio_ids:
                audio = await audio_repo.get_by_id(audio_id)
                if audio:
                    await audio_repo.update_folder(audio_id, request.folder_id)
                    moved_audios += 1

            # Move os vídeos
            for video_id in request.video_ids:
                video = await video_repo.get_by_id(video_id)
                if video:
                    await video_repo.update_folder(video_id, request.folder_id)
                    moved_videos += 1

            logger.info(
                f"Movidos {moved_audios} áudios e {moved_videos} vídeos para pasta {request.folder_id}"
            )

            return {
                "message": "Itens movidos com sucesso",
                "moved_audios": moved_audios,
                "moved_videos": moved_videos,
                "folder_id": request.folder_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao mover itens em lote: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Erro ao mover itens em lote: {str(e)}"
        )


# Web Client - Arquivos estáticos
WEB_CLIENT_DIR = Path(__file__).parent.parent.parent / "web_client"

if WEB_CLIENT_DIR.exists():
    # Montar arquivos estáticos (CSS, JS)
    app.mount("/static", StaticFiles(directory=str(WEB_CLIENT_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        """Serve a página principal do web client"""
        index_path = WEB_CLIENT_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path), media_type="text/html")
        raise HTTPException(status_code=404, detail="Index não encontrado")
