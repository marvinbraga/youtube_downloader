import glob
import os
import shutil
import tempfile
import time
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

# Prefix for per-download throwaway cookie copies (see _writable_cookie_copy).
_COOKIE_TMP_PREFIX = "ytdl_cookies_"


def _writable_cookie_copy(master: Path) -> str:
    """Return a throwaway, writable copy of ``master`` for a single download.

    yt-dlp rewrites the cookiefile on ``YoutubeDL.close()`` (it persists any
    ``Set-Cookie`` the server sent). Pointing it straight at the mounted master
    breaks in two ways:

    * the master is mounted read-only -> ``PermissionError`` on save;
    * the download queue runs multiple downloads at once, and
      ``MozillaCookieJar.save()`` opens with ``'w'`` (non-atomic), so concurrent
      saves to a shared file can interleave and corrupt it.

    Handing each download its own copy sidesteps both: the master is never
    written, and every writer owns a private file. Stale copies are reaped
    best-effort so long-running containers don't accumulate them.
    """
    cutoff = time.time() - 6 * 3600
    for old in glob.glob(os.path.join(tempfile.gettempdir(), f"{_COOKIE_TMP_PREFIX}*")):
        try:
            if os.path.getmtime(old) < cutoff:
                os.unlink(old)
        except OSError:
            pass
    fd, tmp = tempfile.mkstemp(prefix=_COOKIE_TMP_PREFIX, suffix=".txt")
    os.close(fd)
    shutil.copyfile(master, tmp)
    return tmp


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
        # Never hand yt-dlp the master directly — it rewrites it on close.
        return {"cookiefile": _writable_cookie_copy(resolved)}

    return {}


# ---------------------------------------------------------------------------
# Transcription concurrency configuration
# ---------------------------------------------------------------------------

# Maximum number of transcriptions allowed to run simultaneously. Transcribing a
# single audio/video can hold ~100MB in memory; running many in parallel spiked
# memory and was killing the server process. The dedicated executor in main.py
# uses this value to cap concurrent workers; surplus requests wait in the
# executor's internal queue (status "queued") instead of grabbing extra threads.
TRANSCRIPTION_CONCURRENCY = int(os.getenv("TRANSCRIPTION_CONCURRENCY", "2"))


# ---------------------------------------------------------------------------
# Storage backend configuration
# ---------------------------------------------------------------------------

# STORAGE_BACKEND: 'local' (default) | 's3'
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").strip().lower()

# S3-specific config (only required when STORAGE_BACKEND=s3)
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "").strip()
AWS_REGION = (
    os.environ.get("AWS_REGION", "").strip()
    or os.environ.get("AWS_DEFAULT_REGION", "").strip()
)
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "").strip() or None
AWS_S3_KEY_PREFIX = os.environ.get("AWS_S3_KEY_PREFIX", "").strip().strip("/")

# Credentials are picked up automatically by aioboto3 via the standard
# AWS credential chain (env vars, ~/.aws/credentials, IMDS, IRSA, etc.).
# We deliberately do not read AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in
# Python — aioboto3 handles them transparently and reading them here only
# risks accidental logging of secrets.

# How long presigned GET URLs stay valid (seconds). Six hours by default,
# which covers podcasts and long-form episodes without re-issuing the URL
# mid-playback session.
S3_PRESIGNED_URL_TTL = int(os.environ.get("S3_PRESIGNED_URL_TTL", "21600"))

# Whether to delete the local file after a successful S3 upload.
# 'true' (default) frees disk but breaks local-file tools (transcription
# falls back to download_to_temp). 'false' keeps a redundant local copy.
S3_DELETE_LOCAL_AFTER_UPLOAD = (
    os.environ.get("S3_DELETE_LOCAL_AFTER_UPLOAD", "true").strip().lower() == "true"
)


def validate_storage_config() -> None:
    """Validate storage configuration. Called once at startup.

    Raises ValueError if STORAGE_BACKEND=s3 but required S3 env vars are
    missing. Local backend has no required config.
    """
    # Import here to avoid a circular import: app.db.models imports nothing
    # from app.services, but keeping this lazy keeps the dependency direction
    # explicit at the module level.
    from app.db.models import STORAGE_BACKENDS, is_valid_storage_backend

    if not is_valid_storage_backend(STORAGE_BACKEND):
        raise ValueError(
            f"STORAGE_BACKEND='{STORAGE_BACKEND}' is not supported. "
            f"Valid values: {', '.join(sorted(STORAGE_BACKENDS))}"
        )
    if STORAGE_BACKEND == "s3":
        missing = []
        if not AWS_S3_BUCKET:
            missing.append("AWS_S3_BUCKET")
        if not AWS_REGION:
            missing.append("AWS_REGION (or AWS_DEFAULT_REGION)")
        if missing:
            raise ValueError("STORAGE_BACKEND=s3 requires: " + ", ".join(missing))
        if S3_PRESIGNED_URL_TTL <= 0 or S3_PRESIGNED_URL_TTL > 7 * 24 * 3600:
            raise ValueError(
                "S3_PRESIGNED_URL_TTL must be > 0 and <= 604800 seconds (7d)."
            )
