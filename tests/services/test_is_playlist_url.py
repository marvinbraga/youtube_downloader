"""Tests for is_playlist_url URL classification helper."""

import pytest

from app.services.downloaders import is_playlist_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Single video: watch?v=X -> not a playlist
        ("https://www.youtube.com/watch?v=abc1234567a", False),
        # Single video in playlist context: both v= and list= -> not a playlist
        (
            "https://www.youtube.com/watch?v=abc1234567a&list=PL123",
            False,
        ),
        # Playlist watch form: list= without v= -> playlist
        ("https://www.youtube.com/playlist?list=PL123", True),
        # Bare host playlist form -> playlist
        ("https://youtube.com/playlist?list=PL123", True),
        # Short link: id lives in the path, no query params -> not a playlist
        ("https://youtu.be/abc1234567a", False),
    ],
)
def test_is_playlist_url_classification(url: str, expected: bool) -> None:
    assert is_playlist_url(url) is expected
