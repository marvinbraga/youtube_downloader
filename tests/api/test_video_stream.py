"""GET /video/stream/{id} must not 500 when Video.folder is not eager-loaded."""

from datetime import datetime
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.responses import Response

from app.db.models import Base, Folder, Video
from app.db.repositories import VideoRepository

YOUTUBE_ID = "GFvTSkCXEVg"
FOLDER_ID = "folder-docs-1"
REL_PATH = f"video/{YOUTUBE_ID}.mp4"


def test_stream_downloaded_video_does_not_500_when_folder_unloaded(client, tmp_path):
    """Reproduce stream_downloaded_video → get_by_external_id → to_dict()."""

    video_file = tmp_path / REL_PATH
    video_file.parent.mkdir(parents=True)
    video_file.write_bytes(b"fake-mp4")

    async def get_video_by_youtube_id(external_id: str):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with session_factory() as session:
                session.add(
                    Folder(
                        id=FOLDER_ID,
                        name="Documentários Importantes",
                        kind="playlist",
                        cover_url="https://i.ytimg.com/vi/GFvTSkCXEVg/hqdefault.jpg",
                    )
                )
                session.add(
                    Video(
                        id="vid-ep3",
                        title="Ep.3",
                        name="Ep.3",
                        youtube_id=YOUTUBE_ID,
                        external_id=YOUTUBE_ID,
                        folder_id=FOLDER_ID,
                        download_status="ready",
                        storage_backend="local",
                        path=REL_PATH,
                        created_date=datetime(2026, 1, 1),
                        modified_date=datetime(2026, 1, 1),
                    )
                )
                await session.commit()
            async with session_factory() as session:
                video = await VideoRepository(session).get_by_external_id(external_id)
                assert video is not None
                return video.to_dict()
        finally:
            await engine.dispose()

    with (
        patch(
            "app.uwtv.main.video_manager.get_video_by_youtube_id",
            new=get_video_by_youtube_id,
        ),
        patch("app.uwtv.main.DOWNLOADS_DIR", tmp_path),
        patch(
            "app.uwtv.main.StreamingResponse",
            return_value=Response(content=b"ok", media_type="video/mp4"),
        ),
    ):
        resp = client.get(f"/video/stream/{YOUTUBE_ID}")

    assert resp.status_code != 500, resp.text
    assert "MissingGreenlet" not in (resp.text or "")
    assert resp.status_code == 200
