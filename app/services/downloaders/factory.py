"""Factory: pick a Downloader based on URL netloc."""

from urllib.parse import parse_qs, urlparse

from app.services.downloaders.base import Downloader
from app.services.downloaders.instagram import InstagramDownloader
from app.services.downloaders.youtube import YouTubeDownloader

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}

_INSTAGRAM_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
}


def get_downloader(url: str) -> Downloader:
    """Return a concrete Downloader for ``url``.

    Raises:
        ValueError: if the host is unsupported.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host in _YOUTUBE_HOSTS:
        return YouTubeDownloader()
    if host in _INSTAGRAM_HOSTS:
        return InstagramDownloader()

    raise ValueError(
        f"URL não suportada (host '{host}'). "
        "Apenas URLs de YouTube e Instagram são aceitas."
    )


def get_source_for_url(url: str) -> str:
    """Return the source identifier for ``url`` ('youtube' or 'instagram')."""
    return get_downloader(url).source


def is_playlist_url(url: str) -> bool:
    """Return True when ``url`` points to a playlist (not a single video).

    A URL is treated as a playlist when its query string carries a ``list``
    parameter but no ``v`` parameter. URLs that carry both ``v`` and ``list``
    (e.g. ``watch?v=ID&list=ID``) reference a single video being played in the
    context of a playlist and are therefore considered single videos, not
    playlists. The ``youtube.com/playlist?list=...`` form is detected as a
    playlist; short ``youtu.be/ID`` links keep their ID in the path (no query
    params) and are single videos.

    Query parsing uses :func:`urllib.parse.parse_qs` for robustness instead of
    regex matching.
    """
    query = parse_qs(urlparse(url).query)
    return "list" in query and "v" not in query
