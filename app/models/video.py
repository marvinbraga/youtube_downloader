# app/models/video.py
from enum import Enum
from typing import Optional

from pydantic import BaseModel, HttpUrl


class TokenData(BaseModel):
    access_token: str
    token_type: str


class ClientAuth(BaseModel):
    client_id: str
    client_secret: str


class VideoSource(str, Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"


class VideoInfo(BaseModel):
    id: str
    name: str
    path: str
    type: str
    created_date: str
    modified_date: str
    size: int
    source: VideoSource
    youtube_url: Optional[HttpUrl] = None


class SortOption(str, Enum):
    TITLE = "title"
    DATE = "date"
    NONE = "none"
