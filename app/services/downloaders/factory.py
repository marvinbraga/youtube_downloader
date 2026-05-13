"""Factory: pick a Downloader based on URL netloc."""

from urllib.parse import urlparse

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
