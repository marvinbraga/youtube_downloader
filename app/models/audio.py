# app/models/audio.py
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, HttpUrl


class AudioSource(str, Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    READY = "ready"
    ERROR = "error"


class AudioInfo(BaseModel):
    id: str
    name: str
    path: str
    format: str
    created_date: str
    modified_date: str
    size: int
    source: AudioSource
    url: Optional[HttpUrl] = None
    duration: Optional[float] = None  # Duração em segundos


class AudioDownloadRequest(BaseModel):
    url: HttpUrl
    high_quality: bool = True


class VideoDownloadRequest(BaseModel):
    url: HttpUrl
    resolution: str = "1080p"  # 360p, 480p, 720p, 1080p, 1440p, 2160p, best


class TranscriptionProvider(str, Enum):
    GROQ = "groq"
    OPENAI = "openai"
    FAST = "fast"
    LOCAL = "local"


class TranscriptionRequest(BaseModel):
    file_id: str
    provider: TranscriptionProvider = TranscriptionProvider.GROQ
    language: str = "pt"


class TranscriptionResponse(BaseModel):
    file_id: str
    transcription_path: str
    segments: Optional[List[dict]] = None
    status: str = "success"
    message: str = "Transcrição concluída com sucesso"


class PlaylistDownloadRequest(BaseModel):
    """Request para download de playlist completa (áudio ou vídeo)"""

    url: HttpUrl
    high_quality: bool = False  # audio only
    resolution: str = (
        "1080p"  # video only; valid values: 360p 480p 720p 1080p 1440p 2160p best
    )
    skip_existing: bool = True  # skip items that already exist in DB


class PlaylistTaskItem(BaseModel):
    """Representa um item enfileirado/iniciado durante o download de uma playlist"""

    item_id: str  # audio_id or video_id (youtube_id)
    item_type: str  # "audio" or "video"
    task_id: Optional[str] = (
        None  # populated for audio (queue); None for video (background)
    )
    title: str
    url: str
    skipped: bool = False  # True if item already existed and skip_existing=True


class PlaylistDownloadResponse(BaseModel):
    """Resposta do endpoint de playlist"""

    playlist_title: str
    playlist_url: str
    folder_id: str
    total_items: int
    queued_items: int
    skipped_items: int
    tasks: List[PlaylistTaskItem]
