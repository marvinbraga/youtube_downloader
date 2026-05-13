"""Downloader strategies — one implementation per source platform.

Pick a downloader for a given URL via :func:`factory.get_downloader`.
"""

from app.services.downloaders.base import Downloader, ExtractedInfo
from app.services.downloaders.factory import get_downloader, get_source_for_url

__all__ = ["Downloader", "ExtractedInfo", "get_downloader", "get_source_for_url"]
