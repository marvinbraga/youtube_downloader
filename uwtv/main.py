# main.py
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Video Streaming API")

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração do diretório de vídeos
VIDEO_DIR = Path(__file__).parent.parent / "downloads"
VIDEO_DIR.mkdir(exist_ok=True)


def generate_video_stream(video_path: Path):
    """
    Gera um stream do arquivo de vídeo em chunks.
    Isso permite transmitir arquivos grandes de forma eficiente.
    """
    CHUNK_SIZE = 1024 * 1024  # 1MB por chunk

    try:
        with open(video_path, "rb") as video_file:
            while chunk := video_file.read(CHUNK_SIZE):
                yield chunk
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler o arquivo: {str(e)}")


@app.get("/videos")
async def list_videos():
    """Lista todos os vídeos disponíveis no diretório."""
    try:
        videos = [f.name for f in VIDEO_DIR.glob("*") if f.is_file()]
        return {"videos": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar vídeos: {str(e)}")


@app.get("/video/{video_name}")
async def stream_video(video_name: str):
    """
    Endpoint para streaming de vídeo.
    Retorna o vídeo como um stream de bytes com o content-type apropriado.
    """
    video_path = VIDEO_DIR / video_name

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    # Determina o content-type baseado na extensão do arquivo
    content_type = None
    if video_name.endswith('.mp4'):
        content_type = 'video/mp4'
    elif video_name.endswith('.webm'):
        content_type = 'video/webm'
    else:
        raise HTTPException(status_code=400, detail="Formato de vídeo não suportado")

    return StreamingResponse(
        generate_video_stream(video_path),
        media_type=content_type
    )
