"""Tests for extract_playlist_info in AudioDownloadManager."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.managers import AudioDownloadManager


def _make_manager():
    return AudioDownloadManager()


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_happy_path_returns_entries(mock_ydl_cls):
    """extract_playlist_info returns entries list on valid playlist."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "My Playlist",
        "webpage_url": "https://www.youtube.com/playlist?list=PL1",
        "entries": [
            {"id": "abc1234567a", "title": "Track 1"},
            {"id": "xyz9876543z", "title": "Track 2"},
        ],
    }

    mgr = _make_manager()
    result = await mgr.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )

    assert result["title"] == "My Playlist"
    assert len(result["entries"]) == 2
    assert result["entries"][0]["url"] == "https://www.youtube.com/watch?v=abc1234567a"
    assert result["entries"][1]["url"] == "https://www.youtube.com/watch?v=xyz9876543z"


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_raises_value_error_on_empty_entries(mock_ydl_cls):
    """extract_playlist_info raises ValueError when entries is empty list."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {"title": "PL", "entries": []}

    mgr = _make_manager()
    with pytest.raises(ValueError, match="não retornou entradas"):
        await mgr.extract_playlist_info("https://www.youtube.com/playlist?list=PL1")


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_raises_value_error_on_no_entries_key(mock_ydl_cls):
    """extract_playlist_info raises ValueError when entries key is absent."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {"title": "PL"}

    mgr = _make_manager()
    with pytest.raises(ValueError):
        await mgr.extract_playlist_info("https://www.youtube.com/playlist?list=PL1")


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_raises_value_error_when_info_is_none(mock_ydl_cls):
    """extract_playlist_info raises ValueError when yt-dlp returns None."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = None

    mgr = _make_manager()
    with pytest.raises(ValueError, match="não retornou informações"):
        await mgr.extract_playlist_info("https://www.youtube.com/playlist?list=PL1")


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_skips_entries_with_none_id(mock_ydl_cls):
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

    mgr = _make_manager()
    result = await mgr.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )

    assert len(result["entries"]) == 1
    assert result["entries"][0]["id"] == "abc1234567a"


@pytest.mark.anyio
async def test_raises_value_error_for_non_youtube_host():
    """extract_playlist_info raises ValueError for non-YouTube hosts (SSRF guard)."""
    mgr = _make_manager()
    with pytest.raises(ValueError, match="não está na lista permitida"):
        await mgr.extract_playlist_info("https://vimeo.com/channels/staffpicks")


@pytest.mark.anyio
async def test_raises_value_error_for_non_http_scheme():
    """extract_playlist_info raises ValueError for non-HTTP schemes."""
    mgr = _make_manager()
    with pytest.raises(ValueError, match="Esquema de URL"):
        await mgr.extract_playlist_info("file:///etc/passwd")


@pytest.mark.anyio
@patch("app.services.managers.YoutubeDL")
async def test_title_fallback_uses_video_id(mock_ydl_cls):
    """extract_playlist_info falls back to Video_{id} when title fields absent."""
    mock_ydl = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "title": "PL",
        "webpage_url": "https://www.youtube.com/playlist?list=PL1",
        "entries": [{"id": "abc1234567a"}],
    }

    mgr = _make_manager()
    result = await mgr.extract_playlist_info(
        "https://www.youtube.com/playlist?list=PL1"
    )

    assert result["entries"][0]["title"] == "Video_abc1234567a"
