"""Instagram strategy — uses yt-dlp's native extractor for Reels, Posts, IGTV."""

import os
import re
from typing import Any, Dict, Optional

from loguru import logger
from yt_dlp import YoutubeDL

from app.services.configs import get_yt_dlp_cookies_opts
from app.services.downloaders.base import Downloader

# Matches /reel/{shortcode}, /reels/{shortcode}, /p/{shortcode}, /tv/{shortcode}.
# Shortcodes are 5-20 chars of [A-Za-z0-9_-] historically. We allow up to 30
# to be future-proof; yt-dlp will reject genuinely invalid ones at extract time.
_INSTAGRAM_URL_RE = re.compile(
    r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]{1,30})"
)

# Instagram is fussy about User-Agents — pretend to be a recent Chrome.
_INSTAGRAM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class InstagramDownloader(Downloader):
    """Strategy for instagram.com (public Reels, Posts, IGTV)."""

    source = "instagram"

    def extract_id(self, url: str) -> Optional[str]:
        # Profile URLs (instagram.com/<user>/), stories, IGTV-collection links,
        # and other non-media paths must not silently succeed via yt-dlp's
        # generic fallback — that produces junk DB rows whose external_id
        # is a username or timestamp. Require the regex to match a known
        # media-bearing path (/reel, /reels, /p, /tv) up front.
        match = _INSTAGRAM_URL_RE.search(url)
        if match:
            return match.group(1)
        logger.warning(
            f"URL do Instagram não reconhecida como mídia (reel/p/tv): {url}"
        )
        return None

    def get_info(self, url: str) -> Dict[str, Any]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "http_headers": _INSTAGRAM_HEADERS,
            **get_yt_dlp_cookies_opts("instagram"),
        }
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False) or {}

    def build_audio_opts(self, output_dir: str, progress_hook) -> Dict[str, Any]:
        return {
            "format": "bestaudio/best",
            "outtmpl": f"{output_dir}/%(title).200B [%(id)s].%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                }
            ],
            "progress_hooks": [progress_hook],
            "socket_timeout": 30,
            "retries": 5,
            "fragment_retries": 5,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "verbose": os.environ.get("YT_DLP_VERBOSE", "").lower()
            in ("1", "true", "yes"),
            "noplaylist": True,
            "http_headers": _INSTAGRAM_HEADERS,
            **get_yt_dlp_cookies_opts("instagram"),
        }

    def build_video_opts(
        self, output_dir: str, resolution: str, progress_hook
    ) -> Dict[str, Any]:
        # Instagram does not expose discrete resolution ladders; "best" is the
        # only meaningful choice. The ``resolution`` argument is accepted for
        # API parity but ignored by the extractor.
        return {
            "format": "best",
            "outtmpl": f"{output_dir}/%(title).200B [%(id)s].%(ext)s",
            "merge_output_format": "mp4",
            "progress_hooks": [progress_hook],
            "socket_timeout": 30,
            "retries": 5,
            "fragment_retries": 5,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "verbose": os.environ.get("YT_DLP_VERBOSE", "").lower()
            in ("1", "true", "yes"),
            "noplaylist": True,
            "http_headers": _INSTAGRAM_HEADERS,
            **get_yt_dlp_cookies_opts("instagram"),
        }
