"""Video playlists as a collection/series (not Álbuns).

JSON field names (frontend contract):
  - track_number: int | null  (1-based playlist order)
  - folder_id: str | null
  - folder_name: str | null
  - folder_kind: "playlist" | "folder" | "album" | null
"""

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models import Folder, Video

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLtest123"
DOCUMENTARIES_FOLDER_ID = "9f8f3303-fbdd-4a6f-b337-d1a980e66d6c"
DOCUMENTARIES_FOLDER_NAME = "Documentários Importantes"

SAMPLE_PLAYLIST_INFO = {
    "title": DOCUMENTARIES_FOLDER_NAME,
    "webpage_url": PLAYLIST_URL,
    "playlist_id": "PLtest123",
    "entries": [
        {
            "id": "video1234567",
            "title": "Ep 1",
            "url": "https://www.youtube.com/watch?v=video1234567",
        },
        {
            "id": "video7654321",
            "title": "Ep 2",
            "url": "https://www.youtube.com/watch?v=video7654321",
        },
        {
            "id": "video0000003",
            "title": "Ep 3",
            "url": "https://www.youtube.com/watch?v=video0000003",
        },
    ],
}


def _make_db_mock(folder_id=DOCUMENTARIES_FOLDER_ID):
    session_mock = MagicMock()

    @asynccontextmanager
    async def mock_db():
        yield session_mock

    folder_repo = MagicMock()
    folder_repo.create = AsyncMock(return_value=MagicMock(id=folder_id))
    video_repo = MagicMock()
    video_repo.update_folder = AsyncMock()
    video_repo.update = AsyncMock()
    return mock_db, folder_repo, video_repo


def _track_numbers_from_update(video_repo) -> list:
    return [
        c.kwargs.get("track_number")
        for c in video_repo.update.call_args_list
        if "track_number" in c.kwargs
    ]


def _folder_mock(
    folder_id=DOCUMENTARIES_FOLDER_ID,
    kind="playlist",
    name=DOCUMENTARIES_FOLDER_NAME,
):
    f = MagicMock()
    f.id = folder_id
    f.kind = kind
    f.name = name
    f.artist = None
    f.cover_url = None
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
        "cover_url": None,
        "artist": None,
        "created_date": "2026-01-01T00:00:00",
        "modified_date": "2026-01-02T00:00:00",
    }
    return f


def _patch_video_playlist(mock_db, folder_repo, video_repo, **manager_patches):
    patches = {
        "extract": patch(
            "app.uwtv.main.video_manager.extract_playlist_info",
            new=AsyncMock(
                return_value=manager_patches.get("playlist_info", SAMPLE_PLAYLIST_INFO)
            ),
        ),
        "get_existing": patch(
            "app.uwtv.main.video_manager.get_video_by_youtube_id",
            new=manager_patches.get(
                "get_video_by_youtube_id", AsyncMock(return_value=None)
            ),
        ),
        "register": patch(
            "app.uwtv.main.video_manager.register_video_for_download",
            new=manager_patches.get(
                "register",
                AsyncMock(side_effect=["vid-id-1", "vid-id-2", "vid-id-3"]),
            ),
        ),
        "download": patch(
            "app.uwtv.main.video_manager.download_video_with_status_async",
            new=AsyncMock(),
        ),
        "db": patch("app.uwtv.main.get_db_context", mock_db),
        "folders": patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        "videos": patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    }
    return patches


# ---------------------------------------------------------------------------
# Video.to_dict — collection fields
# ---------------------------------------------------------------------------


def test_video_to_dict_includes_track_number_null_by_default():
    video = Video(id="v1", title="T", name="T")
    data = video.to_dict()
    assert "track_number" in data
    assert data["track_number"] is None


def test_video_to_dict_includes_assigned_track_number():
    video = Video(id="v1", title="T", name="T")
    video.track_number = 3
    data = video.to_dict()
    assert data["track_number"] == 3


def test_video_to_dict_includes_folder_name_and_kind_for_playlist():
    folder = Folder(
        id=DOCUMENTARIES_FOLDER_ID,
        name=DOCUMENTARIES_FOLDER_NAME,
        kind="playlist",
    )
    video = Video(
        id="v1",
        title="Ep 1",
        name="Ep 1",
        folder_id=folder.id,
    )
    video.folder = folder
    video.track_number = 1
    data = video.to_dict()
    assert data["folder_id"] == DOCUMENTARIES_FOLDER_ID
    assert data["track_number"] == 1
    assert data["folder_name"] == DOCUMENTARIES_FOLDER_NAME
    assert data["folder_kind"] == "playlist"


def test_video_to_dict_folder_collection_fields_null_when_unfiled():
    video = Video(id="v1", title="Avulso", name="Avulso")
    data = video.to_dict()
    assert data["folder_id"] is None
    assert "folder_name" in data
    assert "folder_kind" in data
    assert data["folder_name"] is None
    assert data["folder_kind"] is None


# ---------------------------------------------------------------------------
# POST /video/playlist — track_number from entry order
# ---------------------------------------------------------------------------


def test_video_playlist_assigns_sequential_track_numbers_in_playlist_order(client):
    mock_db, folder_repo, video_repo = _make_db_mock()
    patches = _patch_video_playlist(mock_db, folder_repo, video_repo)
    with (
        patches["extract"],
        patches["get_existing"],
        patches["register"],
        patches["download"],
        patches["db"],
        patches["folders"],
        patches["videos"],
    ):
        resp = client.post("/video/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    assert resp.json()["queued_items"] == 3
    assert _track_numbers_from_update(video_repo) == [1, 2, 3]
    for call in video_repo.update.call_args_list:
        if "track_number" in call.kwargs:
            assert call.kwargs.get("folder_id") == DOCUMENTARIES_FOLDER_ID


def test_video_playlist_skip_existing_sets_track_number_in_playlist_order(client):
    """Skipped existing videos that land in the playlist folder get track_number.

    Matches audio: always write track_number from enumerate(entries, start=1);
    set folder_id when the existing row is unfiled.
    """
    existing_video = {
        "id": "existing-vid-db-id",
        "download_status": "completed",
        "folder_id": None,
    }
    mock_db, folder_repo, video_repo = _make_db_mock()
    patches = _patch_video_playlist(
        mock_db,
        folder_repo,
        video_repo,
        playlist_info={
            **SAMPLE_PLAYLIST_INFO,
            "entries": SAMPLE_PLAYLIST_INFO["entries"][:1],
        },
        get_video_by_youtube_id=AsyncMock(return_value=existing_video),
    )
    with (
        patches["extract"],
        patches["get_existing"],
        patches["register"],
        patches["download"],
        patches["db"],
        patches["folders"],
        patches["videos"],
    ):
        resp = client.post(
            "/video/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    assert resp.json()["skipped_items"] == 1
    video_repo.update.assert_called()
    kwargs = video_repo.update.call_args.kwargs
    assert kwargs.get("folder_id") == DOCUMENTARIES_FOLDER_ID
    assert kwargs.get("track_number") == 1


def test_video_playlist_skip_existing_already_filed_still_sets_missing_track_number(
    client,
):
    existing_video = {
        "id": "existing-vid-db-id",
        "download_status": "ready",
        "folder_id": DOCUMENTARIES_FOLDER_ID,
    }
    mock_db, folder_repo, video_repo = _make_db_mock()
    patches = _patch_video_playlist(
        mock_db,
        folder_repo,
        video_repo,
        playlist_info={
            **SAMPLE_PLAYLIST_INFO,
            "entries": SAMPLE_PLAYLIST_INFO["entries"][:1],
        },
        get_video_by_youtube_id=AsyncMock(return_value=existing_video),
    )
    with (
        patches["extract"],
        patches["get_existing"],
        patches["register"],
        patches["download"],
        patches["db"],
        patches["folders"],
        patches["videos"],
    ):
        resp = client.post(
            "/video/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    video_repo.update.assert_called()
    kwargs = video_repo.update.call_args.kwargs
    assert kwargs.get("track_number") == 1


def test_video_playlist_failed_register_occupies_index_queued_keep_playlist_order(
    client,
):
    """Failed/unavailable entries occupy their playlist index; they are not compacted.

    register-then-queue: enumerate(entries, start=1) like POST /audio/playlist.
    Entry 1 fails registration → no row/track write. Entry 2 is queued as 2.
    """
    mock_db, folder_repo, video_repo = _make_db_mock()
    patches = _patch_video_playlist(
        mock_db,
        folder_repo,
        video_repo,
        playlist_info={
            **SAMPLE_PLAYLIST_INFO,
            "entries": SAMPLE_PLAYLIST_INFO["entries"][:2],
        },
        register=AsyncMock(side_effect=[Exception("Video unavailable"), "vid-id-2"]),
    )
    with (
        patches["extract"],
        patches["get_existing"],
        patches["register"],
        patches["download"],
        patches["db"],
        patches["folders"],
        patches["videos"],
    ):
        resp = client.post("/video/playlist", json={"url": PLAYLIST_URL})

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed_items"] == 1
    assert body["queued_items"] == 1
    assert _track_numbers_from_update(video_repo) == [2]


def test_video_playlist_mixed_skip_and_queue_uses_playlist_entry_order(client):
    existing = {
        "id": "existing-vid-db-id",
        "download_status": "completed",
        "folder_id": None,
    }

    async def _lookup(youtube_id: str):
        if youtube_id == "video1234567":
            return existing
        return None

    mock_db, folder_repo, video_repo = _make_db_mock()
    patches = _patch_video_playlist(
        mock_db,
        folder_repo,
        video_repo,
        playlist_info={
            **SAMPLE_PLAYLIST_INFO,
            "entries": SAMPLE_PLAYLIST_INFO["entries"][:2],
        },
        get_video_by_youtube_id=AsyncMock(side_effect=_lookup),
        register=AsyncMock(return_value="vid-id-2"),
    )
    with (
        patches["extract"],
        patches["get_existing"],
        patches["register"],
        patches["download"],
        patches["db"],
        patches["folders"],
        patches["videos"],
    ):
        resp = client.post(
            "/video/playlist", json={"url": PLAYLIST_URL, "skip_existing": True}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped_items"] == 1
    assert body["queued_items"] == 1
    assert _track_numbers_from_update(video_repo) == [1, 2]


# ---------------------------------------------------------------------------
# GET /folders/{id}/items — videos sorted by track_number
# ---------------------------------------------------------------------------


def test_get_folder_items_videos_include_track_number_and_follow_playlist_order(
    client,
):
    """GET /folders/{id}/items serializes Video.to_dict() including track_number.

    Sort order is VideoRepository.get_by_folder (track_number ASC, NULLS last).
    """
    folder = _folder_mock()
    later = Video(
        id="v-ep2",
        title="Ep 2",
        name="Ep 2",
        youtube_id="video7654321",
        folder_id=DOCUMENTARIES_FOLDER_ID,
    )
    later.track_number = 2
    first = Video(
        id="v-ep1",
        title="Ep 1",
        name="Ep 1",
        youtube_id="video1234567",
        folder_id=DOCUMENTARIES_FOLDER_ID,
    )
    first.track_number = 1
    unnumbered = Video(
        id="v-null",
        title="Bonus",
        name="Bonus",
        youtube_id="bonus0000001",
        folder_id=DOCUMENTARIES_FOLDER_ID,
    )

    folder_repo = MagicMock()
    folder_repo.get_by_id = AsyncMock(return_value=folder)
    audio_repo = MagicMock()
    audio_repo.get_by_folder = AsyncMock(return_value=[])
    video_repo = MagicMock()
    video_repo.get_by_folder = AsyncMock(return_value=[first, later, unnumbered])

    @asynccontextmanager
    async def mock_db():
        yield MagicMock()

    with (
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
        patch("app.uwtv.main.AudioRepository", return_value=audio_repo),
        patch("app.uwtv.main.VideoRepository", return_value=video_repo),
    ):
        resp = client.get(f"/folders/{DOCUMENTARIES_FOLDER_ID}/items")

    assert resp.status_code == 200
    videos = resp.json()["videos"]
    assert [v["id"] for v in videos] == ["v-ep1", "v-ep2", "v-null"]
    assert [v["track_number"] for v in videos] == [1, 2, None]
    assert all(v["folder_id"] == DOCUMENTARIES_FOLDER_ID for v in videos)


# ---------------------------------------------------------------------------
# GET /video/list-downloads — collection fields on each video
# ---------------------------------------------------------------------------


def test_list_video_downloads_includes_track_number_and_folder_collection_fields(
    client,
):
    folder = Folder(
        id=DOCUMENTARIES_FOLDER_ID,
        name=DOCUMENTARIES_FOLDER_NAME,
        kind="playlist",
    )
    video = Video(
        id="v-ep1",
        title="Ep 1",
        name="Ep 1",
        youtube_id="video1234567",
        folder_id=folder.id,
    )
    video.folder = folder
    video.track_number = 1

    video_repo = MagicMock()
    video_repo.get_all = AsyncMock(return_value=[video])

    @asynccontextmanager
    async def mock_db():
        yield MagicMock()

    with (
        patch("app.services.managers.get_db_context", mock_db),
        patch("app.services.managers.VideoRepository", return_value=video_repo),
    ):
        resp = client.get("/video/list-downloads")

    assert resp.status_code == 200
    item = resp.json()["videos"][0]
    assert item["folder_id"] == DOCUMENTARIES_FOLDER_ID
    assert item["track_number"] == 1
    assert item["folder_name"] == DOCUMENTARIES_FOLDER_NAME
    assert item["folder_kind"] == "playlist"


# ---------------------------------------------------------------------------
# Video playlists are NOT albums
# ---------------------------------------------------------------------------


def test_get_album_rejects_video_playlist_folder(client):
    folder = _folder_mock(kind="playlist")
    folder_repo = MagicMock()
    folder_repo.get_by_id = AsyncMock(return_value=folder)

    @asynccontextmanager
    async def mock_db():
        yield MagicMock()

    with (
        patch("app.uwtv.main.get_db_context", mock_db),
        patch("app.uwtv.main.FolderRepository", return_value=folder_repo),
    ):
        resp = client.get(f"/albums/{DOCUMENTARIES_FOLDER_ID}")

    assert resp.status_code == 404
    detail = resp.json()["detail"].lower()
    assert "álbum" in detail or "album" in detail
