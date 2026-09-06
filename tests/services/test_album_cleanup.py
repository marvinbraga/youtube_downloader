"""Unit tests for album error-track cleanup after audio playlist download."""

from contextlib import ExitStack, asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.album_cleanup import (
    cleanup_album_error_tracks,
    wait_and_cleanup_album_errors,
)


def _track(audio_id: str, status: str) -> SimpleNamespace:
    return SimpleNamespace(id=audio_id, download_status=status)


def _db_and_repos(tracks: list, folder_name: str = "Best of 80's / 90's"):
    session = MagicMock()

    @asynccontextmanager
    async def mock_db():
        yield session

    audio_repo = MagicMock()
    audio_repo.get_by_folder = AsyncMock(return_value=tracks)
    folder_repo = MagicMock()
    folder_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id="folder-1", name=folder_name)
    )
    return mock_db, audio_repo, folder_repo


def _patch_cleanup(mock_db, audio_repo, folder_repo, delete_audio: AsyncMock):
    manager = MagicMock()
    manager.delete_audio = delete_audio
    stack = ExitStack()
    stack.enter_context(patch("app.services.album_cleanup.get_db_context", mock_db))
    stack.enter_context(
        patch("app.services.album_cleanup.AudioRepository", return_value=audio_repo)
    )
    stack.enter_context(
        patch("app.services.album_cleanup.FolderRepository", return_value=folder_repo)
    )
    stack.enter_context(
        patch("app.services.album_cleanup.AudioDownloadManager", return_value=manager)
    )
    return stack


@pytest.mark.anyio
async def test_cleanup_does_not_delete_while_any_track_downloading():
    tracks = [
        _track("ready-1", "ready"),
        _track("dl-1", "downloading"),
        _track("err-1", "error"),
    ]
    mock_db, audio_repo, folder_repo = _db_and_repos(tracks)
    delete_audio = AsyncMock(return_value=True)
    with _patch_cleanup(mock_db, audio_repo, folder_repo, delete_audio):
        deleted = await cleanup_album_error_tracks("folder-1")

    assert deleted == 0
    delete_audio.assert_not_called()


@pytest.mark.anyio
async def test_cleanup_deletes_only_error_tracks_ready_remain():
    tracks = [
        _track("ready-1", "ready"),
        _track("err-1", "error"),
        _track("err-2", "error"),
        _track("ready-2", "ready"),
    ]
    mock_db, audio_repo, folder_repo = _db_and_repos(tracks)
    delete_audio = AsyncMock(return_value=True)
    with _patch_cleanup(mock_db, audio_repo, folder_repo, delete_audio):
        deleted = await cleanup_album_error_tracks("folder-1")

    assert deleted == 2
    delete_audio.assert_any_await("err-1")
    delete_audio.assert_any_await("err-2")
    assert delete_audio.await_count == 2
    called_ids = [c.args[0] for c in delete_audio.await_args_list]
    assert "ready-1" not in called_ids
    assert "ready-2" not in called_ids


@pytest.mark.anyio
async def test_cleanup_noop_when_no_errors():
    tracks = [_track("ready-1", "ready"), _track("ready-2", "ready")]
    mock_db, audio_repo, folder_repo = _db_and_repos(tracks)
    delete_audio = AsyncMock(return_value=True)
    with _patch_cleanup(mock_db, audio_repo, folder_repo, delete_audio):
        deleted = await cleanup_album_error_tracks("folder-1")

    assert deleted == 0
    delete_audio.assert_not_called()


@pytest.mark.anyio
async def test_cleanup_noop_when_folder_empty():
    mock_db, audio_repo, folder_repo = _db_and_repos([])
    delete_audio = AsyncMock(return_value=True)
    with _patch_cleanup(mock_db, audio_repo, folder_repo, delete_audio):
        deleted = await cleanup_album_error_tracks("folder-1")

    assert deleted == 0
    delete_audio.assert_not_called()


@pytest.mark.anyio
async def test_cleanup_is_idempotent():
    first = [_track("err-1", "error"), _track("ready-1", "ready")]
    second = [_track("ready-1", "ready")]
    session = MagicMock()

    @asynccontextmanager
    async def mock_db():
        yield session

    audio_repo = MagicMock()
    audio_repo.get_by_folder = AsyncMock(side_effect=[first, second])
    folder_repo = MagicMock()
    folder_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id="folder-1", name="Baladas Top")
    )
    delete_audio = AsyncMock(return_value=True)
    with _patch_cleanup(mock_db, audio_repo, folder_repo, delete_audio):
        first_deleted = await cleanup_album_error_tracks("folder-1")
        second_deleted = await cleanup_album_error_tracks("folder-1")

    assert first_deleted == 1
    assert second_deleted == 0
    delete_audio.assert_awaited_once_with("err-1")


@pytest.mark.anyio
async def test_wait_and_cleanup_polls_until_idle_then_deletes_errors():
    downloading = [_track("a1", "downloading"), _track("a2", "error")]
    idle = [_track("a1", "ready"), _track("a2", "error")]
    session = MagicMock()

    @asynccontextmanager
    async def mock_db():
        yield session

    audio_repo = MagicMock()
    # wait loop: downloading -> idle; helper: idle again
    audio_repo.get_by_folder = AsyncMock(side_effect=[downloading, idle, idle])
    folder_repo = MagicMock()
    folder_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id="folder-1", name="Brasileiras")
    )
    delete_audio = AsyncMock(return_value=True)
    manager = MagicMock()
    manager.delete_audio = delete_audio
    with (
        patch("app.services.album_cleanup.get_db_context", mock_db),
        patch("app.services.album_cleanup.AudioRepository", return_value=audio_repo),
        patch("app.services.album_cleanup.FolderRepository", return_value=folder_repo),
        patch("app.services.album_cleanup.AudioDownloadManager", return_value=manager),
        patch(
            "app.services.album_cleanup.asyncio.sleep", new_callable=AsyncMock
        ) as sleep,
    ):
        deleted = await wait_and_cleanup_album_errors("folder-1", poll_interval=2.0)

    assert deleted == 1
    sleep.assert_awaited_once_with(2.0)
    delete_audio.assert_awaited_once_with("a2")
