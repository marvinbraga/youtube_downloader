"""Tests for album identification (audio playlists) and GET /albums endpoints."""

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.uwtv.main import app


PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLtest123"

SAMPLE_PLAYLIST_INFO = {
    "title": "Best Of Jazz",
    "webpage_url": PLAYLIST_URL,
    "thumbnail": "https://i.ytimg.com/vi/video1234567/hqdefault.jpg",
    "uploader": "Jazz Channel",
    "playlist_id": "PLtest123",
    "entries": [
        {
            "id": "video1234567",
            "title": "Track 1",
            "url": "https://www.youtube.com/watch?v=video1234567",
        },
        {
            "id": "video7654321",
            "title": "Track 2",
            "url": "https://www.youtube.com/watch?v=video7654321",
        },
    ],
}


def _make_db_mock(folder_id="album-folder-1"):
    session_mock = MagicMock()

    @asynccontextmanager
    async def mock_db():
        yield session_mock

    folder_repo = MagicMock()
    created = MagicMock(id=folder_id)
    folder_repo.create = AsyncMock(return_value=created)
    audio_repo = MagicMock()
    audio_repo.update = AsyncMock()
    audio_repo.update_folder = AsyncMock()
    return mock_db, folder_repo, audio_repo


def test_audio_playlist_creates_folder_as_album(client):
    mock_db, folder_repo, audio_repo = _make_db_mock()
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
    folder_arg = folder_repo.create.call_args[0][0]
    assert folder_arg.kind == "album"
    assert folder_arg.icon == "playlist"
    assert folder_arg.description == "Playlist"
    assert folder_arg.source_url == PLAYLIST_URL
    assert folder_arg.external_playlist_id == "PLtest123"
    assert folder_arg.cover_url == SAMPLE_PLAYLIST_INFO["thumbnail"]
    assert folder_arg.artist == "Jazz Channel"

    # track_number 1-based assigned on register path
    update_calls = audio_repo.update.call_args_list
    assert any(
        c.kwargs.get("track_number") == 1 or (len(c.args) > 1 and False)
        for c in update_calls
    )
    track_numbers = [
        c.kwargs.get("track_number") for c in update_calls if "track_number" in c.kwargs
    ]
    assert track_numbers == [1, 2]


def test_video_playlist_creates_folder_as_playlist_not_album(client):
    mock_db, folder_repo, _ = _make_db_mock(folder_id="video-pl-1")
    video_repo = MagicMock()
    video_repo.update_folder = AsyncMock()
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
            new=AsyncMock(side_effect=["vid-1", "vid-2"]),
        ),
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    ):
        resp = client.post("/video/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    folder_arg = folder_repo.create.call_args[0][0]
    assert folder_arg.kind == "playlist"
    assert folder_arg.kind != "album"


def _folder_mock(
    folder_id="alb-1",
    kind="album",
    name="Best Of Jazz",
    artist="Jazz Channel",
    cover_url="https://example.com/cover.jpg",
):
    f = MagicMock()
    f.id = folder_id
    f.kind = kind
    f.name = name
    f.artist = artist
    f.cover_url = cover_url
    f.source_url = PLAYLIST_URL
    f.external_playlist_id = "PLtest123"
    f.parent_id = None
    f.description = "Playlist"
    f.color = None
    f.icon = "playlist"
    f.created_date = datetime(2026, 1, 1)
    f.modified_date = datetime(2026, 1, 2)
    f.to_dict.return_value = {
        "id": folder_id,
        "name": name,
        "parent_id": None,
        "description": "Playlist",
        "color": None,
        "icon": "playlist",
        "kind": kind,
        "source_url": PLAYLIST_URL,
        "external_playlist_id": "PLtest123",
        "cover_url": cover_url,
        "artist": artist,
        "created_date": "2026-01-01T00:00:00",
        "modified_date": "2026-01-02T00:00:00",
    }
    return f


def test_list_albums_returns_only_albums_with_counts(client):
    album = _folder_mock()
    folder_repo = MagicMock()
    folder_repo.get_albums = AsyncMock(return_value=[album])
    folder_repo.count_items = AsyncMock(
        return_value={"audios": 2, "videos": 0, "total": 2}
    )
    folder_repo.count_ready_audios = AsyncMock(return_value=1)

    @asynccontextmanager
    async def mock_db():
        yield MagicMock()

    with (
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
    ):
        resp = client.get("/albums")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["kind"] == "album"
    assert body[0]["track_count"] == 2
    assert body[0]["ready_count"] == 1
    assert body[0]["artist"] == "Jazz Channel"
    assert body[0]["name"] == "Best Of Jazz"


def test_get_album_detail_returns_ordered_tracks(client):
    album = _folder_mock()
    track1 = MagicMock()
    track1.to_dict.return_value = {
        "id": "a1",
        "title": "Track 1",
        "name": "Track 1",
        "track_number": 1,
        "download_status": "ready",
        "youtube_id": "video1234567",
    }
    track2 = MagicMock()
    track2.to_dict.return_value = {
        "id": "a2",
        "title": "Track 2",
        "name": "Track 2",
        "track_number": 2,
        "download_status": "downloading",
        "youtube_id": "video7654321",
    }

    folder_repo = MagicMock()
    folder_repo.get_by_id = AsyncMock(return_value=album)
    folder_repo.count_items = AsyncMock(
        return_value={"audios": 2, "videos": 0, "total": 2}
    )
    folder_repo.count_ready_audios = AsyncMock(return_value=1)
    audio_repo = MagicMock()
    audio_repo.get_by_folder = AsyncMock(return_value=[track1, track2])

    @asynccontextmanager
    async def mock_db():
        yield MagicMock()

    with (
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
    ):
        resp = client.get("/albums/alb-1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "alb-1"
    assert body["kind"] == "album"
    assert body["track_count"] == 2
    assert body["ready_count"] == 1
    assert len(body["tracks"]) == 2
    assert body["tracks"][0]["track_number"] == 1
    assert body["tracks"][1]["download_status"] == "downloading"


def test_get_album_rejects_non_album_folder(client):
    folder = _folder_mock(kind="folder", name="Normal")
    folder_repo = MagicMock()
    folder_repo.get_by_id = AsyncMock(return_value=folder)

    @asynccontextmanager
    async def mock_db():
        yield MagicMock()

    with (
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
    ):
        resp = client.get("/albums/alb-1")

    assert resp.status_code == 404
    assert (
        "álbum" in resp.json()["detail"].lower()
        or "album" in resp.json()["detail"].lower()
    )


def test_get_album_not_found(client):
    folder_repo = MagicMock()
    folder_repo.get_by_id = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_db():
        yield MagicMock()

    with (
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
    ):
        resp = client.get("/albums/missing")

    assert resp.status_code == 404


def test_albums_require_authentication():
    with TestClient(app) as c:
        assert c.get("/albums").status_code in (401, 403)
        assert c.get("/albums/x").status_code in (401, 403)


def test_folder_to_dict_includes_album_fields():
    from app.db.models import Folder

    folder = Folder(
        id="f1",
        name="Album X",
        kind="album",
        source_url=PLAYLIST_URL,
        external_playlist_id="PLtest123",
        cover_url="https://example.com/c.jpg",
        artist="Artist",
        description="Playlist",
        icon="playlist",
    )
    data = folder.to_dict()
    assert data["kind"] == "album"
    assert data["source_url"] == PLAYLIST_URL
    assert data["external_playlist_id"] == "PLtest123"
    assert data["cover_url"] == "https://example.com/c.jpg"
    assert data["artist"] == "Artist"


def test_audio_to_dict_includes_track_number():
    from app.db.models import Audio

    audio = Audio(
        id="a1",
        title="T",
        name="T",
        track_number=3,
    )
    data = audio.to_dict()
    assert data["track_number"] == 3
