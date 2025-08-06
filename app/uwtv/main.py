# main.py
import os
import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from loguru import logger
import uuid

from app.models.video import TokenData, ClientAuth, SortOption
from app.models.audio import AudioDownloadRequest, TranscriptionRequest, TranscriptionResponse, TranscriptionProvider
from app.services.configs import video_mapping, AUDIO_DIR, audio_mapping
from app.services.files import scan_video_directory, generate_video_stream, scan_audio_directory
from app.services.managers import VideoStreamManager, AudioDownloadManager
from app.services.securities import AUTHORIZED_CLIENTS, create_access_token, verify_token, verify_token_sync, ACCESS_TOKEN_EXPIRE_MINUTES
from app.services.transcription.service import TranscriptionService
from app.services.sse_manager import sse_manager
from app.services.download_queue import download_queue, DownloadTask

app = FastAPI(title="Video Streaming API")

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

# Executa a migração de has_transcription para transcription_status se necessário
try:
    audio_manager.migrate_has_transcription_to_status()
except Exception as e:
    logger.error(f"Erro durante a migração do campo has_transcription: {str(e)}")

# Configurar callbacks da fila de downloads
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

# Configurar callbacks
download_queue.on_download_started = on_download_started_callback
download_queue.on_download_progress = on_download_progress_callback
download_queue.on_download_completed = on_download_completed_callback
download_queue.on_download_failed = on_download_failed_callback
download_queue.on_download_cancelled = on_download_cancelled_callback

# Iniciar processamento da fila
download_queue.start_processing()


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
            media_type='video/mp4'  # YouTube geralmente fornece MP4
        )

    # Para vídeos locais, mantém o código original
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


# Novo endpoint para verificar se um áudio já existe
@app.get("/audio/check_exists")
async def check_audio_exists(
        youtube_url: str,
        token_data: dict = Depends(verify_token)
):
    """
    Verifica se um áudio de um vídeo do YouTube já foi baixado completamente (requer autenticação)
    """
    try:
        logger.info(f"Verificando se áudio já existe para URL: {youtube_url}")
        
        # Extrai o ID do YouTube da URL
        youtube_id = audio_manager.extract_youtube_id(youtube_url)
        
        if not youtube_id:
            logger.warning(f"Não foi possível extrair o ID do YouTube da URL: {youtube_url}")
            return {"exists": False, "message": "URL inválida ou não reconhecida"}
        
        # Verifica se existe algum áudio com este ID do YouTube
        for audio in audio_manager.audio_data["audios"]:
            if audio.get("youtube_id") == youtube_id:
                # Verifica se o download foi completado com sucesso
                download_status = audio.get("download_status", "unknown")
                
                # Se o status não é "ready" ou "completed", não está pronto
                if download_status not in ["ready", "completed"]:
                    logger.info(f"Áudio com ID '{youtube_id}' existe mas não foi baixado completamente. Status: {download_status}")
                    return {
                        "exists": False, 
                        "message": f"Áudio existe no sistema mas não foi baixado completamente (status: {download_status})",
                        "audio_info": audio
                    }
                
                # Verifica se o arquivo realmente existe no sistema de arquivos
                if audio.get("path"):
                    audio_file_path = AUDIO_DIR.parent / audio["path"]
                    if not audio_file_path.exists():
                        logger.warning(f"Áudio com ID '{youtube_id}' existe no sistema mas arquivo não foi encontrado: {audio_file_path}")
                        return {
                            "exists": False, 
                            "message": "Áudio registrado no sistema mas arquivo não encontrado",
                            "audio_info": audio
                        }
                    
                    # Verifica se o arquivo tem tamanho válido (não está corrompido/incompleto)
                    file_size = audio_file_path.stat().st_size
                    if file_size == 0:
                        logger.warning(f"Áudio com ID '{youtube_id}' existe mas o arquivo está vazio: {audio_file_path}")
                        return {
                            "exists": False, 
                            "message": "Áudio existe mas o arquivo está vazio ou corrompido",
                            "audio_info": audio
                        }
                else:
                    logger.warning(f"Áudio com ID '{youtube_id}' existe no sistema mas não tem caminho definido")
                    return {
                        "exists": False, 
                        "message": "Áudio registrado no sistema mas caminho do arquivo não definido",
                        "audio_info": audio
                    }
                
                logger.info(f"Áudio com ID '{youtube_id}' já existe e foi baixado completamente")
                return {
                    "exists": True, 
                    "message": "Este áudio já foi baixado e verificado com sucesso",
                    "audio_info": audio
                }
        
        logger.info(f"Áudio com ID '{youtube_id}' não encontrado no sistema")
        return {"exists": False, "message": "Áudio não encontrado no sistema"}
        
    except Exception as e:
        logger.exception(f"Erro ao verificar existência do áudio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao verificar existência do áudio: {str(e)}"
        )


# Novos endpoints para download de áudio e transcrição

@app.post("/audio/download")
async def download_audio(
        request: AudioDownloadRequest,
        background_tasks: BackgroundTasks,
        token_data: dict = Depends(verify_token)
):
    """
    Faz o download apenas do áudio de um vídeo do YouTube (requer autenticação)
    Registra o áudio imediatamente e depois faz o download em background.
    """
    try:
        logger.info(f"Solicitação de download de áudio: {request.url}")
        
        # Primeiro, registra o áudio com status 'downloading'
        try:
            audio_id = audio_manager.register_audio_for_download(str(request.url))
            logger.info(f"Áudio registrado com ID: {audio_id}")
        except Exception as e:
            logger.error(f"Erro ao registrar áudio: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao registrar áudio: {str(e)}"
            )
        
        # Adicionar à fila de downloads ao invés de executar diretamente
        task_id = await download_queue.add_download(
            audio_id=audio_id,
            url=str(request.url),
            high_quality=request.high_quality,
            priority=0  # Prioridade normal
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


@app.get("/audio/list")
async def list_audio_files(
        token_data: dict = Depends(verify_token)
):
    """
    Lista todos os arquivos de áudio disponíveis (requer autenticação)
    Usa o arquivo data/audios.json como fonte de dados
    """
    try:
        logger.debug(f"Listando arquivos de áudio a partir do arquivo audios.json")
        
        # Carrega os dados do arquivo audios.json usando a função scan_audio_directory
        audio_files = scan_audio_directory()
        
        logger.info(f"Encontrados {len(audio_files)} arquivos de áudio no audios.json")
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
    """
    Transcreve um arquivo de áudio (requer autenticação)
    """
    try:
        logger.info(f"Solicitação de transcrição para arquivo ID: '{request.file_id}'")
        
        # Verifica se existe informação do áudio no gerenciador
        audio_info = audio_manager.get_audio_info(request.file_id)
        
        if audio_info:
            logger.debug(f"Áudio encontrado no gerenciador: {audio_info['id']}")
            audio_path = AUDIO_DIR.parent / audio_info["path"]
            
            # Verifica se o arquivo existe
            if not audio_path.exists():
                logger.error(f"Arquivo de áudio não encontrado no caminho: {audio_path}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Arquivo de áudio não encontrado: {audio_path}"
                )
                
            # Verifica o status da transcrição
            transcription_status = audio_info.get("transcription_status", "none")
            
            # Se a transcrição já estiver concluída (status "ended")
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
            
            # Se a transcrição estiver em andamento
            elif transcription_status == "started":
                logger.info(f"Transcrição já está em andamento para: {request.file_id}")
                return TranscriptionResponse(
                    file_id=request.file_id,
                    transcription_path="",
                    status="processing",
                    message="A transcrição já está em andamento"
                )
            
            # Se a transcrição teve erro anteriormente
            elif transcription_status == "error":
                logger.warning(f"Erro anterior na transcrição para: {request.file_id}. Tentando novamente.")
                # Continua para reiniciar a transcrição
        else:
            # Se não encontrou no gerenciador, tenta encontrar o arquivo
            try:
                audio_path = TranscriptionService.find_audio_file(request.file_id)
                logger.debug(f"Arquivo encontrado por busca: {audio_path}")
            except FileNotFoundError:
                logger.error(f"Arquivo de áudio não encontrado: '{request.file_id}'")
                raise HTTPException(
                    status_code=404,
                    detail=f"Arquivo de áudio não encontrado: {request.file_id}"
                )
                
        # Define o caminho para o arquivo de transcrição
        transcription_file = audio_path.with_suffix(".md")
        
        # Verifica se o arquivo de transcrição já existe
        if transcription_file.exists():
            logger.info(f"Transcrição já existe no caminho: {transcription_file}")
            
            # Se encontramos no sistema de arquivos mas o status não está correto, atualizamos o gerenciador
            if audio_info:
                rel_path = str(transcription_file.relative_to(AUDIO_DIR.parent))
                audio_manager.update_transcription_status(
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
            
        # Atualiza o status para "started" antes de iniciar a transcrição
        if audio_info:
            audio_manager.update_transcription_status(audio_info["id"], "started")
            
        # Cria uma tarefa em segundo plano para transcrição
        def transcribe_task():
            try:
                # Converte o provedor de string para enum
                provider = TranscriptionProvider(request.provider)
                
                # Transcreve o áudio
                docs = TranscriptionService.transcribe_audio(
                    file_path=str(audio_path),
                    provider=provider,
                    language=request.language
                )
                
                # Salva a transcrição
                if docs:
                    output_path = str(transcription_file)
                    transcription_path = TranscriptionService.save_transcription(docs, output_path)
                    
                    # Atualiza o status no gerenciador se houver ID
                    if audio_info:
                        rel_path = Path(transcription_path).relative_to(AUDIO_DIR.parent)
                        audio_manager.update_transcription_status(
                            audio_info["id"], 
                            "ended",
                            str(rel_path)
                        )
                        
                    logger.success(f"Transcrição concluída: {output_path}")
                else:
                    # Se não gerou conteúdo, atualiza para status de erro
                    if audio_info:
                        audio_manager.update_transcription_status(audio_info["id"], "error")
                    logger.error(f"Falha na transcrição: nenhum conteúdo gerado")
            except Exception as e:
                # Em caso de erro, atualiza o status para "error"
                if audio_info:
                    audio_manager.update_transcription_status(audio_info["id"], "error")
                logger.exception(f"Erro na tarefa de transcrição: {str(e)}")
                
        # Adiciona a tarefa em segundo plano
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
    """
    Obtém o arquivo de transcrição (requer autenticação)
    """
    try:
        logger.info(f"Solicitação de obtenção de transcrição para ID: {file_id}")
        
        # Primeiro verifica no gerenciador de áudio
        audio_info = audio_manager.get_audio_info(file_id)
        
        if audio_info and audio_info.get("transcription_status") == "ended":
            transcription_path = AUDIO_DIR.parent / audio_info["transcription_path"]
            
            if transcription_path.exists():
                logger.debug(f"Transcrição encontrada no gerenciador: {transcription_path}")
                return FileResponse(
                    path=transcription_path,
                    media_type="text/markdown",
                    filename=transcription_path.name
                )
            else:
                logger.warning(f"Caminho de transcrição no gerenciador não existe: {transcription_path}")
        
        # Se não encontrou no gerenciador ou o status não é "ended", tenta encontrar o arquivo
        try:
            # Tenta encontrar o arquivo de áudio
            audio_file = TranscriptionService.find_audio_file(file_id)
            transcription_file = audio_file.with_suffix(".md")
            
            if not transcription_file.exists():
                logger.error(f"Transcrição não encontrada para: {file_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Transcrição não encontrada para: {file_id}"
                )
                
            logger.debug(f"Transcrição encontrada por busca de arquivo: {transcription_file}")
            
            # Se encontrou o arquivo, mas o status no gerenciador não está correto, atualiza-o
            if audio_info and audio_info.get("transcription_status") != "ended":
                rel_path = str(transcription_file.relative_to(AUDIO_DIR.parent))
                audio_manager.update_transcription_status(audio_info["id"], "ended", rel_path)
        except FileNotFoundError:
            # Tenta procurar a transcrição diretamente
            transcription_files = list(AUDIO_DIR.glob("**/*.md"))
            
            # Filtra por similaridade com o ID
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
                
            # Usa a transcrição com maior similaridade
            transcription_file = matching_transcriptions[0]
            logger.debug(f"Transcrição encontrada por busca direta: {transcription_file}")
            
            # Também atualiza o status no gerenciador se possível
            if audio_info:
                rel_path = str(transcription_file.relative_to(AUDIO_DIR.parent))
                audio_manager.update_transcription_status(audio_info["id"], "ended", rel_path)
        
        # Retorna o arquivo de transcrição
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


@app.get("/audio/transcription_status/{file_id}")
async def get_transcription_status(
        file_id: str,
        token_data: dict = Depends(verify_token)
):
    """
    Obtém o status atual da transcrição (requer autenticação)
    """
    try:
        logger.info(f"Solicitação de status de transcrição para ID: {file_id}")
        
        # Procura no gerenciador de áudio
        audio_info = audio_manager.get_audio_info(file_id)
        
        if not audio_info:
            logger.warning(f"Áudio não encontrado: {file_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Áudio não encontrado: {file_id}"
            )
        
        # Obtém o status da transcrição
        transcription_status = audio_info.get("transcription_status", "none")
        
        # Verifica se há caminho de transcrição para status "ended"
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


# Novos endpoints para SSE e status de download

@app.get("/audio/download-events")
async def download_events_stream(
    token: str = Query(None, description="Token de autenticação"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    Stream de eventos SSE para atualizações de download em tempo real
    """
    # Verificar autenticação
    auth_token = None
    if authorization:
        # Token vem do header Authorization
        if authorization.startswith("Bearer "):
            auth_token = authorization[7:]
    elif token:
        # Token vem do query parameter
        auth_token = token
    
    if not auth_token:
        raise HTTPException(status_code=403, detail="Token de autenticação necessário")
    
    try:
        # Verificar token
        verify_token_sync(auth_token)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Token inválido")
    
    client_id = str(uuid.uuid4())
    
    async def event_generator():
        try:
            # Conectar o cliente ao gerenciador SSE
            queue = await sse_manager.connect(client_id)
            
            while True:
                # Aguardar por eventos na fila
                event_data = await queue.get()
                yield event_data
                
        except asyncio.CancelledError:
            logger.info(f"Stream SSE cancelado para cliente {client_id}")
        finally:
            # Desconectar o cliente
            sse_manager.disconnect(client_id)
    
    return EventSourceResponse(event_generator())


@app.get("/audio/download-status/{audio_id}")
async def get_download_status(
    audio_id: str,
    token_data: dict = Depends(verify_token)
):
    """
    Obtém o status atual de um download específico
    """
    try:
        # Primeiro, verifica no gerenciador SSE (downloads em andamento)
        sse_status = sse_manager.get_download_status(audio_id)
        
        # Depois, verifica no gerenciador de áudio (dados persistidos)
        audio_info = audio_manager.get_audio_info(audio_id)
        
        if not audio_info and not sse_status:
            raise HTTPException(
                status_code=404,
                detail=f"Áudio não encontrado: {audio_id}"
            )
        
        # Combina informações de ambas as fontes
        status = {
            "audio_id": audio_id,
            "download_status": audio_info.get("download_status", "unknown") if audio_info else "unknown",
            "download_progress": audio_info.get("download_progress", 0) if audio_info else 0,
            "download_error": audio_info.get("download_error", "") if audio_info else ""
        }
        
        # Se há status SSE, ele tem prioridade (mais atualizado)
        if sse_status:
            status.update({
                "download_status": sse_status.get("status", status["download_status"]),
                "download_progress": sse_status.get("progress", status["download_progress"]),
                "live_updates": True
            })
        else:
            status["live_updates"] = False
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao obter status do download: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter status do download: {str(e)}"
        )


# Novos endpoints para gerenciamento da fila (Fase 3)

@app.get("/downloads/queue/status")
async def get_queue_status(
    token_data: dict = Depends(verify_token)
):
    """
    Obtém o status atual da fila de downloads
    """
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
    """
    Lista tasks na fila com filtros opcionais
    """
    try:
        if audio_id:
            tasks = await download_queue.get_tasks_by_audio_id(audio_id)
        else:
            async with download_queue.queue_lock:
                tasks = list(download_queue.tasks.values())
        
        # Filtrar por status se especificado
        if status:
            tasks = [task for task in tasks if task.status == status]
        
        # Converter para dict para serialização
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
    """
    Cancela um download específico na fila
    """
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
    """
    Força retry de um download falhado
    """
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
        
        # Resetar para fila
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
    """
    Remove tasks antigas da fila para limpeza
    """
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
