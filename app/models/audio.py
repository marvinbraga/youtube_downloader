# app/models/audio.py
from enum import Enum
from typing import Literal, Optional, List

from pydantic import BaseModel, HttpUrl


class AudioSource(str, Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"


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
    """Request para download de playlist completa.

    Use com POST /audio/playlist (somente high_quality é relevante)
    ou POST /video/playlist (somente resolution é relevante).
    O endpoint de destino é o discriminador de mídia.
    """

    url: HttpUrl
    high_quality: bool = (
        False  # audio only; False por padrão para conservar banda em playlists
    )
    resolution: Literal["360p", "480p", "720p", "1080p", "1440p", "2160p", "best"] = (
        "1080p"  # video only
    )
    skip_existing: bool = True  # skip items that already exist in DB


class PlaylistTaskItem(BaseModel):
    """Representa um item enfileirado/iniciado durante o download de uma playlist"""

    item_id: Optional[str] = (
        None  # DB record ID (YouTube ID); None when registration failed
    )
    youtube_id: str  # YouTube video ID — always populated
    item_type: Literal["audio", "video"]
    task_id: Optional[str] = (
        None  # populated for audio (queue); None for video (background)
    )
    title: str
    url: HttpUrl
    skipped: bool = False  # True if item already existed and skip_existing=True


class PlaylistDownloadResponse(BaseModel):
    """Resposta do endpoint de playlist"""

    playlist_title: str
    playlist_url: HttpUrl
    folder_id: str
    total_items: int
    queued_items: int
    skipped_items: int
    failed_items: int = 0
    # TODO(review): add Field(ge=0) to counter fields - business-logic-reviewer, 2026-04-28, Severity: Low
    tasks: List[PlaylistTaskItem]
