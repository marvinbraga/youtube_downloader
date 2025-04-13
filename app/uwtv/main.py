# main.py
import os
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from loguru import logger

from app.models.video import TokenData, ClientAuth, SortOption
from app.models.audio import AudioDownloadRequest, TranscriptionRequest, TranscriptionResponse, TranscriptionProvider
from app.services.configs import video_mapping, AUDIO_DIR, audio_mapping
from app.services.files import scan_video_directory, generate_video_stream, scan_audio_directory
from app.services.managers import VideoStreamManager, AudioDownloadManager
from app.services.securities import AUTHORIZED_CLIENTS, create_access_token, verify_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.services.transcription.service import TranscriptionService

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
    Verifica se um áudio de um vídeo do YouTube já foi baixado (requer autenticação)
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
                logger.info(f"Áudio com ID '{youtube_id}' já existe no sistema")
                return {
                    "exists": True, 
                    "message": "Este áudio já foi baixado anteriormente",
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
    """
    try:
        logger.info(f"Solicitação de download de áudio: {request.url}")
        
        # Executa o download de forma assíncrona
        def download_task():
            try:
                audio_path = audio_manager.download_audio(str(request.url))
                logger.info(f"Download de áudio concluído para: {request.url} em {audio_path}")
            except Exception as e:
                logger.error(f"Erro no download assíncrono de áudio: {str(e)}")
        
        background_tasks.add_task(download_task)
        
        return {
            "status": "processando",
            "message": "O download do áudio foi iniciado em segundo plano",
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
                
            # Verifica se já existe transcrição
            if audio_info.get("has_transcription", False) and audio_info.get("transcription_path"):
                transcription_path = AUDIO_DIR.parent / audio_info["transcription_path"]
                if transcription_path.exists():
                    logger.info(f"Transcrição já existe: {transcription_path}")
                    return TranscriptionResponse(
                        file_id=request.file_id,
                        transcription_path=str(transcription_path),
                        status="success",
                        message="Transcrição já existe"
                    )
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
            
            # Se encontramos no sistema de arquivos mas não no gerenciador, atualizamos o gerenciador
            if audio_info and not audio_info.get("has_transcription", False):
                audio_manager.update_transcription_status(
                    audio_info["id"],
                    str(transcription_file.relative_to(AUDIO_DIR.parent))
                )
                
            return TranscriptionResponse(
                file_id=request.file_id,
                transcription_path=str(transcription_file),
                status="success",
                message="Transcrição já existe"
            )
            
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
                        audio_manager.update_transcription_status(audio_info["id"], str(rel_path))
                        
                    logger.success(f"Transcrição concluída: {output_path}")
                else:
                    logger.error(f"Falha na transcrição: nenhum conteúdo gerado")
            except Exception as e:
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
        
        if audio_info and audio_info.get("has_transcription", False):
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
        
        # Se não encontrou no gerenciador, tenta encontrar o arquivo de áudio e seu arquivo .md correspondente
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
