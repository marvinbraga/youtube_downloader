"""Integration tests for POST /audio/playlist and POST /video/playlist endpoints."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


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
    video_repo = MagicMock()
    video_repo.update_folder = AsyncMock()

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
