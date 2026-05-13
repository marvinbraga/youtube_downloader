# Instagram Support Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use ring:execute-plan to implement this plan task-by-task.

**Goal:** Add Instagram (Reels, Posts, IGTV) download support to the existing YouTube Downloader service while preserving 100% backward compatibility with existing YouTube data.

**Architecture:** Keep `yt-dlp` as the single download engine (it has a native Instagram extractor). Introduce a Strategy pattern (`Downloader` abstract base + `YouTubeDownloader` / `InstagramDownloader` subclasses) selected by URL `netloc`. Generalize the persistence layer: add `external_id` and `source` columns to `audios`/`videos` while keeping `youtube_id` as the legacy alias (populated only when `source='youtube'`). Playlists remain YouTube-only for v1 (Instagram has no playlist analog).

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy (async + aiosqlite), yt-dlp (already pinned `>=2026.3.1` — has Instagram extractor), jQuery 3 + Bootstrap 5.3.3 (vanilla, no build).

**Global Prerequisites:**
- Environment: Linux/macOS, Python 3.10–3.12
- Tools: `uv` package manager, `git`, `curl`, `sqlite3` CLI for verification
- Access: No Instagram credentials needed for public Reels/Posts. JWT auth still required for the API.
- State: On branch `feat/instagram-support`, clean working tree (only `.claude/settings.local.json` may be modified — that is expected).

**Verification before starting:**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
python --version          # Expected: Python 3.10.x – 3.12.x
uv --version              # Expected: uv 0.4+
git branch --show-current # Expected: feat/instagram-support
git status                # Expected: only .claude/settings.local.json modified (or clean)
sqlite3 --version         # Expected: 3.x
```

**Out of scope for v1 (explicit non-goals):**
- Instagram playlist/profile downloads (`/_ALLOWED_HOSTS` stays YouTube-only).
- Instagram Stories, private posts, or login-walled content.
- Updating UI copy in `web_client/index.html` (labels "URL do YouTube" stay — placeholder will be updated, but the heading remains).
- Renaming the `youtube_id` SQL column (kept as legacy alias). Future migration can drop it.
- **Refactoring `VideoStreamManager`** — relies on yt-dlp's `"best[ext=mp4]"` format selector to surface a top-level direct-URL. The Strategy abstraction does not yet model that. Streaming remains YouTube-only. Instagram media is consumed via downloaded files (the existing file-based `/audio/stream` and `/video/stream` endpoints).
- **Improving `/audio/check_exists`** — that endpoint currently queries `get_audio_by_youtube_id`, so Instagram-source rows (which have `youtube_id IS NULL`) will report `exists: False` even after a successful download. Dedup at registration time (Task 11 Step 4) still prevents duplicate rows, but the pre-check UX degrades for Instagram URLs. Tracked as a known v1 limitation; a follow-up task should swap this query to `get_by_external_id`.

**Agent recommendation for every task below:** `general-purpose` (this repo has no Python-specific Ring agent).

---

## Task 1: Confirm baseline and snapshot the SQLite schema

**Files:**
- Inspect: `app/db/models.py`, `app/db/database.py`, `data/youtube_downloader.db`

**Prerequisites:**
- Database file exists (it does — the app has been run before).

**Step 1: Snapshot current schemas**

Run:
```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db ".schema audios"
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db ".schema videos"
```

**Expected output (audios):** contains `youtube_id VARCHAR(100)` but NO `source` or `external_id` column.

**Expected output (videos):** contains `youtube_id VARCHAR(100)` and `source VARCHAR(50) NOT NULL DEFAULT 'youtube'` but NO `external_id` column.

**Step 2: Snapshot row counts**

Run:
```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db "SELECT COUNT(*) AS audios FROM audios; SELECT COUNT(*) AS videos FROM videos;"
```

**Expected output:** two integers (record the values — they will be re-checked after migration in Task 4).

**Step 3: Back up the database (rollback safety)**

```bash
cp /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
   /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db.bak-2026-05-13
```

**Expected output:** no output. Backup file exists.

**Step 4: Verify the backup**

```bash
ls -la /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db.bak-2026-05-13
```

**Expected output:** file listed with size > 0.

**If Task Fails:**
- Database file missing → run the server once (`uv run uvicorn app.uwtv.main:app`) to create it, then redo.
- Permission denied on `cp` → check `data/` write permissions.

---

## Task 2: Add `INSTAGRAM` to Pydantic source enums and `external_id` to `AudioInfo`/`VideoInfo`

**Files:**
- Modify: `app/models/audio.py:8-10` (extend `AudioSource`)
- Modify: `app/models/video.py:18-21` (extend `VideoSource`); `app/models/video.py:23-32` (extend `VideoInfo`)

**Prerequisites:**
- Task 1 complete.

**Step 1: Extend `AudioSource` enum**

Edit `app/models/audio.py`. Replace:

```python
class AudioSource(str, Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"
```

with:

```python
class AudioSource(str, Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
```

**Step 2: Extend `VideoSource` enum**

Edit `app/models/video.py`. Replace:

```python
class VideoSource(str, Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"
```

with:

```python
class VideoSource(str, Enum):
    LOCAL = "local"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
```

**Step 3: Verify imports still load**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "from app.models.audio import AudioSource; from app.models.video import VideoSource; print(list(AudioSource), list(VideoSource))"
```

**Expected output:**
```
[<AudioSource.LOCAL: 'local'>, <AudioSource.YOUTUBE: 'youtube'>, <AudioSource.INSTAGRAM: 'instagram'>] [<VideoSource.LOCAL: 'local'>, <VideoSource.YOUTUBE: 'youtube'>, <VideoSource.INSTAGRAM: 'instagram'>]
```

**If Task Fails:**
- ImportError → check that the file edit preserved indentation (4 spaces, no tabs).
- Rollback: `git checkout -- app/models/audio.py app/models/video.py`

---

## Task 3: Add `source` and `external_id` columns to SQLAlchemy `Audio` model

**Files:**
- Modify: `app/db/models.py:79-126` (the `Audio` class)

**Prerequisites:**
- Task 2 complete.

**Step 1: Add `source` column to `Audio`**

Edit `app/db/models.py`. Locate the line:

```python
    youtube_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
```

and INSERT immediately ABOVE it (still inside the `Audio` class) these two new columns:

```python
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="youtube", index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
```

The resulting block should look like:

```python
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="youtube", index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    youtube_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
```

**Step 2: Update `Audio.to_dict()` to include the new fields**

In `app/db/models.py`, inside the `Audio.to_dict()` method (around line 128–155), add the two new keys to the returned dict (right after `"youtube_id"`):

```python
            "youtube_id": self.youtube_id,
            "source": self.source,
            "external_id": self.external_id,
            "url": self.url,
```

(Insert the two new keys; keep all existing keys untouched.)

**Step 3: Add `external_id` to SQLAlchemy `Video` model**

`Video` already has `source` (line 199). Only add `external_id`. Locate in `Video`:

```python
    youtube_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
```

and INSERT immediately above it:

```python
    external_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
```

**Step 4: Update `Video.to_dict()` to include `external_id`**

In `app/db/models.py`, inside `Video.to_dict()` (around line 207–234), add the key right after `"youtube_id"`:

```python
            "youtube_id": self.youtube_id,
            "external_id": self.external_id,
            "url": self.url,
```

**Step 5: Verify models import cleanly**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "from app.db.models import Audio, Video; print(Audio.__table__.columns.keys()); print(Video.__table__.columns.keys())"
```

**Expected output:** Both column lists include `source` and `external_id`. Example:
```
['id', 'title', 'name', 'source', 'external_id', 'youtube_id', 'url', 'path', 'directory', 'format', 'filesize', 'download_status', 'download_progress', 'download_error', 'transcription_status', 'transcription_path', 'folder_id', 'keywords', 'created_date', 'modified_date']
['id', 'title', 'name', 'external_id', 'youtube_id', 'url', 'path', 'directory', 'format', 'filesize', 'duration', 'resolution', 'download_status', 'download_progress', 'download_error', 'transcription_status', 'transcription_path', 'folder_id', 'source', 'created_date', 'modified_date']
```

**If Task Fails:**
- ImportError → re-read the file; ensure both `Optional` and `String` are already imported (they are, lines 3–6).
- Rollback: `git checkout -- app/db/models.py`

---

## Task 4: Add idempotent ALTER TABLE migration in `init_db`

**Files:**
- Modify: `app/db/database.py:31-35` (the `init_db` function)

**Prerequisites:**
- Task 3 complete.
- Database backup exists (Task 1, Step 3).

**Rationale:** SQLAlchemy `create_all()` only creates missing tables — it does NOT add new columns to existing tables. We must run raw `ALTER TABLE` statements gated by `PRAGMA table_info()` for idempotency. SQLite has no `ADD COLUMN IF NOT EXISTS`.

**Step 1: Replace `init_db` with the migration-aware version**

Edit `app/db/database.py`. Replace the existing `init_db` function (lines 31–35):

```python
async def init_db() -> None:
    """Inicializa o banco de dados criando as tabelas"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"Banco de dados inicializado em: {DATABASE_PATH}")
```

with:

```python
async def init_db() -> None:
    """Inicializa o banco de dados criando as tabelas e aplicando migrações de schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_schema_migrations(conn)
    logger.info(f"Banco de dados inicializado em: {DATABASE_PATH}")


async def _apply_schema_migrations(conn) -> None:
    """Aplica migrações idempotentes de schema para suporte multi-plataforma.

    Adiciona colunas `source` e `external_id` em `audios` e `external_id` em
    `videos`. Faz backfill de `external_id = youtube_id` e `source = 'youtube'`
    para linhas pré-existentes. Seguro para rodar em todo startup.
    """
    # --- audios ---
    result = await conn.exec_driver_sql("PRAGMA table_info(audios)")
    audio_cols = {row[1] for row in result.fetchall()}

    if "source" not in audio_cols:
        await conn.exec_driver_sql(
            "ALTER TABLE audios ADD COLUMN source VARCHAR(50) NOT NULL DEFAULT 'youtube'"
        )
        logger.info("Coluna 'source' adicionada em audios")

    if "external_id" not in audio_cols:
        await conn.exec_driver_sql(
            "ALTER TABLE audios ADD COLUMN external_id VARCHAR(100)"
        )
        logger.info("Coluna 'external_id' adicionada em audios")

    # Backfill: linhas antigas usam youtube_id como external_id
    await conn.exec_driver_sql(
        "UPDATE audios SET external_id = youtube_id "
        "WHERE external_id IS NULL AND youtube_id IS NOT NULL"
    )

    # Cria índices se ainda não existirem
    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_audios_source ON audios(source)"
    )
    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_audios_external_id ON audios(external_id)"
    )

    # --- videos ---
    result = await conn.exec_driver_sql("PRAGMA table_info(videos)")
    video_cols = {row[1] for row in result.fetchall()}

    if "external_id" not in video_cols:
        await conn.exec_driver_sql(
            "ALTER TABLE videos ADD COLUMN external_id VARCHAR(100)"
        )
        logger.info("Coluna 'external_id' adicionada em videos")

    await conn.exec_driver_sql(
        "UPDATE videos SET external_id = youtube_id "
        "WHERE external_id IS NULL AND youtube_id IS NOT NULL"
    )

    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_videos_external_id ON videos(external_id)"
    )
```

**Step 2: Run the app briefly to trigger migration**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  timeout 6 uv run uvicorn app.uwtv.main:app --host 127.0.0.1 --port 8765 2>&1 | tail -30
```

**Expected output (relevant lines):**
```
INFO ... Inicializando banco de dados SQLite...
INFO ... Coluna 'source' adicionada em audios
INFO ... Coluna 'external_id' adicionada em audios
INFO ... Coluna 'external_id' adicionada em videos
INFO ... Banco de dados inicializado em: .../data/youtube_downloader.db
INFO ... Aplicação iniciada com sucesso!
```

(The `timeout` will kill uvicorn after 6 seconds — that is expected. We just need startup to complete.)

**Step 3: Verify schema and backfill**

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT COUNT(*) AS total, SUM(CASE WHEN source='youtube' THEN 1 ELSE 0 END) AS yt, SUM(CASE WHEN external_id = youtube_id THEN 1 ELSE 0 END) AS backfilled FROM audios;"
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT COUNT(*) AS total, SUM(CASE WHEN external_id = youtube_id THEN 1 ELSE 0 END) AS backfilled FROM videos;"
```

**Expected output:** `total == yt == backfilled` for audios. `total == backfilled` for videos. (All pre-existing rows have `source='youtube'` and `external_id = youtube_id`.)

**Step 4: Verify idempotency — run startup a second time**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  timeout 6 uv run uvicorn app.uwtv.main:app --host 127.0.0.1 --port 8765 2>&1 | grep -E "(Coluna|inicializado)" | tail -10
```

**Expected output:** ONLY the `Banco de dados inicializado em:` line. NO `Coluna ... adicionada` lines (because columns now exist).

**If Task Fails:**
- `OperationalError: duplicate column name` → the `if "X" not in cols` check is missing/broken — re-check the PRAGMA logic.
- `SyntaxError` near `conn.exec_driver_sql` → verify the function is `async def` and that all calls are `await`ed.
- Migration partially applied → restore `data/youtube_downloader.db.bak-2026-05-13` and retry:
  ```bash
  cp /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db.bak-2026-05-13 \
     /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db
  ```

---

## Task 5: Update `repositories.py` — add `get_by_external_id` (keep `get_by_youtube_id`)

**Files:**
- Modify: `app/db/repositories.py:22-27` (`AudioRepository.get_by_youtube_id`) and `app/db/repositories.py:142-147` (`VideoRepository.get_by_youtube_id`).

**Prerequisites:**
- Task 4 complete.

**Step 1: Add `get_by_external_id` to `AudioRepository`**

In `app/db/repositories.py`, locate the `AudioRepository.get_by_youtube_id` method (lines 22–27) and INSERT this new method immediately AFTER it (preserving original method):

```python
    async def get_by_external_id(
        self, external_id: str, source: Optional[str] = None
    ) -> Optional[Audio]:
        """Busca áudio pelo external_id (opcionalmente filtrando por source)."""
        query = select(Audio).where(Audio.external_id == external_id)
        if source is not None:
            query = query.where(Audio.source == source)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
```

**Step 2: Add `get_by_external_id` to `VideoRepository`**

Locate `VideoRepository.get_by_youtube_id` (lines 142–147) and INSERT immediately after it:

```python
    async def get_by_external_id(
        self, external_id: str, source: Optional[str] = None
    ) -> Optional[Video]:
        """Busca vídeo pelo external_id (opcionalmente filtrando por source)."""
        query = select(Video).where(Video.external_id == external_id)
        if source is not None:
            query = query.where(Video.source == source)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
```

**Step 3: Verify**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "from app.db.repositories import AudioRepository, VideoRepository; print('AR:', hasattr(AudioRepository, 'get_by_external_id')); print('VR:', hasattr(VideoRepository, 'get_by_external_id'))"
```

**Expected output:**
```
AR: True
VR: True
```

**If Task Fails:**
- AttributeError → method may have been inserted outside the class. Re-check indentation (must be 4 spaces, inside class).
- Rollback: `git checkout -- app/db/repositories.py`

---

## Task 6: Update `configs.py` — accept `source` parameter in `get_yt_dlp_cookies_opts`

**Files:**
- Modify: `app/services/configs.py:39-72`

**Prerequisites:**
- Task 5 complete.

**Rationale:** YouTube and Instagram have separate cookie scopes. The function signature must accept a `source` argument with default `'youtube'` so existing startup validation in `app/uwtv/main.py:90` (called as `get_yt_dlp_cookies_opts()`) still works.

**Step 1: Replace the function**

In `app/services/configs.py`, replace the entire `get_yt_dlp_cookies_opts` function (lines 39–72) with:

```python
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
```

**Step 2: Verify signature backward compat (zero-arg call still works)**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "from app.services.configs import get_yt_dlp_cookies_opts; print('default:', get_yt_dlp_cookies_opts()); print('yt:', get_yt_dlp_cookies_opts('youtube')); print('ig:', get_yt_dlp_cookies_opts('instagram'))"
```

**Expected output:** Three lines, each `{}` (assuming no cookie env vars are set). No exceptions.

**Step 3: Verify lifespan validation still passes**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  timeout 6 uv run uvicorn app.uwtv.main:app --host 127.0.0.1 --port 8765 2>&1 | grep -E "(Cookie configuration|Invalid|Aplicação)" | tail -5
```

**Expected output:**
```
INFO ... Cookie configuration validated successfully.
INFO ... Aplicação iniciada com sucesso!
```

**If Task Fails:**
- `TypeError: get_yt_dlp_cookies_opts() missing 1 required positional argument` → the default `source='youtube'` is missing on the function signature.
- Rollback: `git checkout -- app/services/configs.py`

---

## Task 7: Code review checkpoint (Tasks 1–6)

**REQUIRED SUB-SKILL:** Use ring:codereview.

1. Dispatch all 10 reviewers in parallel (code, business-logic, security, test, nil-safety, consequences, dead-code, performance, multi-tenant, lib-commons).
2. Files in scope:
   - `app/models/audio.py`, `app/models/video.py`
   - `app/db/models.py`, `app/db/database.py`, `app/db/repositories.py`
   - `app/services/configs.py`
3. Handle findings:
   - **Critical/High/Medium:** fix immediately, re-run reviewers, repeat until clean.
   - **Low:** add `TODO(review):` comment at the call site.
   - **Cosmetic:** add `FIXME(nitpick):` comment.
4. Proceed only when Critical/High/Medium count = 0.

**Specific concerns to flag for reviewers:**
- Migration idempotency: does the PRAGMA check survive concurrent app starts?
- Backfill SQL: are NULL `youtube_id` rows safely left alone?
- Cookie env var naming: is `INSTAGRAM_COOKIES_FILE` consistent with project conventions?

---

## Task 8: Create downloaders package skeleton (Strategy abstract base)

**Files:**
- Create: `app/services/downloaders/__init__.py`
- Create: `app/services/downloaders/base.py`

**Prerequisites:**
- Task 7 complete (review clean).

**Step 1: Create the package directory**

```bash
mkdir -p /media/marvinbraga/python/marvin/youtube_downloader/app/services/downloaders
```

**Step 2: Create `__init__.py` (base-only — factory import added in Task 10)**

Create file `/media/marvinbraga/python/marvin/youtube_downloader/app/services/downloaders/__init__.py` with content:

```python
"""Downloader strategies — one implementation per source platform.

Pick a downloader for a given URL via :func:`factory.get_downloader`
(added after Task 10).
"""
from app.services.downloaders.base import Downloader, ExtractedInfo

__all__ = ["Downloader", "ExtractedInfo"]
```

Task 10 Step 2.5 will append the `get_downloader` import once `factory.py` exists.

**Step 3: Create `base.py` with the abstract Strategy**

Create file `/media/marvinbraga/python/marvin/youtube_downloader/app/services/downloaders/base.py` with content:

```python
"""Abstract base for platform-specific downloaders."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExtractedInfo:
    """Result of a download, normalized across platforms."""

    info: Dict[str, Any]
    filename: str  # absolute or yt-dlp-prepared filename
    extra: Dict[str, Any] = field(default_factory=dict)


class Downloader(ABC):
    """Abstract Strategy for downloading media from a single platform.

    Each subclass encapsulates:
      * ID extraction from a URL (regex + yt-dlp fallback)
      * The yt-dlp option dictionary (cookies, headers, format selection)
      * Source identifier (`'youtube'`, `'instagram'`, ...)
    """

    source: str = "unknown"  # MUST be overridden by subclasses

    @abstractmethod
    def extract_id(self, url: str) -> Optional[str]:
        """Return the platform-native ID for ``url`` or ``None`` if not parseable."""

    @abstractmethod
    def get_info(self, url: str) -> Dict[str, Any]:
        """Return yt-dlp info dict for ``url`` (without downloading the media)."""

    @abstractmethod
    def build_audio_opts(
        self, output_dir: str, progress_hook
    ) -> Dict[str, Any]:
        """Return yt-dlp opts for audio-only download into ``output_dir``."""

    @abstractmethod
    def build_video_opts(
        self, output_dir: str, resolution: str, progress_hook
    ) -> Dict[str, Any]:
        """Return yt-dlp opts for video download into ``output_dir``."""
```

**Step 4: Verify**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "from app.services.downloaders.base import Downloader, ExtractedInfo; print(Downloader, ExtractedInfo)"
```

**Expected output:**
```
<class 'app.services.downloaders.base.Downloader'> <class 'app.services.downloaders.base.ExtractedInfo'>
```

**Note:** the `from app.services.downloaders.factory import get_downloader` line in `__init__.py` will fail until Task 10 creates `factory.py`. That is fine — at Task 8 we only test direct imports from `base`.

**If Task Fails:**
- `ImportError: cannot import name 'get_downloader'` → that's expected only if Task 8 step 4 imports from the package directly. If so, skip Step 4 and verify after Task 10.
- Rollback: `rm -rf app/services/downloaders/`

---

## Task 9: Implement `YouTubeDownloader`

**Files:**
- Create: `app/services/downloaders/youtube.py`

**Prerequisites:**
- Task 8 complete.

**Step 1: Create `youtube.py`**

Create file `/media/marvinbraga/python/marvin/youtube_downloader/app/services/downloaders/youtube.py` with content:

```python
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
_COMMON_HEADERS = {
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
            "http_headers": _COMMON_HEADERS,
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
            "http_headers": _COMMON_HEADERS,
            **get_yt_dlp_cookies_opts("youtube"),
        }
```

**Step 2: Verify**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "from app.services.downloaders.youtube import YouTubeDownloader; d = YouTubeDownloader(); print(d.source, d.extract_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ'))"
```

**Expected output:**
```
youtube dQw4w9WgXcQ
```

**If Task Fails:**
- `ModuleNotFoundError: app.services.downloaders.base` → Task 8 not complete.
- Rollback: `rm app/services/downloaders/youtube.py`

---

## Task 10: Implement `InstagramDownloader` and the factory

**Files:**
- Create: `app/services/downloaders/instagram.py`
- Create: `app/services/downloaders/factory.py`

**Prerequisites:**
- Task 9 complete.

**Step 1: Create `instagram.py`**

Create file `/media/marvinbraga/python/marvin/youtube_downloader/app/services/downloaders/instagram.py` with content:

```python
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
_COMMON_HEADERS = {
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
        try:
            match = _INSTAGRAM_URL_RE.search(url)
            if match:
                return match.group(1)

            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                **get_yt_dlp_cookies_opts("instagram"),
            }
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("id") or None
        except Exception as exc:
            logger.error(f"Erro ao extrair Instagram ID: {exc}")
            return None

    def get_info(self, url: str) -> Dict[str, Any]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "http_headers": _COMMON_HEADERS,
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
            "http_headers": _COMMON_HEADERS,
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
            "http_headers": _COMMON_HEADERS,
            **get_yt_dlp_cookies_opts("instagram"),
        }
```

**Step 2: Create `factory.py`**

Create file `/media/marvinbraga/python/marvin/youtube_downloader/app/services/downloaders/factory.py` with content:

```python
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
```

**Step 2.5: Extend `app/services/downloaders/__init__.py` to export `get_downloader`**

In `app/services/downloaders/__init__.py`, REPLACE the entire current content with:

```python
"""Downloader strategies — one implementation per source platform.

Pick a downloader for a given URL via :func:`factory.get_downloader`.
"""
from app.services.downloaders.base import Downloader, ExtractedInfo
from app.services.downloaders.factory import get_downloader, get_source_for_url

__all__ = ["Downloader", "ExtractedInfo", "get_downloader", "get_source_for_url"]
```

**Step 3: Verify factory routing and package public API**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "
from app.services.downloaders import get_downloader
print(get_downloader('https://www.youtube.com/watch?v=dQw4w9WgXcQ').source)
print(get_downloader('https://www.instagram.com/reel/ABC123xyz/').source)
print(get_downloader('https://youtu.be/dQw4w9WgXcQ').source)
try:
    get_downloader('https://vimeo.com/12345')
except ValueError as e:
    print('rejected:', str(e)[:50])
"
```

**Expected output:**
```
youtube
instagram
youtube
rejected: URL não suportada (host 'vimeo.com'). Apenas URL
```

**Step 4: Verify Instagram regex parses the canonical URL shapes**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "
from app.services.downloaders.instagram import InstagramDownloader
d = InstagramDownloader()
for u in [
    'https://www.instagram.com/reel/Cabc123XYZ/',
    'https://www.instagram.com/p/Cdef456XYZ/?utm_source=ig_web_copy_link',
    'https://www.instagram.com/tv/Cghi789XYZ/',
    'https://instagram.com/reels/Cjkl000XYZ/',
]:
    print(u.split('?')[0], '->', d.extract_id(u))
"
```

**Expected output:** Each line ends with a non-None shortcode that matches the path segment.

**If Task Fails:**
- Regex mis-match → re-read the URL; some Instagram URLs use `/reels/` (plural) — already covered by the regex.
- Rollback: `rm app/services/downloaders/instagram.py app/services/downloaders/factory.py`

---

## Task 11: Refactor `AudioDownloadManager` to use the Strategy

**Files:**
- Modify: `app/services/managers.py:93-244` (the `AudioDownloadManager` class — methods `__init__`, `extract_youtube_id`, `register_audio_for_download`, `download_audio_with_status_async`)

**Prerequisites:**
- Task 10 complete.

**Step 1: Update module imports**

In `app/services/managers.py`, locate the existing imports block (lines 15–24) and ADD this single import line at the end of that block:

```python
from app.services.downloaders import get_downloader
```

**Step 2: Add `extract_external_id` helper as a module-level function**

Add this function near the top of `app/services/managers.py`, right after the `_YOUTUBE_ID_RE` constant (around line 46), keeping `_YOUTUBE_ID_RE` for the existing playlist allowlist code:

```python
def extract_external_id(url: str) -> tuple:
    """Return ``(source, external_id)`` for ``url``.

    Falls back to a timestamp-based ID if the platform extractor cannot derive one.
    Raises ``ValueError`` if the URL host is not supported.
    """
    downloader = get_downloader(url)  # raises ValueError on unsupported host
    ext_id = downloader.extract_id(url)
    if not ext_id:
        ext_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return downloader.source, ext_id
```

**Step 3: Add a legacy-compatible `extract_youtube_id` shim on `AudioDownloadManager`**

In `app/services/managers.py`, REPLACE the existing `AudioDownloadManager.extract_youtube_id` method (lines 102–132) with this thinner shim that preserves the public method name used by `app/uwtv/main.py:280`:

```python
    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Legacy: returns the external_id for any supported URL.

        Despite the YouTube-flavored name (kept for backward compat with the
        ``/audio/check_exists`` endpoint), this resolves Instagram URLs too.
        """
        try:
            _, ext_id = extract_external_id(url)
            return ext_id
        except ValueError as exc:
            logger.warning(f"URL não suportada para extração de ID: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Erro ao extrair ID externo: {exc}")
            return None
```

**Step 4: Replace `register_audio_for_download` to use the factory and persist `source`/`external_id`**

In `app/services/managers.py`, REPLACE the entire `register_audio_for_download` method (lines 167–245) with:

```python
    async def register_audio_for_download(self, url: str) -> str:
        """Registra um áudio para download com status 'downloading'.

        Multi-source: dispara o downloader correto via factory e persiste
        ``source`` + ``external_id``. O ID primário da linha continua sendo
        o ``external_id`` (mantém o mesmo padrão histórico em que ``id == youtube_id``).
        """
        try:
            logger.info(f"Registrando áudio para download: {url}")

            downloader = get_downloader(url)  # raises ValueError on unsupported host
            source = downloader.source

            external_id = downloader.extract_id(url)
            if not external_id:
                external_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Dedup por (source, external_id) — evita falso-positivo cross-platform
            async with get_db_context() as session:
                repo = AudioRepository(session)
                existing = await repo.get_by_external_id(external_id, source=source)

                if existing is not None:
                    if existing.download_status not in ("error", ""):
                        logger.info(
                            f"Áudio já existe (source={source}, ext_id={external_id})"
                        )
                        return existing.id
                    # Reprocessa erro: reseta status
                    logger.info(
                        f"Áudio {existing.id} estava com status '{existing.download_status}', "
                        "resetando para nova tentativa"
                    )
                    await repo.update(
                        existing.id,
                        download_status="downloading",
                        download_progress=0,
                        download_error="",
                    )
                    return existing.id

            # Extrai título sem baixar
            title = f"Video_{external_id}"
            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, downloader.get_info, url)
                title = info.get("title") or title
            except Exception as extract_error:
                logger.warning(f"Erro ao extrair informações: {extract_error}")

            # YouTube preserva populamento de ``youtube_id`` para compat;
            # outras sources deixam essa coluna NULL.
            youtube_id_value = external_id if source == "youtube" else None

            async with get_db_context() as session:
                repo = AudioRepository(session)
                audio = Audio(
                    id=external_id,
                    title=title,
                    name=f"{title}.m4a",
                    source=source,
                    external_id=external_id,
                    youtube_id=youtube_id_value,
                    url=url,
                    path="",
                    directory="",
                    format="m4a",
                    filesize=0,
                    download_status="downloading",
                    download_progress=0,
                    download_error="",
                    transcription_status="none",
                    transcription_path="",
                    keywords=json.dumps(self._extract_keywords(title)),
                )
                await repo.create(audio)

            logger.info(
                f"Áudio registrado: id={external_id} source={source}"
            )
            return external_id

        except ValueError as ve:
            logger.error(f"URL não suportada: {ve}")
            raise
        except Exception as e:
            logger.error(f"Erro ao registrar áudio: {e}")
            raise
```

**Step 5: Refactor `download_audio_with_status_async` to delegate ydl_opts to the Strategy**

In `app/services/managers.py`, locate `download_audio_with_status_async` (lines 247–382). REPLACE the section that builds `ydl_opts` (lines 280–308 — the dict literal ending with `**get_yt_dlp_cookies_opts()`) with:

```python
            downloader = get_downloader(url)
            ydl_opts = downloader.build_audio_opts(
                output_dir=str(download_dir),
                progress_hook=simple_progress_hook,
            )
```

Keep everything else in the method untouched.

**Step 6: Verify**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "
import asyncio
from app.services.managers import AudioDownloadManager, extract_external_id
m = AudioDownloadManager()
print('yt:', m.extract_youtube_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ'))
print('ig:', m.extract_youtube_id('https://www.instagram.com/reel/Cabc123XYZ/'))
print('source,id:', extract_external_id('https://www.instagram.com/p/Cdef456XYZ/'))
"
```

**Expected output:**
```
yt: dQw4w9WgXcQ
ig: Cabc123XYZ
source,id: ('instagram', 'Cdef456XYZ')
```

**If Task Fails:**
- `NameError: extract_external_id` → Step 2 not applied; check it lives at module scope, not inside a class.
- `TypeError` during register → verify Step 4 uses `await repo.get_by_external_id(external_id, source=source)`.
- Rollback: `git checkout -- app/services/managers.py`

---

## Task 12: Refactor `VideoDownloadManager` to use the Strategy (mirror of Task 11)

**Files:**
- Modify: `app/services/managers.py:647-963` (the `VideoDownloadManager` class methods `extract_youtube_id`, `register_video_for_download`, `download_video_with_status_async`)

**Prerequisites:**
- Task 11 complete.

**Step 1: Replace `VideoDownloadManager.extract_youtube_id`**

In `app/services/managers.py`, REPLACE the existing `VideoDownloadManager.extract_youtube_id` (lines 666–696) with:

```python
    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Legacy: returns the external_id for any supported URL."""
        try:
            _, ext_id = extract_external_id(url)
            return ext_id
        except ValueError as exc:
            logger.warning(f"URL não suportada para extração de ID: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Erro ao extrair ID externo: {exc}")
            return None
```

**Step 2: Replace `register_video_for_download`**

REPLACE `register_video_for_download` (lines 731–813) with:

```python
    async def register_video_for_download(
        self, url: str, resolution: str = "1080p"
    ) -> str:
        """Registra um vídeo para download com status 'downloading'."""
        try:
            logger.info(f"Registrando vídeo para download: {url}")

            downloader = get_downloader(url)
            source = downloader.source

            external_id = downloader.extract_id(url)
            if not external_id:
                external_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            async with get_db_context() as session:
                repo = VideoRepository(session)
                existing = await repo.get_by_external_id(external_id, source=source)

                if existing is not None:
                    if existing.download_status not in ("error", ""):
                        logger.info(
                            f"Vídeo já existe (source={source}, ext_id={external_id})"
                        )
                        return existing.id
                    logger.info(
                        f"Vídeo {existing.id} estava com status '{existing.download_status}', "
                        "resetando para nova tentativa"
                    )
                    await repo.update(
                        existing.id,
                        download_status="downloading",
                        download_progress=0,
                        download_error="",
                    )
                    return existing.id

            title = f"Video_{external_id}"
            duration = None
            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, downloader.get_info, url)
                title = info.get("title") or title
                duration = info.get("duration")
            except Exception as extract_error:
                logger.warning(f"Erro ao extrair informações: {extract_error}")

            youtube_id_value = external_id if source == "youtube" else None

            async with get_db_context() as session:
                repo = VideoRepository(session)
                video = Video(
                    id=external_id,
                    title=title,
                    name=f"{title}.mp4",
                    source=source,
                    external_id=external_id,
                    youtube_id=youtube_id_value,
                    url=url,
                    path="",
                    directory="",
                    format="mp4",
                    filesize=0,
                    duration=duration,
                    resolution=resolution,
                    download_status="downloading",
                    download_progress=0,
                    download_error="",
                )
                await repo.create(video)

            logger.info(f"Vídeo registrado: id={external_id} source={source}")
            return external_id

        except ValueError as ve:
            logger.error(f"URL não suportada: {ve}")
            raise
        except Exception as e:
            logger.error(f"Erro ao registrar vídeo: {e}")
            raise
```

**Step 3: Refactor `download_video_with_status_async` to use Strategy opts**

In `download_video_with_status_async` (lines 815–963), locate the `ydl_opts = { ... }` dict literal (around lines 853–875) — the one that includes `"format": format_str` — and REPLACE it (the entire dict literal up to and including `**get_yt_dlp_cookies_opts(),`) with:

```python
            downloader = get_downloader(url)
            ydl_opts = downloader.build_video_opts(
                output_dir=str(download_dir),
                resolution=resolution,
                progress_hook=simple_progress_hook,
            )
```

Also remove the now-unused `format_str = self.RESOLUTION_MAP.get(...)` line that immediately preceded it.

**Step 4: DO NOT refactor `VideoStreamManager` in v1**

`VideoStreamManager.get_direct_url` relies on the format selector `"best[ext=mp4]"` to make yt-dlp surface a top-level `info["url"]`. The Strategy's `get_info` does not select a format, so swapping it in would regress YouTube streaming (the top-level `url` key disappears and `info` only carries `formats: [...]`).

For v1, leave `VideoStreamManager.__init__` and `VideoStreamManager.get_direct_url` UNTOUCHED. Streaming continues to work only for YouTube URLs — which matches the existing API contract. A future task can introduce `Downloader.build_stream_opts()` to extend streaming to Instagram. Document this explicitly:

In `app/services/managers.py`, INSERT this docstring/comment immediately above `class VideoStreamManager:` (around line 48):

```python
# v1 scope: VideoStreamManager is intentionally NOT refactored to use the
# Downloader Strategy. It depends on yt-dlp's "best[ext=mp4]" format selector
# to expose a top-level info["url"], which the Strategy's get_info() does not
# guarantee. Streaming remains YouTube-only until a future
# Downloader.build_stream_opts() lands. Instagram playback (when needed)
# would use the downloaded file path via existing /audio/stream / /video/stream
# file-based endpoints.
```

No code changes inside `VideoStreamManager` for this task. Skip directly to Step 5.

**Step 5: Verify the whole module imports cleanly**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "from app.services.managers import VideoStreamManager, AudioDownloadManager, VideoDownloadManager, extract_external_id; print('OK')"
```

**Expected output:** `OK`

**Step 6: Verify app still boots end-to-end**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  timeout 6 uv run uvicorn app.uwtv.main:app --host 127.0.0.1 --port 8765 2>&1 | grep -E "(Aplicação iniciada|ERROR|Traceback)" | tail -10
```

**Expected output:** `INFO ... Aplicação iniciada com sucesso!` — no `ERROR` or `Traceback` lines.

**If Task Fails:**
- Boot fails with `ImportError` on `get_downloader` → ensure Task 11 Step 1 added the import at the top of `managers.py`.
- Regression: legacy YouTube streaming breaks → confirm `VideoStreamManager.get_direct_url` was NOT changed (Step 4 says: leave untouched).
- General rollback → `git checkout -- app/services/managers.py` and re-apply step-by-step.

---

## Task 13: Update playlist allowlist comment + factory check (YouTube-only for v1)

**Files:**
- Modify: `app/services/managers.py:552-558` and `app/services/managers.py:1115-1121` (the `_ALLOWED_HOSTS` sets inside `extract_playlist_info`)

**Prerequisites:**
- Task 12 complete.

**Rationale:** `extract_playlist_info` lives on both managers with a hard-coded YouTube allowlist. Instagram has no native playlist concept that yt-dlp can flat-extract via the same path. Keep the allowlist YouTube-only, but ADD a comment clarifying the intentional scope for v1.

**Step 1: Add scoping comment in `AudioDownloadManager.extract_playlist_info`**

In `app/services/managers.py`, locate (around line 552):

```python
        # TODO(review): move _ALLOWED_HOSTS to module-level constant to avoid per-call allocation - code-reviewer, 2026-04-28, Severity: Low
        _ALLOWED_HOSTS = {
            "youtube.com",
            "www.youtube.com",
            "youtu.be",
            "music.youtube.com",
            "m.youtube.com",
        }
```

INSERT immediately above that block (right after the `import urllib.parse` line):

```python
        # NOTE: Playlist support is YouTube-only for v1. Instagram has no
        # native playlist concept that maps cleanly to yt-dlp's flat extractor.
        # Tracked as a non-goal in docs/plans/2026-05-13-instagram-support.md.
```

**Step 2: Repeat in `VideoDownloadManager.extract_playlist_info`**

Same insertion in the duplicate at line ~1115. Do not change the allowlist set itself.

**Step 3: Verify the file still parses**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run python -c "import ast; ast.parse(open('app/services/managers.py').read()); print('OK')"
```

**Expected output:** `OK`

**If Task Fails:**
- `SyntaxError` → re-check indentation (the comment must use the same level as the surrounding code).

---

## Task 14: Frontend — generalize URL validation and update placeholders

**Files:**
- Modify: `web_client/js/app.js:171-173` (`validateYouTubeUrl`)
- Modify: `web_client/index.html` (only placeholder strings at lines 129 and 157 — labels stay)

**Prerequisites:**
- Task 13 complete.

**Step 1: Generalize the validator**

In `web_client/js/app.js`, REPLACE lines 171–173:

```javascript
    function validateYouTubeUrl(url) {
        return url && (url.includes('youtube.com/') || url.includes('youtu.be/'));
    }
```

with:

```javascript
    function validateVideoUrl(url) {
        if (!url) return false;
        return (
            url.includes('youtube.com/') ||
            url.includes('youtu.be/') ||
            url.includes('instagram.com/')
        );
    }

    // Backward-compat alias — remove in a future cleanup pass.
    function validateYouTubeUrl(url) {
        return validateVideoUrl(url);
    }
```

**Step 2: Update toast messages at the two call sites**

In `web_client/js/app.js`, REPLACE line 512:

```javascript
            showToast('Por favor, insira uma URL válida do YouTube', 'warning');
```

with:

```javascript
            showToast('Por favor, insira uma URL válida do YouTube ou Instagram', 'warning');
```

REPLACE line 562 (identical string in `downloadVideo`):

```javascript
            showToast('Por favor, insira uma URL válida do YouTube', 'warning');
```

with:

```javascript
            showToast('Por favor, insira uma URL válida do YouTube ou Instagram', 'warning');
```

**Step 3: Update the two URL input placeholders in `index.html`**

In `web_client/index.html`, REPLACE the placeholder on line 129:

```html
                                           placeholder="https://www.youtube.com/watch?v=...">
```

with:

```html
                                           placeholder="https://www.youtube.com/watch?v=... ou https://www.instagram.com/reel/...">
```

REPLACE the placeholder on line 157 (same string in the video form):

```html
                                           placeholder="https://www.youtube.com/watch?v=...">
```

with:

```html
                                           placeholder="https://www.youtube.com/watch?v=... ou https://www.instagram.com/reel/...">
```

**Note:** the visible labels and the `<title>` "YouTube Downloader" stay unchanged — out of scope for v1.

**Step 4: Verify JS syntax via node**

```bash
node --check /media/marvinbraga/python/marvin/youtube_downloader/web_client/js/app.js && echo OK
```

**Expected output:**
```
OK
```

**If Task Fails:**
- `SyntaxError` from node → re-check brackets in the new function.
- Rollback: `git checkout -- web_client/js/app.js web_client/index.html`

---

## Task 15: Code review checkpoint (Tasks 8–14)

**REQUIRED SUB-SKILL:** Use ring:codereview.

1. Dispatch all 10 reviewers in parallel.
2. Files in scope:
   - `app/services/downloaders/__init__.py`
   - `app/services/downloaders/base.py`
   - `app/services/downloaders/youtube.py`
   - `app/services/downloaders/instagram.py`
   - `app/services/downloaders/factory.py`
   - `app/services/managers.py`
   - `web_client/js/app.js`
   - `web_client/index.html`
3. Handle findings per severity (Critical/High/Medium fixed; Low → `TODO(review):`; Cosmetic → `FIXME(nitpick):`).
4. Proceed only when Critical/High/Medium = 0.

**Specific concerns to flag for reviewers:**
- Strategy duplication: are `_COMMON_HEADERS` / `*_HOSTS` repeated across files where they could be deduped?
- Instagram regex: does it correctly reject `instagram.com/some-profile/` (it must)?
- Dedup correctness: does `register_*_for_download` use `(source, external_id)` in EVERY lookup path?
- `VideoStreamManager.__init__` removal: is the old `self.ydl_opts` attribute referenced anywhere else in the codebase?

---

## Task 16: Manual integration tests (server up)

**Files:** none modified — verification only.

**Prerequisites:**
- All previous tasks done. App boots cleanly.
- A YouTube video URL ready: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- An Instagram public reel URL ready (any current public reel, e.g. ask reviewer to provide one — the executor SHOULD use a known-public account such as `@instagram` for testing).

**Step 1: Start the server**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  uv run uvicorn app.uwtv.main:app --host 127.0.0.1 --port 8000 &
echo $! > /tmp/uvicorn.pid
sleep 4
```

**Expected output:** Process backgrounded. Server logs `Aplicação iniciada com sucesso!`.

**Step 2: Obtain a JWT token**

(Adjust `CLIENT_ID` / `CLIENT_SECRET` to the values configured in `app/services/securities.py` — these are environment-dependent. The default dev pair is `client_id=streaming_client` / `client_secret=streaming_secret` per the existing app config; CONFIRM in `app/services/securities.py` before running.)

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"client_id":"<from-securities.py>","client_secret":"<from-securities.py>"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
echo "Token length: ${#TOKEN}"
```

**Expected output:** `Token length:` followed by a 3-digit number > 100.

**Step 3: Regression — download a YouTube audio**

```bash
curl -s -X POST http://127.0.0.1:8000/audio/download \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","high_quality":true}'
```

**Expected output (JSON):**
```json
{"status":"processando","message":"...","audio_id":"dQw4w9WgXcQ", ...}
```

Then wait ~30 seconds and verify status:

```bash
sleep 30
curl -s -X GET http://127.0.0.1:8000/audio/list \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -40
```

**Expected output:** the `dQw4w9WgXcQ` entry has `"download_status": "ready"`, `"source": "youtube"`, `"external_id": "dQw4w9WgXcQ"`, `"youtube_id": "dQw4w9WgXcQ"`.

**Step 4: New feature — download an Instagram reel as audio**

```bash
curl -s -X POST http://127.0.0.1:8000/audio/download \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.instagram.com/reel/<PUBLIC_SHORTCODE>/","high_quality":true}'
```

(Replace `<PUBLIC_SHORTCODE>` with a current public reel.)

**Expected output (JSON):** `{"status":"processando", "audio_id":"<shortcode>", ...}`.

Then verify in DB:

```bash
sleep 30
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT id, source, external_id, youtube_id, download_status FROM audios WHERE source='instagram';"
```

**Expected output:** at least one row with `source=instagram`, `external_id=<shortcode>`, `youtube_id` is `NULL` (or empty), `download_status=ready`.

**Step 5: Dedup test — register the same Instagram reel twice**

Run the same POST from Step 4 again. **Expected output:** same JSON shape, but server logs show `Áudio já existe (source=instagram, ext_id=<shortcode>)`. No duplicate row appears in `audios`.

**Step 6: Video download — Instagram reel**

```bash
curl -s -X POST http://127.0.0.1:8000/video/download \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.instagram.com/reel/<PUBLIC_SHORTCODE>/","resolution":"1080p"}'
```

**Expected output:** `{"status":"processando", "video_id":"<shortcode>", ...}`. Wait ~60 seconds; the file should appear under `downloads/videos/<shortcode>/`.

**Step 7: Negative test — unsupported host**

```bash
curl -s -X POST http://127.0.0.1:8000/audio/download \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://vimeo.com/12345","high_quality":true}'
```

**Expected output:** HTTP 500 with detail containing `URL não suportada (host 'vimeo.com')`.

**Step 8: Migration regression — confirm pre-existing rows are intact**

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT COUNT(*) AS legacy_yt_audios FROM audios WHERE source='youtube' AND external_id IS NOT NULL AND external_id = youtube_id;"
```

**Expected output:** integer >= the pre-migration `audios` count from Task 1 Step 2.

**Step 9: Stop the server**

```bash
kill "$(cat /tmp/uvicorn.pid)"
rm /tmp/uvicorn.pid
```

**Expected output:** server process terminated.

**If Task Fails:**
- Instagram download fails with HTTP 403 / 404 → the reel may no longer be public OR yt-dlp's Instagram extractor needs cookies. Set `INSTAGRAM_COOKIES_FILE=/path/to/cookies.txt` and retry. If even with cookies it fails, capture the yt-dlp error from server logs (`YT_DLP_VERBOSE=1 uv run uvicorn ...`).
- Dedup test creates a second row → `get_by_external_id` is being called without the `source=` filter. Re-check Task 11 Step 4 and Task 12 Step 2.
- Legacy YouTube audio fails after migration → restore DB backup from Task 1 Step 3 and re-run the migration once. `cp data/youtube_downloader.db.bak-2026-05-13 data/youtube_downloader.db`.

---

## Task 17: Frontend smoke test (manual, browser)

**Files:** none modified.

**Prerequisites:**
- Server running on port 8000.
- Browser available.

**Step 1: Open the SPA**

Navigate to `http://127.0.0.1:8000/static/index.html`.

**Step 2: Verify the URL inputs accept Instagram**

- Type a YouTube URL into the audio download field → click Download → toast says "Download de áudio iniciado com sucesso!".
- Replace with an Instagram reel URL → click Download → same success toast (no "URL inválida do YouTube" warning).
- Type `https://vimeo.com/12345` → click Download → either client validator rejects ("URL válida do YouTube ou Instagram") OR backend returns the 500 from Task 16 Step 7. Both are acceptable.

**Step 3: Verify list rendering**

After downloads finish, both YouTube and Instagram entries appear in the audio list with their thumbnails / status badges rendered correctly.

**Step 4: Verify playback still works for legacy YouTube videos**

Click a pre-existing YouTube video's play button. **Expected:** video plays in the player (regression check for `VideoStreamManager.get_direct_url`).

**If Task Fails:**
- Toast "URL inválida do YouTube" still appears for Instagram → `validateVideoUrl` is being shadowed; check that the new function is defined and `validateYouTubeUrl` aliases it.
- Old YouTube playback breaks → `VideoStreamManager.get_direct_url` refactor (Task 12 Step 4) is wrong. Restore the legacy implementation as a fallback and retry.

---

## Task 18: Final code review checkpoint

**REQUIRED SUB-SKILL:** Use ring:codereview.

Run all 10 reviewers on the **cumulative diff** of the branch vs `master`:

```bash
git -C /media/marvinbraga/python/marvin/youtube_downloader diff master...HEAD --stat
```

Handle findings per the severity rules (Task 7). Proceed only when Critical/High/Medium = 0.

---

## Task 19: Commit and prepare for PR

**Files:** none modified.

**Prerequisites:** all previous tasks complete; no uncommitted code-changing files except those covered by this plan.

**Step 1: Inspect the diff**

```bash
git -C /media/marvinbraga/python/marvin/youtube_downloader status
git -C /media/marvinbraga/python/marvin/youtube_downloader diff --stat master...HEAD
```

**Expected output:** Changed files include `app/db/models.py`, `app/db/database.py`, `app/db/repositories.py`, `app/models/audio.py`, `app/models/video.py`, `app/services/configs.py`, `app/services/managers.py`, the new `app/services/downloaders/*`, `web_client/js/app.js`, `web_client/index.html`, and this plan file.

**Step 2: Stage and commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader && \
  git add app/db/models.py app/db/database.py app/db/repositories.py \
          app/models/audio.py app/models/video.py \
          app/services/configs.py app/services/managers.py \
          app/services/downloaders \
          web_client/js/app.js web_client/index.html \
          docs/plans/2026-05-13-instagram-support.md && \
  git commit -m "$(cat <<'EOF'
feat: add Instagram support via Strategy pattern

- Introduce Downloader abstract base + YouTubeDownloader / InstagramDownloader
- Add source + external_id columns (idempotent ALTER TABLE backfill)
- Route by URL netloc via factory; keep youtube_id as legacy alias
- Frontend: validateVideoUrl accepts instagram.com URLs
- Playlists remain YouTube-only for v1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

**Step 3: Verify the commit**

```bash
git -C /media/marvinbraga/python/marvin/youtube_downloader log -1 --stat
```

**Expected output:** the commit shows the expected files and the message above.

**If Task Fails:**
- Pre-commit hook fails → fix the issue, re-stage, create a NEW commit (do not `--amend`).
- Backup file `data/youtube_downloader.db.bak-2026-05-13` accidentally staged → unstage with `git restore --staged data/youtube_downloader.db.bak-2026-05-13`.

---

## Plan Checklist

- [x] Header with goal, architecture, tech stack, prerequisites
- [x] Verification commands with expected output
- [x] Tasks broken into bite-sized steps (2-5 min each)
- [x] Exact file paths for all files
- [x] Complete code (no placeholders)
- [x] Exact commands with expected output
- [x] Failure recovery steps for each task
- [x] Code review checkpoints after batches (Tasks 7, 15, 18)
- [x] Severity-based issue handling documented
- [x] Passes Zero-Context Test
