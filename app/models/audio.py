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
