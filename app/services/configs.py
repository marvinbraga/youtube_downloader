import os
from pathlib import Path
from typing import Any, Dict, Union

from fastapi.security import HTTPBearer

# Diretórios base
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DOWNLOADS_DIR = ROOT_DIR / "downloads"

# Diretórios específicos
VIDEO_DIR = DOWNLOADS_DIR / "videos"
AUDIO_DIR = DOWNLOADS_DIR / "audio"
JSON_CONFIG_PATH = DATA_DIR / "videos.json"
AUDIO_CONFIG_PATH = DATA_DIR / "audios.json"

# Garante que os diretórios existam
DATA_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)
VIDEO_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

# Mapeamentos
video_mapping: Dict[str, Union[Path, str]] = {}
audio_mapping: Dict[str, Union[Path, str]] = {}

# Configuração de segurança
security = HTTPBearer()


# ---------------------------------------------------------------------------
# yt-dlp cookie authentication
# ---------------------------------------------------------------------------

VALID_BROWSERS = {"chrome", "brave", "firefox", "edge", "opera", "safari", "vivaldi"}


def get_yt_dlp_cookies_opts(source: str = "youtube") -> Dict[str, Any]:
    """Return yt-dlp options for cookie-based authentication for a given source.

    Cookies are looked up per-source. For ``source='youtube'`` the legacy env
    vars ``YT_COOKIES_FROM_BROWSER`` and ``YT_COOKIES_FILE`` are honored. For
    other sources (e.g. ``instagram``) the upper-cased prefix is used:
    ``INSTAGRAM_COOKIES_FROM_BROWSER`` and ``INSTAGRAM_COOKIES_FILE``.

    Priority within a source:
      1. ``<SOURCE>_COOKIES_FROM_BROWSER`` — extract directly from browser profile.
         Valid values: chrome, brave, firefox, edge, opera, safari, vivaldi.
      2. ``<SOURCE>_COOKIES_FILE`` — path to a Netscape-format cookies.txt file.
      3. Neither set — returns ``{}`` (no cookie auth; public content still works).
    """
    source_key = source.upper() if source else "YOUTUBE"
    # Backward-compatible aliases: YOUTUBE keeps the historical YT_ prefix.
    if source_key == "YOUTUBE":
        browser_env = "YT_COOKIES_FROM_BROWSER"
        file_env = "YT_COOKIES_FILE"
    else:
        browser_env = f"{source_key}_COOKIES_FROM_BROWSER"
        file_env = f"{source_key}_COOKIES_FILE"

    browser = os.environ.get(browser_env, "").strip().lower()
    if browser:
        if browser not in VALID_BROWSERS:
            raise ValueError(
                f"{browser_env}='{browser}' is not supported. "
                f"Valid values: {', '.join(sorted(VALID_BROWSERS))}"
            )
        return {"cookiesfrombrowser": (browser,)}

    cookies_file = os.environ.get(file_env, "").strip()
    if cookies_file:
        resolved = Path(cookies_file).resolve()
        if not resolved.is_file():
            raise ValueError(
                f"{file_env}='{cookies_file}' does not point to a regular file."
            )
        return {"cookiefile": str(resolved)}

    return {}
