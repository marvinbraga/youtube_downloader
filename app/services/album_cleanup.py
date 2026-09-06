"""Remove unavailable (error) album tracks after an audio playlist finishes."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from loguru import logger

from app.db.database import get_db_context
from app.db.repositories import AudioRepository, FolderRepository
from app.services.managers import AudioDownloadManager

POLL_INTERVAL_SECONDS = 2.0


def _status_is(audio: object, status: str) -> bool:
    return getattr(audio, "download_status", None) == status


def _any_downloading(audios: Iterable[object]) -> bool:
    return any(_status_is(audio, "downloading") for audio in audios)


async def cleanup_album_error_tracks(folder_id: str) -> int:
    """Delete error tracks in ``folder_id`` once no track is still downloading.

    Returns the number of tracks deleted. Returns 0 and deletes nothing while
    any track in the folder has ``download_status == "downloading"``.
    """
    async with get_db_context() as session:
        audios = await AudioRepository(session).get_by_folder(folder_id)

    if _any_downloading(audios):
        return 0

    error_ids = [audio.id for audio in audios if _status_is(audio, "error")]
    if not error_ids:
        return 0

    manager = AudioDownloadManager()
    deleted = 0
    for audio_id in error_ids:
        try:
            removed = await manager.delete_audio(audio_id)
        except Exception:  # noqa: BLE001 — continue remaining tracks
            logger.exception(
                "Failed to delete error track {} from album folder {}",
                audio_id,
                folder_id,
            )
            continue
        if removed:
            deleted += 1

    if deleted:
        album_name = folder_id
        async with get_db_context() as session:
            folder = await FolderRepository(session).get_by_id(folder_id)
            if folder is not None and getattr(folder, "name", None):
                album_name = folder.name
        logger.info(
            "Album {}: removed {} error tracks after playlist download",
            album_name,
            deleted,
        )
    return deleted


async def wait_and_cleanup_album_errors(
    folder_id: str,
    poll_interval: float = POLL_INTERVAL_SECONDS,
) -> int:
    """Poll until the album folder has no downloading tracks, then clean errors."""
    try:
        while True:
            async with get_db_context() as session:
                audios = await AudioRepository(session).get_by_folder(folder_id)
            if not _any_downloading(audios):
                break
            await asyncio.sleep(poll_interval)
        return await cleanup_album_error_tracks(folder_id)
    except Exception:  # noqa: BLE001 — detached task; log instead of raising
        logger.exception(
            "Album error-track cleanup failed for folder {}",
            folder_id,
        )
        return 0
