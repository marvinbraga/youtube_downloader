"""Tests for extract_playlist_info on AudioDownloadManager and VideoDownloadManager."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.managers import (
    AudioDownloadManager,
    VideoDownloadManager,
    extract_artist_from_info,
)


@pytest.fixture(params=[AudioDownloadManager, VideoDownloadManager])
def manager(request):
    return request.param()


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_happy_path_returns_entries(mock_ydl_cls, manager):
    """extract_playlist_info returns entries list on valid playlist."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "My Playlist",
        "webpage_url": "https://www.youtube.com/playlist?list=PL1",
        "id": "PL1",
        "uploader": "Channel X",
        "thumbnail": "https://i.ytimg.com/vi/abc1234567a/hqdefault.jpg",
        "entries": [
            {"id": "abc1234567a", "title": "Track 1"},
            {"id": "xyz9876543z", "title": "Track 2"},
        ],
    }

    result = await manager.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )

    assert result["title"] == "My Playlist"
    assert len(result["entries"]) == 2
    assert result["entries"][0]["url"] == "https://www.youtube.com/watch?v=abc1234567a"
    assert result["entries"][1]["url"] == "https://www.youtube.com/watch?v=xyz9876543z"
    assert result["playlist_id"] == "PL1"
    assert result["uploader"] == "Channel X"
    assert result["thumbnail"] == "https://i.ytimg.com/vi/abc1234567a/hqdefault.jpg"


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_raises_value_error_on_empty_entries(mock_ydl_cls, manager):
    """extract_playlist_info raises ValueError when entries is empty list."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {"title": "PL", "entries": []}

    with pytest.raises(ValueError, match="não retornou entradas"):
        await manager.extract_playlist_info("https://www.youtube.com/playlist?list=PL1")


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_raises_value_error_on_no_entries_key(mock_ydl_cls, manager):
    """extract_playlist_info raises ValueError when entries key is absent."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {"title": "PL"}

    with pytest.raises(ValueError, match="não retornou entradas"):
        await manager.extract_playlist_info("https://www.youtube.com/playlist?list=PL1")


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_raises_value_error_when_info_is_none(mock_ydl_cls, manager):
    """extract_playlist_info raises ValueError when yt-dlp returns None."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = None

    with pytest.raises(ValueError, match="não retornou informações"):
        await manager.extract_playlist_info("https://www.youtube.com/playlist?list=PL1")


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_skips_entries_with_none_id(mock_ydl_cls, manager):
    """extract_playlist_info skips entries where id is None (deleted/private videos)."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "PL",
        "webpage_url": "https://www.youtube.com/playlist?list=PL1",
        "entries": [
            {"id": "abc1234567a", "title": "Valid"},
            {"id": None, "title": "[Private video]"},
            None,
        ],
    }

    result = await manager.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )

    assert len(result["entries"]) == 1
    assert result["entries"][0]["id"] == "abc1234567a"


@pytest.mark.anyio
async def test_raises_value_error_for_non_youtube_host(manager):
    """extract_playlist_info raises ValueError for non-YouTube hosts (SSRF guard)."""
    with pytest.raises(ValueError, match="não está na lista permitida"):
        await manager.extract_playlist_info("https://vimeo.com/channels/staffpicks")


@pytest.mark.anyio
async def test_raises_value_error_for_non_http_scheme(manager):
    """extract_playlist_info raises ValueError for non-HTTP schemes."""
    with pytest.raises(ValueError, match="Esquema de URL"):
        await manager.extract_playlist_info("file:///etc/passwd")


@pytest.mark.anyio
async def test_raises_value_error_for_userinfo_url(manager):
    """extract_playlist_info raises ValueError for URLs with embedded credentials."""
    with pytest.raises(ValueError, match="credenciais embutidas"):
        await manager.extract_playlist_info(
            "https://evil.com@youtube.com/playlist?list=PL1"
        )


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_title_fallback_uses_video_id(mock_ydl_cls, manager):
    """extract_playlist_info falls back to Video_{id} when title fields absent."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "PL",
        "webpage_url": "https://www.youtube.com/playlist?list=PL1",
        "entries": [{"id": "abc1234567a"}],
    }

    result = await manager.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )

    assert result["entries"][0]["title"] == "Video_abc1234567a"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/playlist?list=PL1",
        "https://youtu.be/abc1234567a",
        "https://music.youtube.com/playlist?list=PL1",
        "https://m.youtube.com/playlist?list=PL1",
    ],
)
@patch("app.services.managers.YoutubeDL")
async def test_all_allowed_hosts_are_accepted(mock_ydl_cls, url, manager):
    """All allowed YouTube hosts accept without raising."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "PL",
        "webpage_url": url,
        "entries": [{"id": "abc1234567a", "title": "T"}],
    }
    result = await manager.extract_playlist_info(url)
    assert len(result["entries"]) == 1


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_raises_value_error_when_all_entries_filtered(mock_ydl_cls, manager):
    """extract_playlist_info raises ValueError when all entries lack valid IDs."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "PL",
        "webpage_url": "https://www.youtube.com/playlist?list=PL1",
        "entries": [
            None,
            {"id": None, "title": "[Private video]"},
            {"id": "", "title": "[Deleted]"},
        ],
    }
    with pytest.raises(ValueError, match="Nenhuma entrada com ID válido"):
        await manager.extract_playlist_info("https://www.youtube.com/playlist?list=PL1")


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_playlist_title_falls_back_to_playlist_string(mock_ydl_cls, manager):
    """extract_playlist_info falls back to 'Playlist' when title fields absent."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "entries": [{"id": "abc1234567a", "title": "T"}],
    }
    result = await manager.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )
    assert result["title"] == "Playlist"


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_webpage_url_falls_back_to_input_url(mock_ydl_cls, manager):
    """extract_playlist_info falls back to input URL when webpage_url absent."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "PL",
        "entries": [{"id": "abc1234567a", "title": "T"}],
    }
    result = await manager.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )
    assert "youtube.com" in result["webpage_url"]


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_skips_entries_with_invalid_id_format(mock_ydl_cls, manager):
    """extract_playlist_info skips entries with IDs that fail the YouTube regex."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "PL",
        "webpage_url": "https://www.youtube.com/playlist?list=PL1",
        "entries": [
            {"id": "abc1234567a", "title": "Valid"},
            {"id": "../secrets", "title": "Injection attempt"},
            {"id": "tooshort", "title": "Too short"},
        ],
    }

    result = await manager.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )

    assert len(result["entries"]) == 1
    assert result["entries"][0]["id"] == "abc1234567a"


# ---------------------------------------------------------------------------
# extract_artist_from_info
# ---------------------------------------------------------------------------


def test_extract_artist_prefers_artist_field():
    assert extract_artist_from_info({"artist": "A", "uploader": "B"}) == "A"


def test_extract_artist_album_artist_fallback():
    assert extract_artist_from_info({"album_artist": "Album Artist"}) == "Album Artist"


def test_extract_artist_from_artists_list_of_strings():
    assert extract_artist_from_info({"artists": ["One", "Two"]}) == "One, Two"


def test_extract_artist_from_artists_list_of_dicts():
    assert (
        extract_artist_from_info({"artists": [{"name": "X"}, {"name": "Y"}]}) == "X, Y"
    )


def test_extract_artist_ignores_uploader_channel():
    """Uploader/channel are playlist owner — never treated as track artist."""
    assert extract_artist_from_info({"uploader": "Channel"}) is None
    assert extract_artist_from_info({"channel": "Ch"}) is None
    assert extract_artist_from_info({"creator": "Creator"}) is None
    assert extract_artist_from_info({"playlist_uploader": "Owner"}) is None
    assert extract_artist_from_info({"playlist_channel": "Owner Ch"}) is None


def test_extract_artist_empty_or_missing():
    assert extract_artist_from_info(None) is None
    assert extract_artist_from_info({}) is None
    assert extract_artist_from_info({"artist": "  "}) is None


def test_extract_artist_from_title_dash_pattern():
    assert (
        extract_artist_from_info({"title": "Artist Name - Song Title"}) == "Artist Name"
    )
    assert extract_artist_from_info({"title": "Band – Hit"}) == "Band"
    assert extract_artist_from_info({"title": "Solo — Ballad"}) == "Solo"


def test_extract_artist_from_title_bullet_pattern():
    assert (
        extract_artist_from_info({"title": "Song Title · Artist Name"}) == "Artist Name"
    )
    assert extract_artist_from_info({"title": "Ballad • Singer"}) == "Singer"


def test_extract_artist_title_pattern_requires_both_sides():
    assert extract_artist_from_info({"title": "Just a title"}) is None
    assert extract_artist_from_info({"title": " - only right"}) is None


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_entry_includes_artist_when_present(mock_ydl_cls, manager):
    """Flat playlist entries include artist from music fields only."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "My Playlist",
        "webpage_url": "https://www.youtube.com/playlist?list=PL1",
        "id": "PL1",
        "entries": [
            {"id": "abc1234567a", "title": "Track 1", "artist": "Singer One"},
            {"id": "xyz9876543z", "title": "Track 2", "uploader": "Channel Two"},
        ],
    }

    result = await manager.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )

    assert result["entries"][0]["artist"] == "Singer One"
    assert "artist" not in result["entries"][1]
