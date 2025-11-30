# main.py
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from loguru import logger
import uuid

# Configura logging antes de qualquer outro import
from app.core.logging import setup_logging
setup_logging(level="INFO")

from app.models.video import TokenData, ClientAuth, SortOption
from app.models.audio import AudioDownloadRequest, VideoDownloadRequest, TranscriptionRequest, TranscriptionResponse, TranscriptionProvider
from app.services.configs import video_mapping, AUDIO_DIR, audio_mapping, DOWNLOADS_DIR
from app.services.files import scan_video_directory, generate_video_stream, generate_audio_stream
from app.services.managers import VideoStreamManager, AudioDownloadManager, VideoDownloadManager
from app.services.securities import AUTHORIZED_CLIENTS, create_access_token, verify_token, verify_token_sync, ACCESS_TOKEN_EXPIRE_MINUTES
from app.services.transcription.service import TranscriptionService
from app.services.sse_manager import sse_manager
from app.services.download_queue import download_queue, DownloadTask
from app.db.database import init_db, migrate_json_to_sqlite


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

    # Iniciar processamento da fila
    download_queue.start_processing()

    logger.info("Aplicação iniciada com sucesso!")
    yield

    # Shutdown
    logger.info("Encerrando aplicação...")


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


# Callbacks da fila de downloads
async def on_download_started_callback(task: DownloadTask):
    await sse_manager.download_started(task.audio_id, f"Download iniciado na fila (posição: {task.priority})")


async def on_download_progress_callback(task: DownloadTask, progress: int):
    await sse_manager.download_progress(task.audio_id, progress)


async def on_download_completed_callback(task: DownloadTask):
    await sse_manager.download_completed(task.audio_id, f"Download concluído pela fila")


async def on_download_failed_callback(task: DownloadTask, error: str):
    await sse_manager.download_error(task.audio_id, error)


async def on_download_cancelled_callback(task: DownloadTask):
    await sse_manager.download_error(task.audio_id, "Download cancelado pelo usuário")


@app.post("/auth/token", response_model=TokenData)
async def login_for_access_token(client: ClientAuth):
    """Endpoint para autenticação do cliente"""
    if (client.client_id not in AUTHORIZED_CLIENTS or
            AUTHORIZED_CLIENTS[client.client_id]["secret"] != client.client_secret):
        logger.error("Credenciais inválidas.")
        raise HTTPException(
            status_code=401,
            detail="Credenciais inválidas"
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": client.client_id},
        expires_delta=access_token_expires
    )

    result = {"access_token": access_token, "token_type": "bearer"}
    logger.debug(f"Credenciais: {result}")
    return result


@app.get("/videos")
async def list_videos(
        sort_by: SortOption = Query(SortOption.NONE),
        token_data: dict = Depends(verify_token)
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
async def list_video_downloads(
        token_data: dict = Depends(verify_token)
):
    """Lista todos os vídeos baixados"""
    try:
        logger.debug("Listando vídeos do banco de dados")

        videos = await video_manager.get_all_videos()

        logger.info(f"Encontrados {len(videos)} vídeos")
        return {"videos": videos}
    except Exception as e:
        logger.exception(f"Erro ao listar vídeos: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar vídeos: {str(e)}"
        )


@app.get("/video/{video_id}")
async def stream_video(
        video_id: str,
        token_data: dict = Depends(verify_token)
):
    """Stream de vídeo (requer autenticação)"""
    if video_id not in video_mapping:
        logger.error("Vídeo não encontrado.")
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    video_source = video_mapping[video_id]

    # Se for uma URL do YouTube
    if isinstance(video_source, str) and video_source.startswith('http'):
        logger.debug(f"Iniciando streaming do YouTube: {video_source}")
        return StreamingResponse(
            stream_manager.stream_youtube_video(video_source),
            media_type='video/mp4'
        )

    # Para vídeos locais
    video_path = video_source
    content_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm'
    }

    content_type = content_types.get(video_path.suffix.lower())
    if not content_type:
        logger.error("Formato de vídeo não suportado.")
        raise HTTPException(status_code=400, detail="Formato de vídeo não suportado")

    return StreamingResponse(
        generate_video_stream(video_path),
        media_type=content_type
    )


@app.get("/audios/{audio_id}/stream/")
async def stream_audio(
        audio_id: str,
        token_data: dict = Depends(verify_token)
):
    """Endpoint para streaming de áudio (requer autenticação)"""
    try:
        logger.debug(f"Solicitado streaming do áudio: {audio_id}")

        # Busca o áudio no mapeamento
        if audio_id not in audio_mapping:
            logger.warning(f"Áudio não encontrado no mapeamento: {audio_id}")
            raise HTTPException(status_code=404, detail="Áudio não encontrado")

        audio_path = audio_mapping[audio_id]

        # Verifica se o arquivo existe
        if not audio_path.exists():
            logger.warning(f"Arquivo de áudio não encontrado: {audio_path}")
            raise HTTPException(status_code=404, detail="Arquivo de áudio não encontrado")

        # Determina o tipo de mídia
        content_type = "audio/mp4"
        if audio_path.suffix.lower() == '.m4a':
            content_type = "audio/mp4"
        elif audio_path.suffix.lower() == '.mp3':
            content_type = "audio/mpeg"
        elif audio_path.suffix.lower() == '.wav':
            content_type = "audio/wav"
        elif audio_path.suffix.lower() == '.ogg':
            content_type = "audio/ogg"

        logger.info(f"Streaming áudio {audio_id}: {audio_path} ({content_type})")

        return StreamingResponse(
            generate_audio_stream(audio_path),
            media_type=content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao fazer streaming do áudio {audio_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao fazer streaming do áudio: {str(e)}"
        )


@app.get("/audio/check_exists")
async def check_audio_exists(
        youtube_url: str,
        token_data: dict = Depends(verify_token)
):
    """Verifica se um áudio de um vídeo do YouTube já foi baixado"""
    try:
        logger.info(f"Verificando se áudio já existe para URL: {youtube_url}")

        youtube_id = audio_manager.extract_youtube_id(youtube_url)

        if not youtube_id:
            logger.warning(f"Não foi possível extrair o ID do YouTube da URL: {youtube_url}")
            return {"exists": False, "message": "URL inválida ou não reconhecida"}

        # Busca no banco de dados
        audio_info = await audio_manager.get_audio_by_youtube_id(youtube_id)

        if not audio_info:
            logger.info(f"Áudio com ID '{youtube_id}' não encontrado no sistema")
            return {"exists": False, "message": "Áudio não encontrado no sistema"}

        download_status = audio_info.get("download_status", "unknown")

        if download_status not in ["ready", "completed"]:
            logger.info(f"Áudio com ID '{youtube_id}' existe mas não foi baixado. Status: {download_status}")
            return {
                "exists": False,
                "message": f"Áudio existe mas não foi baixado completamente (status: {download_status})",
                "audio_info": audio_info
            }

        # Verifica se o arquivo existe
        if audio_info.get("path"):
            audio_file_path = AUDIO_DIR.parent / audio_info["path"]
            if not audio_file_path.exists():
                logger.warning(f"Arquivo não encontrado: {audio_file_path}")
                return {
                    "exists": False,
                    "message": "Áudio registrado mas arquivo não encontrado",
                    "audio_info": audio_info
                }

            file_size = audio_file_path.stat().st_size
            if file_size == 0:
                logger.warning(f"Arquivo vazio: {audio_file_path}")
                return {
                    "exists": False,
                    "message": "Áudio existe mas o arquivo está vazio",
                    "audio_info": audio_info
                }
        else:
            logger.warning(f"Áudio sem caminho definido")
            return {
                "exists": False,
                "message": "Áudio registrado mas caminho não definido",
                "audio_info": audio_info
            }

        logger.info(f"Áudio com ID '{youtube_id}' já existe e foi baixado")
        return {
            "exists": True,
            "message": "Este áudio já foi baixado com sucesso",
            "audio_info": audio_info
        }

    except Exception as e:
        logger.exception(f"Erro ao verificar existência do áudio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao verificar existência do áudio: {str(e)}"
        )


@app.post("/audio/download")
async def download_audio(
        request: AudioDownloadRequest,
        background_tasks: BackgroundTasks,
        token_data: dict = Depends(verify_token)
):
    """Faz o download apenas do áudio de um vídeo do YouTube"""
    try:
        logger.info(f"Solicitação de download de áudio: {request.url}")

        # Registra o áudio com status 'downloading'
        try:
            audio_id = await audio_manager.register_audio_for_download(str(request.url))
            logger.info(f"Áudio registrado com ID: {audio_id}")
        except Exception as e:
            logger.error(f"Erro ao registrar áudio: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao registrar áudio: {str(e)}"
            )

        # Adicionar à fila de downloads
        task_id = await download_queue.add_download(
            audio_id=audio_id,
            url=str(request.url),
            high_quality=request.high_quality,
            priority=0
        )

        return {
            "status": "processando",
            "message": "O áudio foi registrado e adicionado à fila de downloads",
            "audio_id": audio_id,
            "task_id": task_id,
            "url": str(request.url)
        }
    except Exception as e:
        logger.exception(f"Erro ao iniciar download de áudio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao iniciar download de áudio: {str(e)}"
        )


@app.post("/video/download")
async def download_video(
        request: VideoDownloadRequest,
        background_tasks: BackgroundTasks,
        token_data: dict = Depends(verify_token)
):
    """Faz o download de um vídeo do YouTube"""
    try:
        logger.info(f"Solicitação de download de vídeo: {request.url} (resolução: {request.resolution})")

        # Registra o vídeo com status 'downloading'
        try:
            video_id = await video_manager.register_video_for_download(
                str(request.url),
                resolution=request.resolution
            )
            logger.info(f"Vídeo registrado com ID: {video_id}")
        except Exception as e:
            logger.error(f"Erro ao registrar vídeo: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao registrar vídeo: {str(e)}"
            )

        # Inicia o download em background
        background_tasks.add_task(
            video_manager.download_video_with_status_async,
            video_id,
            str(request.url),
            request.resolution,
            sse_manager
        )

        return {
            "status": "processando",
            "message": "O vídeo foi registrado e o download foi iniciado",
            "video_id": video_id,
            "resolution": request.resolution,
            "url": str(request.url)
        }
    except Exception as e:
        logger.exception(f"Erro ao iniciar download de vídeo: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao iniciar download de vídeo: {str(e)}"
        )


@app.get("/video/download-status/{video_id}")
async def get_video_download_status(
        video_id: str,
        token_data: dict = Depends(verify_token)
):
    """Obtém o status de download de um vídeo"""
    try:
        video_info = await video_manager.get_video_info(video_id)

        if not video_info:
            raise HTTPException(
                status_code=404,
                detail=f"Vídeo não encontrado: {video_id}"
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
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter status: {str(e)}"
        )


@app.get("/video/stream/{video_id}")
async def stream_downloaded_video(
        video_id: str,
        token_data: dict = Depends(verify_token)
):
    """Streaming de vídeo baixado do YouTube"""
    try:
        logger.debug(f"Solicitado streaming do vídeo: {video_id}")

        video_info = await video_manager.get_video_by_youtube_id(video_id)

        if not video_info:
            logger.warning(f"Vídeo não encontrado: {video_id}")
            raise HTTPException(status_code=404, detail="Vídeo não encontrado")

        if video_info.get("download_status") != "ready":
            logger.warning(f"Vídeo ainda não está pronto: {video_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Vídeo ainda não está pronto. Status: {video_info.get('download_status')}"
            )

        # O path no banco é relativo (ex: videos/id/file.mp4), construir caminho absoluto
        relative_path = video_info.get("path", "")
        video_path = DOWNLOADS_DIR / relative_path

        if not video_path.exists():
            logger.error(f"Arquivo de vídeo não encontrado: {video_path}")
            raise HTTPException(status_code=404, detail="Arquivo de vídeo não encontrado")

        content_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska'
        }

        content_type = content_types.get(video_path.suffix.lower(), 'video/mp4')

        logger.info(f"Iniciando streaming do vídeo: {video_path}")
        return StreamingResponse(
            generate_video_stream(video_path),
            media_type=content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao fazer streaming do vídeo {video_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao fazer streaming do vídeo: {str(e)}"
        )


@app.get("/audio/list")
async def list_audio_files(
        token_data: dict = Depends(verify_token)
):
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
            status_code=500,
            detail=f"Erro ao listar arquivos de áudio: {str(e)}"
        )


@app.post("/audio/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
        request: TranscriptionRequest,
        background_tasks: BackgroundTasks,
        token_data: dict = Depends(verify_token)
):
    """Transcreve um arquivo de áudio"""
    try:
        logger.info(f"Solicitação de transcrição para arquivo ID: '{request.file_id}'")

        # Verifica se existe informação do áudio
        audio_info = await audio_manager.get_audio_info(request.file_id)

        if audio_info:
            logger.debug(f"Áudio encontrado: {audio_info['id']}")
            audio_path = AUDIO_DIR.parent / audio_info["path"]

            if not audio_path.exists():
                logger.error(f"Arquivo de áudio não encontrado: {audio_path}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Arquivo de áudio não encontrado: {audio_path}"
                )

            transcription_status = audio_info.get("transcription_status", "none")

            if transcription_status == "ended" and audio_info.get("transcription_path"):
                transcription_path = AUDIO_DIR.parent / audio_info["transcription_path"]
                if transcription_path.exists():
                    logger.info(f"Transcrição já existe: {transcription_path}")
                    return TranscriptionResponse(
                        file_id=request.file_id,
                        transcription_path=str(transcription_path),
                        status="success",
                        message="Transcrição já existe"
                    )

            elif transcription_status == "started":
                logger.info(f"Transcrição já está em andamento para: {request.file_id}")
                return TranscriptionResponse(
                    file_id=request.file_id,
                    transcription_path="",
                    status="processing",
                    message="A transcrição já está em andamento"
                )

            elif transcription_status == "error":
                logger.warning(f"Erro anterior na transcrição. Tentando novamente.")
        else:
            try:
                audio_path = TranscriptionService.find_audio_file(request.file_id)
                logger.debug(f"Arquivo encontrado por busca: {audio_path}")
            except FileNotFoundError:
                logger.error(f"Arquivo de áudio não encontrado: '{request.file_id}'")
                raise HTTPException(
                    status_code=404,
                    detail=f"Arquivo de áudio não encontrado: {request.file_id}"
                )

        transcription_file = audio_path.with_suffix(".md")

        if transcription_file.exists():
            logger.info(f"Transcrição já existe: {transcription_file}")

            if audio_info:
                rel_path = str(transcription_file.relative_to(AUDIO_DIR.parent))
                await audio_manager.update_transcription_status(
                    audio_info["id"],
                    "ended",
                    rel_path
                )

            return TranscriptionResponse(
                file_id=request.file_id,
                transcription_path=str(transcription_file),
                status="success",
                message="Transcrição já existe"
            )

        # Atualiza o status para "started"
        if audio_info:
            await audio_manager.update_transcription_status(audio_info["id"], "started")

        # Tarefa em segundo plano para transcrição
        def transcribe_task():
            try:
                provider = TranscriptionProvider(request.provider)

                docs = TranscriptionService.transcribe_audio(
                    file_path=str(audio_path),
                    provider=provider,
                    language=request.language
                )

                if docs:
                    output_path = str(transcription_file)
                    transcription_path = TranscriptionService.save_transcription(docs, output_path)

                    if audio_info:
                        rel_path = Path(transcription_path).relative_to(AUDIO_DIR.parent)
                        # Executa atualização assíncrona
                        asyncio.run(audio_manager.update_transcription_status(
                            audio_info["id"],
                            "ended",
                            str(rel_path)
                        ))

                    logger.success(f"Transcrição concluída: {output_path}")
                else:
                    if audio_info:
                        asyncio.run(audio_manager.update_transcription_status(audio_info["id"], "error"))
                    logger.error(f"Falha na transcrição: nenhum conteúdo gerado")
            except Exception as e:
                if audio_info:
                    asyncio.run(audio_manager.update_transcription_status(audio_info["id"], "error"))
                logger.exception(f"Erro na tarefa de transcrição: {str(e)}")

        background_tasks.add_task(transcribe_task)

        return TranscriptionResponse(
            file_id=request.file_id,
            transcription_path=str(transcription_file),
            status="processing",
            message="A transcrição foi iniciada em segundo plano"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao iniciar transcrição: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao iniciar transcrição: {str(e)}"
        )


@app.get("/audio/transcription/{file_id}")
async def get_transcription(
        file_id: str,
        token_data: dict = Depends(verify_token)
):
    """Obtém o arquivo de transcrição"""
    try:
        logger.info(f"Solicitação de obtenção de transcrição para ID: {file_id}")

        audio_info = await audio_manager.get_audio_info(file_id)

        if audio_info and audio_info.get("transcription_status") == "ended":
            transcription_path = AUDIO_DIR.parent / audio_info["transcription_path"]

            if transcription_path.exists():
                logger.debug(f"Transcrição encontrada: {transcription_path}")
                return FileResponse(
                    path=transcription_path,
                    media_type="text/markdown",
                    filename=transcription_path.name
                )
            else:
                logger.warning(f"Caminho de transcrição não existe: {transcription_path}")

        try:
            audio_file = TranscriptionService.find_audio_file(file_id)
            transcription_file = audio_file.with_suffix(".md")

            if not transcription_file.exists():
                logger.error(f"Transcrição não encontrada para: {file_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Transcrição não encontrada para: {file_id}"
                )

            logger.debug(f"Transcrição encontrada: {transcription_file}")

            if audio_info and audio_info.get("transcription_status") != "ended":
                rel_path = str(transcription_file.relative_to(AUDIO_DIR.parent))
                await audio_manager.update_transcription_status(audio_info["id"], "ended", rel_path)

        except FileNotFoundError:
            transcription_files = list(AUDIO_DIR.glob("**/*.md"))

            matching_transcriptions = []
            for tf in transcription_files:
                if TranscriptionService.calculate_similarity(file_id, tf.stem) > 0.3:
                    matching_transcriptions.append(tf)

            if not matching_transcriptions:
                logger.error(f"Arquivo não encontrado: {file_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Arquivo não encontrado: {file_id}"
                )

            transcription_file = matching_transcriptions[0]
            logger.debug(f"Transcrição encontrada por busca: {transcription_file}")

            if audio_info:
                rel_path = str(transcription_file.relative_to(AUDIO_DIR.parent))
                await audio_manager.update_transcription_status(audio_info["id"], "ended", rel_path)

        return FileResponse(
            path=transcription_file,
            media_type="text/markdown",
            filename=transcription_file.name
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter transcrição: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter transcrição: {str(e)}"
        )


@app.get("/audio/stream/{audio_id}")
async def stream_audio_file(
        audio_id: str,
        token: str = Query(None)
):
    """Endpoint para servir arquivos de áudio com autenticação opcional"""
    try:
        if token:
            try:
                verify_token_sync(token)
            except Exception as e:
                logger.warning(f"Token inválido: {str(e)}")
                raise HTTPException(status_code=403, detail="Token inválido")

        logger.debug(f"Solicitado stream do áudio: {audio_id}")

        # Busca no banco de dados
        audio = await audio_manager.get_audio_info(audio_id)

        if not audio:
            logger.warning(f"Áudio não encontrado: {audio_id}")
            raise HTTPException(status_code=404, detail="Áudio não encontrado")

        audio_file_path = AUDIO_DIR.parent / audio["path"]

        if not audio_file_path.exists():
            logger.warning(f"Arquivo não encontrado: {audio_file_path}")
            raise HTTPException(status_code=404, detail="Arquivo de áudio não encontrado")

        content_type = "audio/mp4"
        if audio_file_path.suffix.lower() == '.m4a':
            content_type = "audio/mp4"
        elif audio_file_path.suffix.lower() == '.mp3':
            content_type = "audio/mpeg"
        elif audio_file_path.suffix.lower() == '.wav':
            content_type = "audio/wav"

        logger.info(f"Servindo áudio {audio_id}: {audio_file_path} ({content_type})")

        return FileResponse(
            path=str(audio_file_path),
            media_type=content_type,
            filename=f"{audio['name']}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao servir áudio {audio_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao servir áudio: {str(e)}"
        )


@app.get("/audio/transcription_status/{file_id}")
async def get_transcription_status(
        file_id: str,
        token_data: dict = Depends(verify_token)
):
    """Obtém o status atual da transcrição"""
    try:
        logger.info(f"Solicitação de status de transcrição para ID: {file_id}")

        audio_info = await audio_manager.get_audio_info(file_id)

        if not audio_info:
            logger.warning(f"Áudio não encontrado: {file_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Áudio não encontrado: {file_id}"
            )

        transcription_status = audio_info.get("transcription_status", "none")

        transcription_path = None
        if transcription_status == "ended" and audio_info.get("transcription_path"):
            transcription_path = audio_info["transcription_path"]

        return {
            "file_id": file_id,
            "status": transcription_status,
            "transcription_path": transcription_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter status da transcrição: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter status da transcrição: {str(e)}"
        )


@app.delete("/audio/transcription/{file_id}")
async def delete_transcription(
        file_id: str,
        token_data: dict = Depends(verify_token)
):
    """Exclui a transcrição de um áudio"""
    try:
        logger.info(f"Solicitação de exclusão de transcrição para ID: {file_id}")

        audio_info = await audio_manager.get_audio_info(file_id)

        if not audio_info:
            logger.warning(f"Áudio não encontrado: {file_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Áudio não encontrado: {file_id}"
            )

        transcription_status = audio_info.get("transcription_status", "none")
        transcription_path = audio_info.get("transcription_path")

        if transcription_status != "ended" or not transcription_path:
            logger.warning(f"Transcrição não encontrada para: {file_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Transcrição não encontrada para: {file_id}"
            )

        # Caminho completo do arquivo de transcrição
        full_path = AUDIO_DIR.parent / transcription_path

        # Remove o arquivo se existir
        if full_path.exists():
            full_path.unlink()
            logger.info(f"Arquivo de transcrição removido: {full_path}")
        else:
            logger.warning(f"Arquivo de transcrição não existe: {full_path}")

        # Atualiza o status no banco de dados
        await audio_manager.update_transcription_status(file_id, "none", None)

        logger.success(f"Transcrição excluída com sucesso para: {file_id}")

        return {
            "status": "success",
            "message": f"Transcrição excluída com sucesso",
            "file_id": file_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao excluir transcrição: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao excluir transcrição: {str(e)}"
        )


# SSE e status de download

@app.get("/audio/download-events")
async def download_events_stream(
    token: str = Query(None, description="Token de autenticação"),
    authorization: Optional[str] = Header(None, alias="Authorization")
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
async def get_download_status(
    audio_id: str,
    token_data: dict = Depends(verify_token)
):
    """Obtém o status atual de um download específico"""
    try:
        audio_info = await audio_manager.get_audio_info(audio_id)
        sse_status = sse_manager.get_download_status(audio_id)

        if not audio_info and not sse_status:
            raise HTTPException(
                status_code=404,
                detail=f"Áudio não encontrado: {audio_id}"
            )

        # Banco de dados é a fonte da verdade
        db_status = audio_info.get("download_status", "unknown") if audio_info else "unknown"
        db_progress = audio_info.get("download_progress", 0) if audio_info else 0
        db_error = audio_info.get("download_error", "") if audio_info else ""

        status = {
            "audio_id": audio_id,
            "download_status": db_status,
            "download_progress": db_progress,
            "download_error": db_error,
            "live_updates": sse_status is not None
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
            status_code=500,
            detail=f"Erro ao obter status do download: {str(e)}"
        )


@app.delete("/audio/{audio_id}")
async def delete_audio(
    audio_id: str,
    token_data: dict = Depends(verify_token)
):
    """Exclui um áudio do banco de dados e remove os arquivos físicos"""
    try:
        result = await audio_manager.delete_audio(audio_id)
        if result:
            return {
                "status": "success",
                "message": f"Áudio {audio_id} excluído com sucesso"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Áudio não encontrado: {audio_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao excluir áudio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao excluir áudio: {str(e)}"
        )


@app.delete("/video/{video_id}")
async def delete_video(
    video_id: str,
    token_data: dict = Depends(verify_token)
):
    """Exclui um vídeo do banco de dados e remove os arquivos físicos"""
    try:
        result = await video_manager.delete_video(video_id)
        if result:
            return {
                "status": "success",
                "message": f"Vídeo {video_id} excluído com sucesso"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Vídeo não encontrado: {video_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao excluir vídeo: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao excluir vídeo: {str(e)}"
        )


# Endpoints para gerenciamento da fila

@app.get("/downloads/queue/status")
async def get_queue_status(
    token_data: dict = Depends(verify_token)
):
    """Obtém o status atual da fila de downloads"""
    try:
        status = await download_queue.get_queue_status()
        return status
    except Exception as e:
        logger.exception(f"Erro ao obter status da fila: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter status da fila: {str(e)}"
        )


@app.get("/downloads/queue/tasks")
async def get_queue_tasks(
    status: Optional[str] = None,
    audio_id: Optional[str] = None,
    token_data: dict = Depends(verify_token)
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
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "next_retry_at": task.next_retry_at.isoformat() if task.next_retry_at else None,
                "progress": task.progress
            }
            task_list.append(task_dict)

        return {"tasks": task_list}

    except Exception as e:
        logger.exception(f"Erro ao listar tasks da fila: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar tasks da fila: {str(e)}"
        )


@app.post("/downloads/queue/cancel/{task_id}")
async def cancel_download_task(
    task_id: str,
    token_data: dict = Depends(verify_token)
):
    """Cancela um download específico na fila"""
    try:
        success = await download_queue.cancel_download(task_id)

        if success:
            return {
                "success": True,
                "message": f"Download {task_id} cancelado com sucesso"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} não encontrada"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao cancelar download: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao cancelar download: {str(e)}"
        )


@app.post("/downloads/queue/retry/{task_id}")
async def retry_download_task(
    task_id: str,
    token_data: dict = Depends(verify_token)
):
    """Força retry de um download falhado"""
    try:
        task = await download_queue.get_task_status(task_id)

        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} não encontrada"
            )

        if task.status != "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Task {task_id} não está em estado de falha"
            )

        async with download_queue.queue_lock:
            task.status = "queued"
            task.error_message = None
            task.next_retry_at = None

        return {
            "success": True,
            "message": f"Download {task_id} recolocado na fila"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao fazer retry do download: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao fazer retry do download: {str(e)}"
        )


@app.delete("/downloads/queue/cleanup")
async def cleanup_queue(
    max_age_hours: int = 24,
    token_data: dict = Depends(verify_token)
):
    """Remove tasks antigas da fila para limpeza"""
    try:
        await download_queue.cleanup_old_tasks(max_age_hours)
        return {
            "success": True,
            "message": f"Limpeza da fila concluída (tasks mais antigas que {max_age_hours}h)"
        }

    except Exception as e:
        logger.exception(f"Erro ao limpar fila: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao limpar fila: {str(e)}"
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
