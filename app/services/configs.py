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


def get_yt_dlp_cookies_opts() -> Dict[str, Any]:
    """Return yt-dlp options for cookie-based authentication.

    Priority:
    1. YT_COOKIES_FROM_BROWSER — uses cookies extracted directly from the
       named browser's profile.  Value must be one of: chrome, brave,
       firefox, edge, opera, safari, vivaldi.
    2. YT_COOKIES_FILE — path to a Netscape-format cookies.txt file.
    3. Neither set — returns an empty dict (no cookie auth).

    Examples
    --------
    YT_COOKIES_FROM_BROWSER=chrome  ->  {"cookiesfrombrowser": ("chrome",)}
    YT_COOKIES_FILE=/tmp/cookies.txt ->  {"cookiefile": "/tmp/cookies.txt"}
    """
    browser = os.environ.get("YT_COOKIES_FROM_BROWSER", "").strip().lower()
    if browser:
        if browser not in VALID_BROWSERS:
            raise ValueError(
                f"YT_COOKIES_FROM_BROWSER='{browser}' is not supported. "
                f"Valid values: {', '.join(sorted(VALID_BROWSERS))}"
            )
        return {"cookiesfrombrowser": (browser,)}

    cookies_file = os.environ.get("YT_COOKIES_FILE", "").strip()
    if cookies_file:
        resolved = Path(cookies_file).resolve()
        if not resolved.is_file():
            raise ValueError(
                f"YT_COOKIES_FILE='{cookies_file}' does not point to a regular file."
            )
        return {"cookiefile": str(resolved)}

    return {}
