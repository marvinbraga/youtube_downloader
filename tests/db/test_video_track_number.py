"""Schema + repository contract for Video.track_number (playlist collection order).

JSON / column name: ``track_number`` (nullable INTEGER, 1-based playlist order).
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import (
    _apply_schema_migrations,
    _backfill_playlist_video_track_numbers,
)
from app.db.models import Base, Folder, Video
from app.db.repositories import VideoRepository

DOCUMENTARIES_FOLDER_ID = "9f8f3303-fbdd-4a6f-b337-d1a980e66d6c"
DOCUMENTARIES_FOLDER_NAME = "Documentários Importantes"


@pytest.mark.anyio
async def test_schema_migration_adds_videos_track_number_column():
    """``_apply_schema_migrations`` must ADD videos.track_number on legacy DBs.

    create_all is not enough: production SQLite already has a videos table, so
    the column is added the same way audios.track_number was (ALTER TABLE).
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Simulate a pre-feature DB even if the ORM already maps the column.
            pragma = await conn.exec_driver_sql("PRAGMA table_info(videos)")
            existing = {row[1] for row in pragma.fetchall()}
            if "track_number" in existing:
                await conn.exec_driver_sql(
                    "ALTER TABLE videos DROP COLUMN track_number"
                )
            await _apply_schema_migrations(conn)
            result = await conn.exec_driver_sql("PRAGMA table_info(videos)")
            cols = {row[1]: row for row in result.fetchall()}

        assert "track_number" in cols
        col_type, notnull = cols["track_number"][2], cols["track_number"][3]
        assert col_type.upper().startswith("INT")
        assert notnull == 0
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_video_repository_get_by_folder_orders_by_track_number_nulls_last():
    """Playlist items: track_number ASC, NULLS last, then created_date ASC."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _apply_schema_migrations(conn)

        t0 = datetime(2026, 1, 1, 12, 0, 0)
        async with session_factory() as session:
            folder = Folder(
                id=DOCUMENTARIES_FOLDER_ID,
                name=DOCUMENTARIES_FOLDER_NAME,
                kind="playlist",
            )
            session.add(folder)
            await session.flush()

            ep2 = Video(
                id="v-ep2",
                title="Ep 2",
                name="Ep 2",
                youtube_id="ep2aaaaaaaa",
                folder_id=folder.id,
                created_date=t0,
            )
            ep1 = Video(
                id="v-ep1",
                title="Ep 1",
                name="Ep 1",
                youtube_id="ep1aaaaaaaa",
                folder_id=folder.id,
                created_date=t0 + timedelta(seconds=30),
            )
            null_early = Video(
                id="v-null-early",
                title="Unnumbered early",
                name="Unnumbered early",
                youtube_id="nulleeeeeee",
                folder_id=folder.id,
                created_date=t0 + timedelta(seconds=5),
            )
            null_late = Video(
                id="v-null-late",
                title="Unnumbered late",
                name="Unnumbered late",
                youtube_id="nullllllate",
                folder_id=folder.id,
                created_date=t0 + timedelta(seconds=60),
            )
            ep2.track_number = 2
            ep1.track_number = 1
            session.add_all([ep2, ep1, null_early, null_late])
            await session.commit()

            repo = VideoRepository(session)
            ordered = await repo.get_by_folder(folder.id)

        assert [v.id for v in ordered] == [
            "v-ep1",
            "v-ep2",
            "v-null-early",
            "v-null-late",
        ]
        assert [v.track_number for v in ordered] == [1, 2, None, None]
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_backfill_assigns_playlist_track_numbers_by_created_date():
    """Unnumbered videos in kind=playlist folders get 1..n by created_date ASC."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _apply_schema_migrations(conn)

        t0 = datetime(2026, 1, 1, 12, 0, 0)
        async with session_factory() as session:
            folder = Folder(
                id=DOCUMENTARIES_FOLDER_ID,
                name=DOCUMENTARIES_FOLDER_NAME,
                kind="playlist",
            )
            session.add(folder)
            session.add_all(
                [
                    Video(
                        id="later",
                        title="Later",
                        name="Later",
                        youtube_id="lateraaaaaa",
                        folder_id=folder.id,
                        created_date=t0 + timedelta(seconds=10),
                    ),
                    Video(
                        id="earlier",
                        title="Earlier",
                        name="Earlier",
                        youtube_id="earlieraaaa",
                        folder_id=folder.id,
                        created_date=t0,
                    ),
                ]
            )
            await session.commit()

        async with engine.begin() as conn:
            await _backfill_playlist_video_track_numbers(conn)

        async with session_factory() as session:
            repo = VideoRepository(session)
            ordered = await repo.get_by_folder(DOCUMENTARIES_FOLDER_ID)

        assert [v.id for v in ordered] == ["earlier", "later"]
        assert [v.track_number for v in ordered] == [1, 2]
    finally:
        await engine.dispose()
