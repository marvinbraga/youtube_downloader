# YouTube Cookie Auth Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use ring:executing-plans to implement this plan task-by-task.

**Goal:** Add support for authenticating yt-dlp downloads using cookies from the user's browser or a cookies file, configurable via environment variables.

**Architecture:** A single helper function `get_yt_dlp_cookies_opts()` is added to `app/services/configs.py` to read two environment variables (`YT_COOKIES_FROM_BROWSER`, `YT_COOKIES_FILE`) and return the appropriate yt-dlp options dict. Every `ydl_opts` construction site in `app/services/managers.py` merges this dict in. No new dependencies are required because yt-dlp natively supports both `cookiesfrombrowser` and `cookiefile` options.

**Tech Stack:** Python 3.8+, yt-dlp (already installed), python-dotenv (already used via uvicorn/FastAPI env loading)

**Global Prerequisites:**
- Environment: Linux, Python 3.11+, uv package manager
- Tools: `python --version`, `uv --version`, `pytest --version`
- Access: No additional API keys required
- State: Work on `master` branch, clean working tree

**Verification before starting:**
```bash
# Run ALL these commands and verify output:
python --version        # Expected: Python 3.11+
uv --version            # Expected: uv 0.x.x
git status              # Expected: clean working tree (or only .env / settings changes)
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "import yt_dlp; print(yt_dlp.version.__version__)"
# Expected: a version string such as 2024.x.x
```

---

## Task 1: Add `get_yt_dlp_cookies_opts` to `app/services/configs.py`

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/configs.py`

**Prerequisites:**
- File must exist: `app/services/configs.py`
- No tools beyond Python stdlib are needed

**Step 1: Open the file**

Read `/media/marvinbraga/python/marvin/youtube_downloader/app/services/configs.py`.
Current content (29 lines) ends at the `security = HTTPBearer()` line.

**Step 2: Add the import and helper function**

Insert the following block immediately after line 4 (`from fastapi.security import HTTPBearer`) and before line 6 (`# Diretórios base`):

```python
import os
from typing import Dict, Any
```

Note: `os` and `Dict`/`Any` are not yet imported in this file. The existing import `from typing import Dict, Union` is already present on line 2 — so only `os` needs to be added and `Any` needs to be added to the existing `Union` import.

The exact edit to make (replace the two existing import lines at the top):

Old block (lines 1-4):
```python
from pathlib import Path
from typing import Dict, Union

from fastapi.security import HTTPBearer
```

New block:
```python
import os
from pathlib import Path
from typing import Any, Dict, Union

from fastapi.security import HTTPBearer
```

**Step 3: Append the helper function at the end of the file**

After `security = HTTPBearer()` (the last line of the file), append:

```python


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
        return {"cookiefile": cookies_file}

    return {}
```

**Step 4: Verify the file is syntactically correct**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "from app.services.configs import get_yt_dlp_cookies_opts; print('OK')"
```

Expected output:
```
OK
```

**If you see an ImportError or SyntaxError:** Re-read the file and check that all indentation uses 4 spaces, and that the function is at module level (not nested inside another block).

**Step 5: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add app/services/configs.py && git commit -m "feat: add get_yt_dlp_cookies_opts helper to configs"
```

Expected output:
```
[master xxxxxxx] feat: add get_yt_dlp_cookies_opts helper to configs
 1 file changed, N insertions(+), N deletions(-)
```

**If Task Fails:**

1. **SyntaxError on import:**
   - Check: `uv run python -m py_compile app/services/configs.py`
   - Fix: Ensure `import os` is at the top-level, not inside a function
   - Rollback: `git checkout -- app/services/configs.py`

2. **TypeError on function call:**
   - Run: `uv run python -c "import inspect, app.services.configs as c; print(inspect.getsource(c.get_yt_dlp_cookies_opts))"`
   - Verify the function body matches Step 3 exactly
   - Rollback: `git checkout -- app/services/configs.py`

3. **Can't recover:**
   - Document what failed and why, then stop and return to human partner

---

## Task 2: Write unit tests for `get_yt_dlp_cookies_opts`

**Files:**
- Create: `/media/marvinbraga/python/marvin/youtube_downloader/tests/services/test_configs_cookies.py`
- Prerequisites file must exist: `app/services/configs.py` (done in Task 1)

**Prerequisites:**
- Task 1 completed
- `pytest` available via `uv run pytest`
- Check tests directory exists: `ls /media/marvinbraga/python/marvin/youtube_downloader/tests/`

**Step 1: Confirm the tests/services directory exists**

Run:
```bash
ls /media/marvinbraga/python/marvin/youtube_downloader/tests/
```

If a `services/` subdirectory does not exist, create it:
```bash
mkdir -p /media/marvinbraga/python/marvin/youtube_downloader/tests/services
touch /media/marvinbraga/python/marvin/youtube_downloader/tests/services/__init__.py
```

**Step 2: Write the failing tests**

Create `/media/marvinbraga/python/marvin/youtube_downloader/tests/services/test_configs_cookies.py` with:

```python
"""Unit tests for get_yt_dlp_cookies_opts in app/services/configs.py."""
import os
import pytest

from app.services.configs import get_yt_dlp_cookies_opts, VALID_BROWSERS


class TestGetYtDlpCookiesOpts:
    """Tests for the cookie authentication helper."""

    def test_returns_empty_dict_when_no_env_vars_set(self, monkeypatch):
        """When neither env var is set the function returns an empty dict."""
        monkeypatch.delenv("YT_COOKIES_FROM_BROWSER", raising=False)
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {}

    def test_returns_cookiesfrombrowser_for_chrome(self, monkeypatch):
        """YT_COOKIES_FROM_BROWSER=chrome returns correct yt-dlp key."""
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "chrome")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("chrome",)}

    def test_returns_cookiesfrombrowser_for_brave(self, monkeypatch):
        """YT_COOKIES_FROM_BROWSER=brave returns correct yt-dlp key."""
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "brave")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("brave",)}

    def test_browser_value_is_case_insensitive(self, monkeypatch):
        """Browser name matching is case-insensitive."""
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "Chrome")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("chrome",)}

    def test_browser_value_trims_whitespace(self, monkeypatch):
        """Browser name is stripped of surrounding whitespace."""
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "  firefox  ")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("firefox",)}

    def test_raises_on_invalid_browser_name(self, monkeypatch):
        """An unsupported browser name raises ValueError."""
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "notabrowser")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        with pytest.raises(ValueError, match="notabrowser"):
            get_yt_dlp_cookies_opts()

    def test_returns_cookiefile_when_browser_not_set(self, monkeypatch):
        """YT_COOKIES_FILE path is returned when browser var is absent."""
        monkeypatch.delenv("YT_COOKIES_FROM_BROWSER", raising=False)
        monkeypatch.setenv("YT_COOKIES_FILE", "/tmp/cookies.txt")
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiefile": "/tmp/cookies.txt"}

    def test_browser_takes_precedence_over_file(self, monkeypatch):
        """When both vars are set, browser takes precedence."""
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "firefox")
        monkeypatch.setenv("YT_COOKIES_FILE", "/tmp/cookies.txt")
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("firefox",)}

    def test_empty_browser_string_falls_through_to_file(self, monkeypatch):
        """An empty string for browser env var is treated as unset."""
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "")
        monkeypatch.setenv("YT_COOKIES_FILE", "/tmp/cookies.txt")
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiefile": "/tmp/cookies.txt"}

    def test_valid_browsers_constant_contains_expected_entries(self):
        """VALID_BROWSERS contains the documented browser list."""
        expected = {"chrome", "brave", "firefox", "edge", "opera", "safari", "vivaldi"}
        assert VALID_BROWSERS == expected
```

**Step 3: Run the tests to confirm they pass**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run pytest tests/services/test_configs_cookies.py -v
```

Expected output:
```
collected 10 items

tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_returns_empty_dict_when_no_env_vars_set PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_returns_cookiesfrombrowser_for_chrome PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_returns_cookiesfrombrowser_for_brave PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_browser_value_is_case_insensitive PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_browser_value_trims_whitespace PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_raises_on_invalid_browser_name PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_returns_cookiefile_when_browser_not_set PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_browser_takes_precedence_over_file PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_empty_browser_string_falls_through_to_file PASSED
tests/services/test_configs_cookies.py::TestGetYtDlpCookiesOpts::test_valid_browsers_constant_contains_expected_entries PASSED

========= 10 passed in 0.XXs =========
```

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add tests/services/test_configs_cookies.py && git commit -m "test: add unit tests for get_yt_dlp_cookies_opts"
```

**If Task Fails:**

1. **ModuleNotFoundError for `app.services.configs`:**
   - Check: `uv run python -c "import app.services.configs"` — if it fails, you may need to run from the project root
   - Fix: Ensure the command is run from `/media/marvinbraga/python/marvin/youtube_downloader`
   - Check: Ensure a `tests/__init__.py` exists (create empty file if missing)

2. **Test for invalid browser fails with wrong exception:**
   - Re-read `get_yt_dlp_cookies_opts` and confirm the `raise ValueError(...)` is inside the `if browser not in VALID_BROWSERS:` block
   - Rollback test file: `git checkout -- tests/services/test_configs_cookies.py`

3. **Can't recover:**
   - Document what failed and why, stop and return to human partner

---

## Task 3: Update `VideoStreamManager.ydl_opts` in `app/services/managers.py`

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`

**Prerequisites:**
- Task 1 completed (function exists in `configs.py`)
- Lines 14 and 26-31 visible in `managers.py`

**Step 1: Update the import line at the top of `managers.py`**

Current line 14:
```python
from app.services.configs import AUDIO_DIR, VIDEO_DIR, audio_mapping, video_mapping
```

Replace with:
```python
from app.services.configs import (
    AUDIO_DIR,
    VIDEO_DIR,
    audio_mapping,
    video_mapping,
    get_yt_dlp_cookies_opts,
)
```

**Step 2: Merge cookies opts into `VideoStreamManager.__init__` ydl_opts**

Current block (lines 26-31):
```python
    def __init__(self):
        self.ydl_opts = {
            "format": "best[ext=mp4]",
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": YDL_JS_RUNTIMES,
        }
```

Replace with:
```python
    def __init__(self):
        self.ydl_opts = {
            "format": "best[ext=mp4]",
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": YDL_JS_RUNTIMES,
            **get_yt_dlp_cookies_opts(),
        }
```

**Step 3: Verify syntax**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "from app.services.managers import VideoStreamManager; print('OK')"
```

Expected output:
```
OK
```

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add app/services/managers.py && git commit -m "feat: inject cookie opts into VideoStreamManager ydl_opts"
```

**If Task Fails:**

1. **ImportError for `get_yt_dlp_cookies_opts`:**
   - Check Task 1 is complete: `uv run python -c "from app.services.configs import get_yt_dlp_cookies_opts; print('OK')"`
   - Rollback: `git checkout -- app/services/managers.py`

2. **SyntaxError from `**get_yt_dlp_cookies_opts()` inside dict literal:**
   - Confirm Python version is 3.5+ (dict unpacking in literals requires 3.5+)
   - Rollback: `git checkout -- app/services/managers.py`

3. **Can't recover:**
   - Document what failed and why, stop and return to human partner

---

## Task 4: Merge cookies opts into `AudioDownloadManager.register_audio_for_download` ydl_opts (info extraction)

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`

**Prerequisites:**
- Task 3 completed (import already updated)
- Lines 155-160 in `managers.py` (ydl_opts for info extraction in `register_audio_for_download`)

**Step 1: Locate the ydl_opts block**

The block is inside `AudioDownloadManager.register_audio_for_download`, around line 155:

```python
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "js_runtimes": YDL_JS_RUNTIMES,
            }
```

**Step 2: Add the merge**

Replace that block with:
```python
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "js_runtimes": YDL_JS_RUNTIMES,
                **get_yt_dlp_cookies_opts(),
            }
```

**Step 3: Verify syntax**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "from app.services.managers import AudioDownloadManager; print('OK')"
```

Expected output:
```
OK
```

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add app/services/managers.py && git commit -m "feat: inject cookie opts into AudioDownloadManager info extraction ydl_opts"
```

**If Task Fails:**

1. **Wrong block edited (two ydl_opts exist in this class):**
   - The block at ~line 155 is inside `register_audio_for_download` and has `skip_download: True`
   - The block at ~line 235 is inside `download_audio_with_status_async` and has `format: bestaudio/best`
   - Make sure you edited the one with `skip_download: True`
   - Rollback: `git checkout -- app/services/managers.py`

2. **Can't recover:**
   - Document what failed and why, stop and return to human partner

---

## Task 5: Merge cookies opts into `AudioDownloadManager.download_audio_with_status_async` ydl_opts (actual download)

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`

**Prerequisites:**
- Task 4 completed
- Lines 235-260 in `managers.py` (ydl_opts for the actual audio download)

**Step 1: Locate the ydl_opts block**

Inside `AudioDownloadManager.download_audio_with_status_async`, around line 235, the block starts with:
```python
            ydl_opts = {
                "format": "bestaudio/best",
```
and ends just before the `try:` block that calls `_execute_ydl_download`.

**Step 2: Add the merge**

The full current block is:
```python
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": str(download_dir / "%(title)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                        "preferredquality": "192",
                    }
                ],
                "progress_hooks": [simple_progress_hook],
                "socket_timeout": 30,
                "retries": 10,
                "fragment_retries": 10,
                "nocheckcertificate": True,
                "ignoreerrors": False,
                "verbose": True,
                "noplaylist": True,
                "js_runtimes": YDL_JS_RUNTIMES,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "DNT": "1",
                },
            }
```

Replace with:
```python
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": str(download_dir / "%(title)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                        "preferredquality": "192",
                    }
                ],
                "progress_hooks": [simple_progress_hook],
                "socket_timeout": 30,
                "retries": 10,
                "fragment_retries": 10,
                "nocheckcertificate": True,
                "ignoreerrors": False,
                "verbose": True,
                "noplaylist": True,
                "js_runtimes": YDL_JS_RUNTIMES,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "DNT": "1",
                },
                **get_yt_dlp_cookies_opts(),
            }
```

**Step 3: Verify syntax**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "from app.services.managers import AudioDownloadManager; print('OK')"
```

Expected output:
```
OK
```

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add app/services/managers.py && git commit -m "feat: inject cookie opts into AudioDownloadManager download ydl_opts"
```

**If Task Fails:**

1. **KeyError or duplicate keys warning from yt-dlp:**
   - `**get_yt_dlp_cookies_opts()` must be the last entry in the dict so it does not shadow the `http_headers` key
   - yt-dlp does not merge `http_headers` — the cookies opts dict never contains `http_headers`, so there is no conflict
   - Rollback: `git checkout -- app/services/managers.py`

2. **Can't recover:**
   - Document what failed and why, stop and return to human partner

---

## Task 6: Merge cookies opts into `VideoDownloadManager.register_video_for_download` ydl_opts (info extraction)

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`

**Prerequisites:**
- Task 5 completed
- Lines 569-574 in `managers.py` (ydl_opts for info extraction in `register_video_for_download`)

**Step 1: Locate the ydl_opts block**

Inside `VideoDownloadManager.register_video_for_download`, around line 569:
```python
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "js_runtimes": YDL_JS_RUNTIMES,
            }
```

**Step 2: Add the merge**

Replace with:
```python
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "js_runtimes": YDL_JS_RUNTIMES,
                **get_yt_dlp_cookies_opts(),
            }
```

**Step 3: Verify syntax**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "from app.services.managers import VideoDownloadManager; print('OK')"
```

Expected output:
```
OK
```

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add app/services/managers.py && git commit -m "feat: inject cookie opts into VideoDownloadManager info extraction ydl_opts"
```

**If Task Fails:**

1. **Wrong block edited:**
   - The block at ~line 569 is in `register_video_for_download` and has `skip_download: True`
   - The block at ~line 656 is in `download_video_with_status_async` and has `format: format_str`
   - Ensure you are editing the one with `skip_download: True`
   - Rollback: `git checkout -- app/services/managers.py`

2. **Can't recover:**
   - Document what failed and why, stop and return to human partner

---

## Task 7: Merge cookies opts into `VideoDownloadManager.download_video_with_status_async` ydl_opts (actual download)

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`

**Prerequisites:**
- Task 6 completed
- Lines 656-675 in `managers.py`

**Step 1: Locate the ydl_opts block**

Inside `VideoDownloadManager.download_video_with_status_async`, around line 656, the block starts with:
```python
            ydl_opts = {
                "format": format_str,
```

**Step 2: Add the merge**

The full current block is:
```python
            ydl_opts = {
                "format": format_str,
                "outtmpl": str(download_dir / "%(title)s.%(ext)s"),
                "merge_output_format": "mp4",
                "progress_hooks": [simple_progress_hook],
                "socket_timeout": 30,
                "retries": 10,
                "fragment_retries": 10,
                "nocheckcertificate": True,
                "ignoreerrors": False,
                "verbose": True,
                "noplaylist": True,
                "js_runtimes": YDL_JS_RUNTIMES,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "DNT": "1",
                },
            }
```

Replace with:
```python
            ydl_opts = {
                "format": format_str,
                "outtmpl": str(download_dir / "%(title)s.%(ext)s"),
                "merge_output_format": "mp4",
                "progress_hooks": [simple_progress_hook],
                "socket_timeout": 30,
                "retries": 10,
                "fragment_retries": 10,
                "nocheckcertificate": True,
                "ignoreerrors": False,
                "verbose": True,
                "noplaylist": True,
                "js_runtimes": YDL_JS_RUNTIMES,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "DNT": "1",
                },
                **get_yt_dlp_cookies_opts(),
            }
```

**Step 3: Verify syntax**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "from app.services.managers import VideoDownloadManager; print('OK')"
```

Expected output:
```
OK
```

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add app/services/managers.py && git commit -m "feat: inject cookie opts into VideoDownloadManager download ydl_opts"
```

**If Task Fails:**

1. **AttributeError or TypeError:**
   - Verify `get_yt_dlp_cookies_opts` returns a `dict` (not `None`)
   - Run: `uv run python -c "from app.services.configs import get_yt_dlp_cookies_opts; r = get_yt_dlp_cookies_opts(); print(type(r), r)"`
   - Rollback: `git checkout -- app/services/managers.py`

2. **Can't recover:**
   - Document what failed and why, stop and return to human partner

---

## Task 8: Handle the `extract_youtube_id` fallback ydl_opts in both managers

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`

**Prerequisites:**
- Task 7 completed
- Two `extract_youtube_id` methods exist — one in `AudioDownloadManager` (~line 89) and one in `VideoDownloadManager` (~line 500). Each has a `ydl_info_opts` local dict.

**Step 1: Locate the two `ydl_info_opts` blocks**

Both blocks look like this (one in each class's `extract_youtube_id`):
```python
                ydl_info_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "extract_flat": True,
                    "js_runtimes": YDL_JS_RUNTIMES,
                }
```

**Step 2: Update both blocks**

Replace each occurrence with:
```python
                ydl_info_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "extract_flat": True,
                    "js_runtimes": YDL_JS_RUNTIMES,
                    **get_yt_dlp_cookies_opts(),
                }
```

There are exactly 2 occurrences of this pattern in the file. Both must be updated.

**Step 3: Verify both classes import correctly**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "
from app.services.managers import AudioDownloadManager, VideoDownloadManager
print('OK')
"
```

Expected output:
```
OK
```

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add app/services/managers.py && git commit -m "feat: inject cookie opts into extract_youtube_id fallback ydl_opts"
```

**If Task Fails:**

1. **Only one block updated (the other still uses the old pattern):**
   - Search the file: `grep -n "ydl_info_opts" app/services/managers.py`
   - Expected output: 2 lines, both in `extract_youtube_id` methods
   - Edit the remaining one
   - Rollback if unsure: `git checkout -- app/services/managers.py`

2. **Can't recover:**
   - Document what failed and why, stop and return to human partner

---

## Task 9: Run all tests and perform a final import smoke-test

**Files:**
- No file changes — verification only

**Prerequisites:**
- Tasks 1-8 completed

**Step 1: Run the cookie unit tests**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run pytest tests/services/test_configs_cookies.py -v
```

Expected output:
```
========= 10 passed in 0.XXs =========
```

**Step 2: Run the full test suite**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run pytest -v 2>&1 | tail -20
```

Expected output: All previously passing tests still pass. Zero new failures.

**Step 3: Full import smoke-test of the application**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && uv run python -c "
from app.services.configs import get_yt_dlp_cookies_opts, VALID_BROWSERS
from app.services.managers import AudioDownloadManager, VideoDownloadManager, VideoStreamManager
print('All imports OK')
print('VALID_BROWSERS:', sorted(VALID_BROWSERS))
print('No-env cookies opts:', get_yt_dlp_cookies_opts())
"
```

Expected output:
```
All imports OK
VALID_BROWSERS: ['brave', 'chrome', 'edge', 'firefox', 'opera', 'safari', 'vivaldi']
No-env cookies opts: {}
```

**If Step 2 reveals new failures:**
- Identify which test file is failing
- Compare against the git log to find which task introduced the regression
- Run: `git log --oneline -10` to see recent commits
- Rollback to the last known-good commit: `git revert HEAD` (do not use `git reset --hard` unless no other option)

---

## Task 10: Code Review

**Files:**
- No file changes until review findings are acted on

**Prerequisites:**
- Task 9 completed with all tests passing

**Step 1: Dispatch all 6 reviewers in parallel**

REQUIRED SUB-SKILL: Use ring:requesting-code-review

All reviewers run simultaneously (ring:code-reviewer, ring:business-logic-reviewer, ring:security-reviewer, ring:test-reviewer, ring:nil-safety-reviewer, ring:consequences-reviewer). Wait for all to complete.

**Step 2: Handle findings by severity (MANDATORY)**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 6 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location
- Format: `TODO(review): [Issue description] (reported by [reviewer] on 2026-04-01, severity: Low)`

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on 2026-04-01, severity: Cosmetic)`

**Step 3: Proceed only when:**
- Zero Critical/High/Medium issues remain
- All Low issues have TODO(review): comments
- All Cosmetic issues have FIXME(nitpick): comments

---

## Task 11: Create `.env.example` with the new variables

**Files:**
- Create: `/media/marvinbraga/python/marvin/youtube_downloader/.env.example`

**Prerequisites:**
- Tasks 1-10 completed
- The `.env` file already exists at the project root; `.env.example` does not yet exist

**Step 1: Write `.env.example`**

Create the file `/media/marvinbraga/python/marvin/youtube_downloader/.env.example` with the following content:

```dotenv
# ==============================================================================
# LLM API KEYS
# ==============================================================================

ANTHROPIC_API_KEY=your-anthropic-api-key
COHERE_API_KEY=your-cohere-api-key
GOOGLE_API_KEY=your-google-api-key
GROQ_API_KEY=your-groq-api-key
NVIDIA_API_KEY=your-nvidia-api-key
OPENAI_API_KEY=your-openai-api-key
XAI_API_KEY=your-xai-api-key

# ==============================================================================
# yt-dlp Cookie Authentication (optional)
# ==============================================================================
#
# Use one of the two methods below to pass cookies to yt-dlp so it can
# authenticate with YouTube (useful for age-restricted or member-only content).
#
# METHOD 1: Extract cookies directly from an installed browser.
# Supported values: chrome | brave | firefox | edge | opera | safari | vivaldi
# Leave blank or omit to disable.
#
# YT_COOKIES_FROM_BROWSER=chrome

# METHOD 2: Path to a Netscape-format cookies.txt file.
# Ignored when YT_COOKIES_FROM_BROWSER is set.
# Leave blank or omit to disable.
#
# YT_COOKIES_FILE=/path/to/cookies.txt
```

**Step 2: Verify the file was written**

Run:
```bash
cat /media/marvinbraga/python/marvin/youtube_downloader/.env.example
```

Expected output: the exact content written in Step 1.

**Step 3: Ensure `.env.example` is tracked by git (not in .gitignore)**

Run:
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git check-ignore -v .env.example
```

Expected output: no output (meaning the file is NOT ignored).

If the file IS being ignored (output shows a `.gitignore` rule matching it), open `.gitignore` and add an explicit negation line:
```
!.env.example
```

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && git add .env.example && git commit -m "docs: add .env.example with YT_COOKIES_FROM_BROWSER and YT_COOKIES_FILE"
```

Expected output:
```
[master xxxxxxx] docs: add .env.example with YT_COOKIES_FROM_BROWSER and YT_COOKIES_FILE
 1 file changed, N insertions(+)
```

**If Task Fails:**

1. **`.env.example` is gitignored:**
   - Open `.gitignore` and add `!.env.example` as the last line
   - Re-run `git check-ignore -v .env.example` — expect no output
   - Then proceed with Step 4

2. **Can't recover:**
   - Document what failed and why, stop and return to human partner

---

## Final Verification Checklist

After all tasks are complete, run this sequence:

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader

# 1. All unit tests pass
uv run pytest tests/services/test_configs_cookies.py -v
# Expected: 10 passed

# 2. Full test suite unbroken
uv run pytest -v 2>&1 | tail -5
# Expected: all previously passing tests still pass

# 3. No-cookie mode: empty dict returned
uv run python -c "
import os
os.environ.pop('YT_COOKIES_FROM_BROWSER', None)
os.environ.pop('YT_COOKIES_FILE', None)
from app.services.configs import get_yt_dlp_cookies_opts
print(get_yt_dlp_cookies_opts())
"
# Expected: {}

# 4. Browser mode: correct tuple returned
uv run python -c "
import os
os.environ['YT_COOKIES_FROM_BROWSER'] = 'brave'
from app.services.configs import get_yt_dlp_cookies_opts
print(get_yt_dlp_cookies_opts())
"
# Expected: {'cookiesfrombrowser': ('brave',)}

# 5. File mode: path returned
uv run python -c "
import os
os.environ.pop('YT_COOKIES_FROM_BROWSER', None)
os.environ['YT_COOKIES_FILE'] = '/tmp/my_cookies.txt'
from app.services.configs import get_yt_dlp_cookies_opts
print(get_yt_dlp_cookies_opts())
"
# Expected: {'cookiefile': '/tmp/my_cookies.txt'}

# 6. All 5 ydl_opts sites now include the cookie merge
grep -n "get_yt_dlp_cookies_opts" app/services/managers.py
# Expected: 5 lines (one import line + four/five ydl_opts sites)
```
