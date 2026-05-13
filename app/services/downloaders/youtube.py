"""YouTube strategy — preserves the historical yt-dlp option set."""

import os
import re
import shutil
from typing import Any, Dict, Optional

from loguru import logger
from yt_dlp import YoutubeDL

from app.services.configs import get_yt_dlp_cookies_opts
from app.services.downloaders.base import Downloader

# Detecta deno e node para resolver JS challenges do YouTube
_deno_path = shutil.which("deno") or os.path.expanduser("~/.deno/bin/deno")
_node_path = shutil.which("node") or os.path.expanduser(
    "~/.nvm/versions/node/v20.19.6/bin/node"
)

YDL_JS_RUNTIMES: Dict[str, Dict[str, str]] = {}
if _deno_path and os.path.exists(_deno_path):
    YDL_JS_RUNTIMES["deno"] = {"path": _deno_path}
if _node_path and os.path.exists(_node_path):
    YDL_JS_RUNTIMES["node"] = {"path": _node_path}

if not YDL_JS_RUNTIMES:
    logger.warning("Nenhum runtime JS encontrado (deno/node). Downloads podem falhar.")

YDL_REMOTE_COMPONENTS = ["ejs:github"]

_YOUTUBE_URL_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|live/|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)

# Shared HTTP headers used by both audio and video opts
_YOUTUBE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "DNT": "1",
}

# Resolution-to-format mapping (kept in sync with managers.VideoDownloadManager.RESOLUTION_MAP)
_RESOLUTION_MAP: Dict[str, str] = {
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "best": "bestvideo+bestaudio/best",
}


class YouTubeDownloader(Downloader):
    """Strategy for youtube.com / youtu.be."""

    source = "youtube"

    def extract_id(self, url: str) -> Optional[str]:
        try:
            match = _YOUTUBE_URL_RE.search(url)
            if match:
                return match.group(1)

            ydl_info_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                "js_runtimes": YDL_JS_RUNTIMES,
                "remote_components": YDL_REMOTE_COMPONENTS,
                **get_yt_dlp_cookies_opts("youtube"),
            }
            with YoutubeDL(ydl_info_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("id") or None
        except Exception as exc:
            logger.error(f"Erro ao extrair YouTube ID: {exc}")
            return None

    def get_info(self, url: str) -> Dict[str, Any]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "js_runtimes": YDL_JS_RUNTIMES,
            "remote_components": YDL_REMOTE_COMPONENTS,
            **get_yt_dlp_cookies_opts("youtube"),
        }
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False) or {}

    def build_audio_opts(self, output_dir: str, progress_hook) -> Dict[str, Any]:
        return {
            "format": "bestaudio/best",
            "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                }
            ],
            "progress_hooks": [progress_hook],
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "verbose": os.environ.get("YT_DLP_VERBOSE", "").lower()
            in ("1", "true", "yes"),
            "noplaylist": True,
            "js_runtimes": YDL_JS_RUNTIMES,
            "remote_components": YDL_REMOTE_COMPONENTS,
            "http_headers": _YOUTUBE_HEADERS,
            **get_yt_dlp_cookies_opts("youtube"),
        }

    def build_video_opts(
        self, output_dir: str, resolution: str, progress_hook
    ) -> Dict[str, Any]:
        format_str = _RESOLUTION_MAP.get(resolution, _RESOLUTION_MAP["1080p"])
        return {
            "format": format_str,
            "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
            "merge_output_format": "mp4",
            "progress_hooks": [progress_hook],
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "verbose": os.environ.get("YT_DLP_VERBOSE", "").lower()
            in ("1", "true", "yes"),
            "noplaylist": True,
            "js_runtimes": YDL_JS_RUNTIMES,
            "remote_components": YDL_REMOTE_COMPONENTS,
            "http_headers": _YOUTUBE_HEADERS,
            **get_yt_dlp_cookies_opts("youtube"),
        }
