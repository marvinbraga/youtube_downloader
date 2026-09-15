"""Integration tests for POST /audio/playlist and POST /video/playlist endpoints."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.configs import MAX_PLAYLIST_ENTRIES


SAMPLE_PLAYLIST_INFO = {
    "title": "Test Playlist",
    "webpage_url": "https://www.youtube.com/playlist?list=PLtest123",
    "entries": [
        {
            "id": "video1234567",
            "title": "Video 1",
            "url": "https://www.youtube.com/watch?v=video1234567",
        },
        {
            "id": "video7654321",
            "title": "Video 2",
            "url": "https://www.youtube.com/watch?v=video7654321",
        },
    ],
}

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLtest123"


def _entries(n: int):
    return [
        {
            "id": f"vid{i:011d}",
            "title": f"Video {i}",
            "url": f"https://www.youtube.com/watch?v=vid{i:011d}",
        }
        for i in range(n)
    ]


def _make_db_mock(folder_id="folder-uuid-123"):
    """Build async context manager mock for get_db_context."""
    session_mock = MagicMock()

    @asynccontextmanager
    async def mock_db():
        yield session_mock

    folder_repo = MagicMock()
    folder_repo.create = AsyncMock(return_value=MagicMock(id=folder_id))
    audio_repo = MagicMock()
    audio_repo.update_folder = AsyncMock()
    audio_repo.update = AsyncMock()
    video_repo = MagicMock()
    video_repo.update_folder = AsyncMock()
    video_repo.update = AsyncMock()

    return mock_db, folder_repo, audio_repo, video_repo


# ---------------------------------------------------------------------------
# POST /audio/playlist
# ---------------------------------------------------------------------------


def test_audio_playlist_happy_path_queues_all_entries(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(return_value=SAMPLE_PLAYLIST_INFO),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(side_effect=["audio-id-1", "audio-id-2"]),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(side_effect=["task-id-1", "task-id-2"]),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    body = resp.json()
    assert body["queued_items"] == 2
    assert body["skipped_items"] == 0
    assert body["failed_items"] == 0
    assert len(body["tasks"]) == 2
    assert body["tasks"][0]["item_type"] == "audio"
    assert body["tasks"][0]["skipped"] is False
    assert body["tasks"][0]["youtube_id"] == "video1234567"


def test_audio_playlist_non_playlist_url_raises_400(client):
    with patch(
        "app.uwtv.main.audio_manager.extract_playlist_info",
        new=AsyncMock(side_effect=ValueError("URL não parece ser uma playlist")),
    ):
        resp = client.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 400
    assert "playlist" in resp.json()["detail"].lower()


def test_audio_playlist_requires_authentication():
    from fastapi.testclient import TestClient
    from app.uwtv.main import app

    with TestClient(app) as c:
        resp = c.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code in (401, 403)


def test_audio_playlist_skip_existing_true_skips_known_entries(client):
    existing_audio = {"id": "existing-db-id", "download_status": "completed"}
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Test Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": [SAMPLE_PLAYLIST_INFO["entries"][0]],
                }
            ),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=existing_audio),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post(
            "/audio/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped_items"] == 1
    assert body["queued_items"] == 0
    assert body["tasks"][0]["skipped"] is True
    assert body["tasks"][0]["task_id"] is None


def test_audio_playlist_existing_with_error_status_is_not_skipped(client):
    existing_audio = {"id": "existing-db-id", "download_status": "error"}
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Test Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": [SAMPLE_PLAYLIST_INFO["entries"][0]],
                }
            ),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=existing_audio),
        ),
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value="new-audio-id"),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(return_value="task-id-1"),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post(
            "/audio/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped_items"] == 0
    assert body["queued_items"] == 1


def test_audio_playlist_register_failure_continues_remaining_entries(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(return_value=SAMPLE_PLAYLIST_INFO),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(side_effect=[Exception("DB error"), "audio-id-2"]),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(return_value="task-id-2"),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed_items"] == 1
    assert body["queued_items"] == 1
    assert len(body["tasks"]) == 2


def test_audio_playlist_playlist_title_truncated_at_255_chars(client):
    long_title = "A" * 300
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": long_title,
                    "webpage_url": PLAYLIST_URL,
                    "entries": [],
                }
            ),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    # folder_repo.create was called with a Folder whose name is 255 chars
    call_args = folder_repo.create.call_args
    folder_arg = call_args[0][0]
    assert len(folder_arg.name) == 255
    assert folder_arg.kind == "album"


def test_audio_playlist_sets_track_numbers_on_skip_existing(client):
    existing_audio = {
        "id": "existing-db-id",
        "download_status": "ready",
        "folder_id": None,
    }
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    audio_repo.update = AsyncMock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Test Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": [SAMPLE_PLAYLIST_INFO["entries"][0]],
                    "playlist_id": "PLtest123",
                }
            ),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=existing_audio),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post(
            "/audio/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    audio_repo.update.assert_called()
    kwargs = audio_repo.update.call_args.kwargs
    assert kwargs.get("folder_id") == "folder-uuid-123"
    assert kwargs.get("track_number") == 1


# ---------------------------------------------------------------------------
# POST /audio/download — playlist guard
# ---------------------------------------------------------------------------


def test_audio_download_playlist_url_returns_400(client):
    """A playlist URL sent to /audio/download is rejected with 400, not registered.

    The guard runs before the handler's broad ``except Exception`` block, so the
    HTTPException(400) must survive and not be re-wrapped as a 500.
    """
    with (
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(),
        ) as register_mock,
        patch("app.uwtv.main.download_queue.add_download", new=AsyncMock()) as add_mock,
    ):
        resp = client.post("/audio/download", json={"url": PLAYLIST_URL})

    assert resp.status_code == 400
    assert "/audio/playlist" in resp.json()["detail"]
    register_mock.assert_not_called()
    add_mock.assert_not_called()


def test_audio_download_single_video_with_list_param_is_allowed(client):
    """watch?v=X&list=Y is a single video and must NOT be blocked by the guard."""
    single_with_list = "https://www.youtube.com/watch?v=abc1234567a&list=PL123"
    with (
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value="audio-id-1"),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(return_value="task-id-1"),
        ),
    ):
        resp = client.post("/audio/download", json={"url": single_with_list})

    assert resp.status_code == 200
    body = resp.json()
    assert body["audio_id"] == "audio-id-1"
    assert body["task_id"] == "task-id-1"


SINGLE_WATCH_URL = "https://www.youtube.com/watch?v=abc1234567a"


def test_audio_download_without_folder_id_stays_avulso(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value="audio-id-1"),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(return_value="task-id-1"),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post("/audio/download", json={"url": SINGLE_WATCH_URL})

    assert resp.status_code == 200
    audio_repo.update_folder.assert_not_called()
    audio_repo.update.assert_not_called()
    folder_repo.get_by_id.assert_not_called()
    waiter.assert_not_called()


def test_audio_download_empty_folder_id_stays_avulso(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value="audio-id-1"),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(return_value="task-id-1"),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post(
            "/audio/download", json={"url": SINGLE_WATCH_URL, "folder_id": ""}
        )

    assert resp.status_code == 200
    audio_repo.update_folder.assert_not_called()
    audio_repo.update.assert_not_called()
    waiter.assert_not_called()


def test_audio_download_with_album_folder_id_assigns_folder(client):
    album_id = "album-folder-1"
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    album = MagicMock()
    album.id = album_id
    album.kind = "album"
    folder_repo.get_by_id = AsyncMock(return_value=album)
    existing_track = MagicMock()
    existing_track.track_number = 2
    audio_repo.get_by_folder = AsyncMock(return_value=[existing_track])
    with (
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value="audio-id-1"),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(return_value="task-id-1"),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post(
            "/audio/download",
            json={"url": SINGLE_WATCH_URL, "folder_id": album_id},
        )

    assert resp.status_code == 200
    folder_repo.get_by_id.assert_awaited_once_with(album_id)
    audio_repo.update.assert_called()
    kwargs = audio_repo.update.call_args.kwargs
    assert kwargs.get("folder_id") == album_id
    assert kwargs.get("track_number") == 3
    waiter.assert_not_called()


def test_audio_download_existing_audio_still_assigns_album_folder(client):
    album_id = "album-folder-1"
    existing_id = "already-in-db"
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    album = MagicMock()
    album.id = album_id
    album.kind = "album"
    folder_repo.get_by_id = AsyncMock(return_value=album)
    audio_repo.get_by_folder = AsyncMock(return_value=[])
    with (
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value=existing_id),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(return_value="task-id-1"),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post(
            "/audio/download",
            json={"url": SINGLE_WATCH_URL, "folder_id": album_id},
        )

    assert resp.status_code == 200
    assert resp.json()["audio_id"] == existing_id
    kwargs = audio_repo.update.call_args.kwargs
    assert kwargs.get("folder_id") == album_id
    assert kwargs.get("track_number") == 1


def test_audio_download_unknown_folder_id_returns_404(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    folder_repo.get_by_id = AsyncMock(return_value=None)
    add_mock = AsyncMock(return_value="task-id-1")
    with (
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value="audio-id-1"),
        ),
        patch("app.uwtv.main.download_queue.add_download", add_mock),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post(
            "/audio/download",
            json={"url": SINGLE_WATCH_URL, "folder_id": "missing-folder"},
        )

    assert resp.status_code == 404
    assert "não encontrada" in resp.json()["detail"].lower()
    audio_repo.update.assert_not_called()
    audio_repo.update_folder.assert_not_called()
    add_mock.assert_not_called()
    waiter.assert_not_called()


def test_audio_download_non_album_folder_returns_400(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    generic = MagicMock()
    generic.id = "folder-not-album"
    generic.kind = "folder"
    folder_repo.get_by_id = AsyncMock(return_value=generic)
    add_mock = AsyncMock(return_value="task-id-1")
    with (
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value="audio-id-1"),
        ),
        patch("app.uwtv.main.download_queue.add_download", add_mock),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post(
            "/audio/download",
            json={"url": SINGLE_WATCH_URL, "folder_id": "folder-not-album"},
        )

    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "álbum" in detail or "album" in detail
    audio_repo.update.assert_not_called()
    add_mock.assert_not_called()
    waiter.assert_not_called()


# ---------------------------------------------------------------------------
# POST /video/playlist
# ---------------------------------------------------------------------------


def test_video_playlist_happy_path_schedules_background_task(client):
    mock_db, folder_repo, _, video_repo = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.video_manager.extract_playlist_info",
            new=AsyncMock(return_value=SAMPLE_PLAYLIST_INFO),
        ),
        patch(
            "app.uwtv.main.video_manager.get_video_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.uwtv.main.video_manager.register_video_for_download",
            new=AsyncMock(side_effect=["vid-id-1", "vid-id-2"]),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    ):
        resp = client.post("/video/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    body = resp.json()
    assert body["queued_items"] == 2
    assert body["skipped_items"] == 0
    assert body["failed_items"] == 0


def test_video_playlist_no_background_task_when_all_entries_skipped(client):
    existing_video = {"id": "existing-vid-db-id", "download_status": "completed"}
    mock_db, folder_repo, _, video_repo = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.video_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Test Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": [SAMPLE_PLAYLIST_INFO["entries"][0]],
                }
            ),
        ),
        patch(
            "app.uwtv.main.video_manager.get_video_by_youtube_id",
            new=AsyncMock(return_value=existing_video),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    ):
        resp = client.post(
            "/video/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["queued_items"] == 0
    assert body["skipped_items"] == 1


def test_video_playlist_propagates_resolution_to_register(client):
    mock_db, folder_repo, _, video_repo = _make_db_mock()
    register_mock = AsyncMock(return_value="vid-id-1")
    with (
        patch(
            "app.uwtv.main.video_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Test Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": [SAMPLE_PLAYLIST_INFO["entries"][0]],
                }
            ),
        ),
        patch(
            "app.uwtv.main.video_manager.get_video_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.uwtv.main.video_manager.register_video_for_download", new=register_mock
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    ):
        resp = client.post(
            "/video/playlist", json={"url": PLAYLIST_URL, "resolution": "720p"}
        )

    assert resp.status_code == 200
    register_mock.assert_called_once_with(
        "https://www.youtube.com/watch?v=video1234567",
        resolution="720p",
    )


def test_video_playlist_skip_existing_true_skips_known_videos(client):
    existing_video = {"id": "existing-vid-db-id", "download_status": "completed"}
    mock_db, folder_repo, _, video_repo = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.video_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Test Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": [SAMPLE_PLAYLIST_INFO["entries"][0]],
                }
            ),
        ),
        patch(
            "app.uwtv.main.video_manager.get_video_by_youtube_id",
            new=AsyncMock(return_value=existing_video),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    ):
        resp = client.post(
            "/video/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["tasks"][0]["item_type"] == "video"
    assert body["tasks"][0]["skipped"] is True


def test_video_playlist_non_playlist_url_raises_400(client):
    with patch(
        "app.uwtv.main.video_manager.extract_playlist_info",
        new=AsyncMock(side_effect=ValueError("URL não parece ser uma playlist")),
    ):
        resp = client.post("/video/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 400


def test_audio_playlist_max_entries_limit_returns_400(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Huge Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": _entries(MAX_PLAYLIST_ENTRIES + 1),
                }
            ),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "máximo" in detail
    assert str(MAX_PLAYLIST_ENTRIES) in detail


def test_video_playlist_max_entries_limit_returns_400(client):
    mock_db, folder_repo, _, video_repo = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.video_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Huge Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": _entries(MAX_PLAYLIST_ENTRIES + 1),
                }
            ),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    ):
        resp = client.post("/video/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "máximo" in detail
    assert str(MAX_PLAYLIST_ENTRIES) in detail


def test_audio_playlist_schedules_waiter_after_enqueue(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(return_value=SAMPLE_PLAYLIST_INFO),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(side_effect=["audio-id-1", "audio-id-2"]),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(side_effect=["task-id-1", "task-id-2"]),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    waiter.assert_called_once_with("folder-uuid-123")


def test_audio_playlist_schedules_waiter_when_queued_items_zero(client):
    existing_audio = {"id": "existing-db-id", "download_status": "ready"}
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Test Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": [SAMPLE_PLAYLIST_INFO["entries"][0]],
                }
            ),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=existing_audio),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post(
            "/audio/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    assert resp.json()["queued_items"] == 0
    waiter.assert_called_once_with("folder-uuid-123")


def test_audio_playlist_does_not_schedule_waiter_when_over_max(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Huge Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": _entries(MAX_PLAYLIST_ENTRIES + 1),
                }
            ),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 400
    waiter.assert_not_called()
    folder_repo.create.assert_not_called()


def test_video_playlist_does_not_schedule_album_waiter(client):
    mock_db, folder_repo, _, video_repo = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.video_manager.extract_playlist_info",
            new=AsyncMock(return_value=SAMPLE_PLAYLIST_INFO),
        ),
        patch(
            "app.uwtv.main.video_manager.get_video_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.uwtv.main.video_manager.register_video_for_download",
            new=AsyncMock(side_effect=["vid-id-1", "vid-id-2"]),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
        patch(
            "app.uwtv.main.wait_and_cleanup_album_errors", new_callable=AsyncMock
        ) as waiter,
    ):
        resp = client.post("/video/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    waiter.assert_not_called()


def test_audio_playlist_at_max_entries_is_accepted(client):
    mock_db, folder_repo, audio_repo, _ = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.audio_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Full Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": _entries(MAX_PLAYLIST_ENTRIES),
                }
            ),
        ),
        patch(
            "app.uwtv.main.audio_manager.get_audio_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.uwtv.main.audio_manager.register_audio_for_download",
            new=AsyncMock(return_value="audio-id"),
        ),
        patch(
            "app.uwtv.main.download_queue.add_download",
            new=AsyncMock(return_value="task-id"),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.post("/audio/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    body = resp.json()
    assert body["queued_items"] == MAX_PLAYLIST_ENTRIES
    assert body["failed_items"] == 0


def test_video_playlist_at_max_entries_is_accepted(client):
    mock_db, folder_repo, _, video_repo = _make_db_mock()
    with (
        patch(
            "app.uwtv.main.video_manager.extract_playlist_info",
            new=AsyncMock(
                return_value={
                    "title": "Full Playlist",
                    "webpage_url": PLAYLIST_URL,
                    "entries": _entries(MAX_PLAYLIST_ENTRIES),
                }
            ),
        ),
        patch(
            "app.uwtv.main.video_manager.get_video_by_youtube_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.uwtv.main.video_manager.register_video_for_download",
            new=AsyncMock(return_value="vid-id"),
        ),
        patch(
            "app.uwtv.main.video_manager.download_video_with_status_async",
            new=AsyncMock(),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    ):
        resp = client.post("/video/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    body = resp.json()
    assert body["queued_items"] == MAX_PLAYLIST_ENTRIES
    assert body["failed_items"] == 0


# ---------------------------------------------------------------------------
# POST /video/download — playlist guard
# ---------------------------------------------------------------------------

# Mirrors the audio single-download guard in download_audio (~main.py:1011):
# "URL de playlist detectada. Use o endpoint POST /audio/playlist para baixar playlists."
VIDEO_DOWNLOAD_PLAYLIST_DETAIL = (
    "URL de playlist detectada. Use o endpoint POST /video/playlist "
    "para baixar playlists."
)

# Confirmed production bug: playlist-only URL accepted by POST /video/download.
PRODUCTION_VIDEO_PLAYLIST_URL = (
    "https://www.youtube.com/playlist?list=PLae_TRAJztAYURYktDd-O03VaSqQd6xr8"
)


@pytest.mark.parametrize(
    "playlist_url",
    [
        PLAYLIST_URL,
        PRODUCTION_VIDEO_PLAYLIST_URL,
        "https://youtube.com/playlist?list=PL123",
    ],
)
def test_video_download_playlist_url_returns_400(client, playlist_url):
    """A playlist URL sent to /video/download is rejected with 400, not registered.

    The guard must run before the handler's broad ``except Exception`` block, so
    HTTPException(400) survives and is not re-wrapped as a 500. yt-dlp must not
    start (register + background download stay uncalled).
    """
    with (
        patch(
            "app.uwtv.main.video_manager.register_video_for_download",
            new=AsyncMock(return_value="should-not-register"),
        ) as register_mock,
        patch(
            "app.uwtv.main.video_manager.download_video_with_status_async",
            new=AsyncMock(),
        ) as download_mock,
    ):
        resp = client.post("/video/download", json={"url": playlist_url})

    assert resp.status_code == 400
    assert resp.json()["detail"] == VIDEO_DOWNLOAD_PLAYLIST_DETAIL
    register_mock.assert_not_called()
    download_mock.assert_not_called()


def test_video_download_single_video_with_list_param_is_allowed(client):
    """watch?v=X&list=Y is a single video and must NOT be blocked by the guard."""
    single_with_list = "https://www.youtube.com/watch?v=abc1234567a&list=PL123"
    with (
        patch(
            "app.uwtv.main.video_manager.register_video_for_download",
            new=AsyncMock(return_value="vid-id-1"),
        ) as register_mock,
        patch(
            "app.uwtv.main.video_manager.download_video_with_status_async",
            new=AsyncMock(),
        ),
    ):
        resp = client.post("/video/download", json={"url": single_with_list})

    assert resp.status_code == 200
    body = resp.json()
    assert body["video_id"] == "vid-id-1"
    register_mock.assert_awaited()


def test_video_download_plain_single_video_is_allowed(client):
    """A watch URL without list= is a single video and must still be accepted."""
    single_url = "https://www.youtube.com/watch?v=abc1234567a"
    with (
        patch(
            "app.uwtv.main.video_manager.register_video_for_download",
            new=AsyncMock(return_value="vid-id-1"),
        ),
        patch(
            "app.uwtv.main.video_manager.download_video_with_status_async",
            new=AsyncMock(),
        ),
    ):
        resp = client.post("/video/download", json={"url": single_url})

    assert resp.status_code == 200
    assert resp.json()["video_id"] == "vid-id-1"
