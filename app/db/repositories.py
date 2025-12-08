# app/db/repositories.py
import json
from datetime import datetime
from typing import Optional, List

from loguru import logger
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Audio, Video, Folder


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

    async def update_folder(self, audio_id: str, folder_id: Optional[str]) -> Optional[Audio]:
        """Atualiza a pasta de um áudio"""
        return await self.update(audio_id, folder_id=folder_id)

    async def get_by_folder(self, folder_id: Optional[str]) -> List[Audio]:
        """Lista áudios por pasta"""
        if folder_id is None:
            result = await self.session.execute(
                select(Audio).where(Audio.folder_id.is_(None))
            )
        else:
            result = await self.session.execute(
                select(Audio).where(Audio.folder_id == folder_id)
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

    async def update_folder(self, video_id: str, folder_id: Optional[str]) -> Optional[Video]:
        """Atualiza a pasta de um vídeo"""
        return await self.update(video_id, folder_id=folder_id)

    async def get_by_folder(self, folder_id: Optional[str]) -> List[Video]:
        """Lista vídeos por pasta"""
        if folder_id is None:
            result = await self.session.execute(
                select(Video).where(Video.folder_id.is_(None))
            )
        else:
            result = await self.session.execute(
                select(Video).where(Video.folder_id == folder_id)
            )
        return list(result.scalars().all())


class FolderRepository:
    """Repositório para operações de pasta no banco de dados"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, folder_id: str) -> Optional[Folder]:
        """Busca pasta pelo ID"""
        result = await self.session.execute(
            select(Folder).where(Folder.id == folder_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, order_by_name: bool = True) -> List[Folder]:
        """Lista todas as pastas"""
        query = select(Folder)
        if order_by_name:
            query = query.order_by(Folder.name)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_root_folders(self) -> List[Folder]:
        """Lista pastas raiz (sem parent)"""
        result = await self.session.execute(
            select(Folder).where(Folder.parent_id.is_(None)).order_by(Folder.name)
        )
        return list(result.scalars().all())

    async def get_children(self, folder_id: str) -> List[Folder]:
        """Lista subpastas de uma pasta"""
        result = await self.session.execute(
            select(Folder).where(Folder.parent_id == folder_id).order_by(Folder.name)
        )
        return list(result.scalars().all())

    async def create(self, folder: Folder) -> Folder:
        """Cria uma nova pasta"""
        self.session.add(folder)
        await self.session.flush()
        await self.session.refresh(folder)
        return folder

    async def update(self, folder_id: str, **kwargs) -> Optional[Folder]:
        """Atualiza uma pasta"""
        kwargs["modified_date"] = datetime.now()

        await self.session.execute(
            update(Folder).where(Folder.id == folder_id).values(**kwargs)
        )
        await self.session.flush()
        return await self.get_by_id(folder_id)

    async def delete(self, folder_id: str) -> bool:
        """Remove uma pasta"""
        result = await self.session.execute(
            delete(Folder).where(Folder.id == folder_id)
        )
        return result.rowcount > 0

    async def get_path(self, folder_id: str) -> List[Folder]:
        """Retorna o caminho completo da pasta (da raiz até a pasta)"""
        path = []
        current = await self.get_by_id(folder_id)

        while current:
            path.insert(0, current)
            if current.parent_id:
                current = await self.get_by_id(current.parent_id)
            else:
                current = None

        return path

    async def has_children(self, folder_id: str) -> bool:
        """Verifica se a pasta tem subpastas"""
        result = await self.session.execute(
            select(Folder.id).where(Folder.parent_id == folder_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def has_items(self, folder_id: str) -> bool:
        """Verifica se a pasta tem itens (áudios ou vídeos)"""
        audio_result = await self.session.execute(
            select(Audio.id).where(Audio.folder_id == folder_id).limit(1)
        )
        if audio_result.scalar_one_or_none():
            return True

        video_result = await self.session.execute(
            select(Video.id).where(Video.folder_id == folder_id).limit(1)
        )
        return video_result.scalar_one_or_none() is not None

    async def count_items(self, folder_id: str) -> dict:
        """Conta itens em uma pasta"""
        from sqlalchemy import func

        audio_result = await self.session.execute(
            select(func.count(Audio.id)).where(Audio.folder_id == folder_id)
        )
        video_result = await self.session.execute(
            select(func.count(Video.id)).where(Video.folder_id == folder_id)
        )

        audio_count = audio_result.scalar() or 0
        video_count = video_result.scalar() or 0

        return {
            "audios": audio_count,
            "videos": video_count,
            "total": audio_count + video_count
        }
