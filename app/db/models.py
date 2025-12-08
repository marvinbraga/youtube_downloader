# app/db/models.py
from datetime import datetime
from typing import Optional, List
import uuid

from sqlalchemy import String, Integer, DateTime, Text, Boolean, Float, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Folder(Base):
    """Modelo SQLAlchemy para pastas de organização"""
    __tablename__ = "folders"

    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("folders.id"), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Para UI (ex: "#FF5733")
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # Para UI (ex: "folder", "star")
    created_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    modified_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    # Relacionamentos
    parent: Mapped[Optional["Folder"]] = relationship(
        "Folder",
        remote_side=[id],
        back_populates="children",
        foreign_keys=[parent_id]
    )
    children: Mapped[List["Folder"]] = relationship(
        "Folder",
        back_populates="parent",
        foreign_keys=[parent_id]
    )
    audios: Mapped[List["Audio"]] = relationship("Audio", back_populates="folder")
    videos: Mapped[List["Video"]] = relationship("Video", back_populates="folder")

    def to_dict(self, include_children: bool = False, include_items: bool = False) -> dict:
        """Converte o modelo para dicionário"""
        result = {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "modified_date": self.modified_date.isoformat() if self.modified_date else None,
        }
        if include_children:
            result["children"] = [child.to_dict(include_children=True) for child in self.children]
        if include_items:
            result["audios"] = [audio.to_dict() for audio in self.audios]
            result["videos"] = [video.to_dict() for video in self.videos]
            result["item_count"] = len(self.audios) + len(self.videos)
        return result


class Audio(Base):
    """Modelo SQLAlchemy para áudios"""
    __tablename__ = "audios"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    youtube_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    directory: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="m4a")
    filesize: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Status de download
    download_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    download_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    download_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status de transcrição
    transcription_status: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    transcription_path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")

    # Organização
    folder_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("folders.id"), nullable=True, index=True)
    folder: Mapped[Optional["Folder"]] = relationship("Folder", back_populates="audios")

    # Metadados
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")  # JSON serializado
    created_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    modified_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    def to_dict(self) -> dict:
        """Converte o modelo para dicionário"""
        import json
        return {
            "id": self.id,
            "title": self.title,
            "name": self.name,
            "youtube_id": self.youtube_id,
            "url": self.url,
            "path": self.path,
            "directory": self.directory,
            "format": self.format,
            "filesize": self.filesize,
            "download_status": self.download_status,
            "download_progress": self.download_progress,
            "download_error": self.download_error,
            "transcription_status": self.transcription_status,
            "transcription_path": self.transcription_path,
            "folder_id": self.folder_id,
            "keywords": json.loads(self.keywords) if self.keywords else [],
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "modified_date": self.modified_date.isoformat() if self.modified_date else None,
        }


class Video(Base):
    """Modelo SQLAlchemy para vídeos"""
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    youtube_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    directory: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="mp4")
    filesize: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution: Mapped[str] = mapped_column(String(20), nullable=False, default="")

    # Status de download
    download_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    download_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    download_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status de transcrição
    transcription_status: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    transcription_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Organização
    folder_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("folders.id"), nullable=True, index=True)
    folder: Mapped[Optional["Folder"]] = relationship("Folder", back_populates="videos")

    # Metadados
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="youtube")
    created_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    modified_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    def to_dict(self) -> dict:
        """Converte o modelo para dicionário"""
        return {
            "id": self.id,
            "title": self.title,
            "name": self.name,
            "youtube_id": self.youtube_id,
            "url": self.url,
            "path": self.path,
            "directory": self.directory,
            "format": self.format,
            "filesize": self.filesize,
            "duration": self.duration,
            "resolution": self.resolution,
            "download_status": self.download_status,
            "download_progress": self.download_progress,
            "download_error": self.download_error,
            "transcription_status": self.transcription_status,
            "transcription_path": self.transcription_path,
            "folder_id": self.folder_id,
            "source": self.source,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "modified_date": self.modified_date.isoformat() if self.modified_date else None,
        }
