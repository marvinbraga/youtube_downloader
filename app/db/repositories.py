# app/db/repositories.py
import json
from datetime import datetime
from typing import Optional, List

from loguru import logger
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Audio, Video


class AudioRepository:
    """Repositório para operações de áudio no banco de dados"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, audio_id: str) -> Optional[Audio]:
        """Busca áudio pelo ID"""
        result = await self.session.execute(
            select(Audio).where(Audio.id == audio_id)
        )
        return result.scalar_one_or_none()

    async def get_by_youtube_id(self, youtube_id: str) -> Optional[Audio]:
        """Busca áudio pelo ID do YouTube"""
        result = await self.session.execute(
            select(Audio).where(Audio.youtube_id == youtube_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, order_by_date: bool = True) -> List[Audio]:
        """Lista todos os áudios"""
        query = select(Audio)
        if order_by_date:
            query = query.order_by(Audio.modified_date.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> List[Audio]:
        """Lista áudios por status de download"""
        result = await self.session.execute(
            select(Audio).where(Audio.download_status == status)
        )
        return list(result.scalars().all())

    async def create(self, audio: Audio) -> Audio:
        """Cria um novo áudio"""
        self.session.add(audio)
        await self.session.flush()
        await self.session.refresh(audio)
        return audio

    async def update(self, audio_id: str, **kwargs) -> Optional[Audio]:
        """Atualiza um áudio"""
        kwargs["modified_date"] = datetime.now()

        await self.session.execute(
            update(Audio).where(Audio.id == audio_id).values(**kwargs)
        )
        await self.session.flush()
        return await self.get_by_id(audio_id)

    async def delete(self, audio_id: str) -> bool:
        """Remove um áudio"""
        result = await self.session.execute(
            delete(Audio).where(Audio.id == audio_id)
        )
        return result.rowcount > 0

    async def update_download_status(
        self,
        audio_id: str,
        status: str,
        progress: int = None,
        error: str = None
    ) -> Optional[Audio]:
        """Atualiza o status de download de um áudio"""
        update_data = {
            "download_status": status,
            "modified_date": datetime.now()
        }
        if progress is not None:
            update_data["download_progress"] = progress
        if error is not None:
            update_data["download_error"] = error

        return await self.update(audio_id, **update_data)

    async def update_transcription_status(
        self,
        audio_id: str,
        status: str,
        transcription_path: str = None
    ) -> Optional[Audio]:
        """Atualiza o status de transcrição de um áudio"""
        update_data = {
            "transcription_status": status,
            "modified_date": datetime.now()
        }
        if transcription_path is not None:
            update_data["transcription_path"] = transcription_path

        return await self.update(audio_id, **update_data)

    async def complete_download(
        self,
        audio_id: str,
        path: str,
        directory: str,
        filesize: int
    ) -> Optional[Audio]:
        """Marca o download como concluído com os dados do arquivo"""
        return await self.update(
            audio_id,
            path=path,
            directory=directory,
            filesize=filesize,
            download_status="ready",
            download_progress=100
        )

    async def search_by_keyword(self, keyword: str) -> List[Audio]:
        """Busca áudios por palavra-chave no título ou keywords"""
        keyword_lower = keyword.lower()
        result = await self.session.execute(
            select(Audio).where(
                (Audio.title.ilike(f"%{keyword_lower}%")) |
                (Audio.keywords.ilike(f"%{keyword_lower}%"))
            )
        )
        return list(result.scalars().all())


class VideoRepository:
    """Repositório para operações de vídeo no banco de dados"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, video_id: str) -> Optional[Video]:
        """Busca vídeo pelo ID"""
        result = await self.session.execute(
            select(Video).where(Video.id == video_id)
        )
        return result.scalar_one_or_none()

    async def get_by_youtube_id(self, youtube_id: str) -> Optional[Video]:
        """Busca vídeo pelo ID do YouTube"""
        result = await self.session.execute(
            select(Video).where(Video.youtube_id == youtube_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, order_by_date: bool = True) -> List[Video]:
        """Lista todos os vídeos"""
        query = select(Video)
        if order_by_date:
            query = query.order_by(Video.modified_date.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> List[Video]:
        """Lista vídeos por status de download"""
        result = await self.session.execute(
            select(Video).where(Video.download_status == status)
        )
        return list(result.scalars().all())

    async def create(self, video: Video) -> Video:
        """Cria um novo vídeo"""
        self.session.add(video)
        await self.session.flush()
        await self.session.refresh(video)
        return video

    async def update(self, video_id: str, **kwargs) -> Optional[Video]:
        """Atualiza um vídeo"""
        kwargs["modified_date"] = datetime.now()

        await self.session.execute(
            update(Video).where(Video.id == video_id).values(**kwargs)
        )
        await self.session.flush()
        return await self.get_by_id(video_id)

    async def delete(self, video_id: str) -> bool:
        """Remove um vídeo"""
        result = await self.session.execute(
            delete(Video).where(Video.id == video_id)
        )
        return result.rowcount > 0

    async def update_download_status(
        self,
        video_id: str,
        status: str,
        progress: int = None,
        error: str = None
    ) -> Optional[Video]:
        """Atualiza o status de download de um vídeo"""
        update_data = {
            "download_status": status,
            "modified_date": datetime.now()
        }
        if progress is not None:
            update_data["download_progress"] = progress
        if error is not None:
            update_data["download_error"] = error

        return await self.update(video_id, **update_data)

    async def complete_download(
        self,
        video_id: str,
        path: str,
        directory: str,
        filesize: int,
        duration: float = None,
        resolution: str = None
    ) -> Optional[Video]:
        """Marca o download como concluído com os dados do arquivo"""
        update_data = {
            "path": path,
            "directory": directory,
            "filesize": filesize,
            "download_status": "ready",
            "download_progress": 100
        }
        if duration is not None:
            update_data["duration"] = duration
        if resolution is not None:
            update_data["resolution"] = resolution

        return await self.update(video_id, **update_data)

    async def update_transcription_status(
        self,
        video_id: str,
        status: str,
        transcription_path: str = None
    ) -> Optional[Video]:
        """Atualiza o status de transcrição de um vídeo"""
        update_data = {
            "transcription_status": status,
            "modified_date": datetime.now()
        }
        if transcription_path is not None:
            update_data["transcription_path"] = transcription_path

        return await self.update(video_id, **update_data)
