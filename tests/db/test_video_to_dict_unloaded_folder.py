"""Video.to_dict() must not lazy-load Folder under AsyncSession.

stream_downloaded_video → VideoDownloadManager.get_video_by_youtube_id →
VideoRepository.get_by_external_id (no joinedload) → Video.to_dict().
Accessing self.folder there raises sqlalchemy.exc.MissingGreenlet.
"""

from datetime import datetime

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload

from app.db.models import Base, Folder, Video
from app.db.repositories import VideoRepository

YOUTUBE_ID = "GFvTSkCXEVg"
FOLDER_ID = "folder-docs-1"
FOLDER_NAME = "Documentários Importantes"
FOLDER_COVER = "https://i.ytimg.com/vi/GFvTSkCXEVg/hqdefault.jpg"


async def _engine_and_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, session_factory


async def _seed_episode(session_factory) -> None:
    async with session_factory() as session:
        folder = Folder(
            id=FOLDER_ID,
            name=FOLDER_NAME,
            kind="playlist",
            cover_url=FOLDER_COVER,
        )
        session.add(folder)
        session.add(
            Video(
                id="vid-ep3",
                title="Ep.3",
                name="Ep.3",
                youtube_id=YOUTUBE_ID,
                external_id=YOUTUBE_ID,
                folder_id=folder.id,
                download_status="ready",
                storage_backend="local",
                path=f"video/{YOUTUBE_ID}.mp4",
                created_date=datetime(2026, 1, 1),
                modified_date=datetime(2026, 1, 1),
            )
        )
        await session.commit()


@pytest.mark.anyio
async def test_to_dict_does_not_lazy_load_unloaded_folder_or_raise_missing_greenlet():
    """Same load path as GET /video/stream/{id}: no joinedload on Video.folder."""
    engine, session_factory = await _engine_and_factory()
    try:
        await _seed_episode(session_factory)
        async with session_factory() as session:
            repo = VideoRepository(session)
            video = await repo.get_by_external_id(YOUTUBE_ID)
            assert video is not None
            assert video.folder_id == FOLDER_ID
            assert "folder" in sa_inspect(video).unloaded

            try:
                data = video.to_dict()
            except MissingGreenlet as exc:
                pytest.fail(
                    "Video.to_dict() must not lazy-load folder under AsyncSession: "
                    f"{exc}"
                )

            assert data["folder_id"] == FOLDER_ID
            assert data["folder_name"] is None
            assert data["folder_kind"] is None
            assert data["folder_cover_url"] is None
            assert "folder" in sa_inspect(video).unloaded
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_to_dict_emits_folder_fields_when_relationship_already_loaded():
    engine, session_factory = await _engine_and_factory()
    try:
        await _seed_episode(session_factory)
        async with session_factory() as session:
            result = await session.execute(
                select(Video)
                .where(Video.external_id == YOUTUBE_ID)
                .options(joinedload(Video.folder))
            )
            video = result.unique().scalar_one()
            assert "folder" not in sa_inspect(video).unloaded

            data = video.to_dict()

            assert data["folder_id"] == FOLDER_ID
            assert data["folder_name"] == FOLDER_NAME
            assert data["folder_kind"] == "playlist"
            assert data["folder_cover_url"] == FOLDER_COVER
    finally:
        await engine.dispose()
