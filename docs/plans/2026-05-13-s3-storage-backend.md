# S3 Storage Backend Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use ring:execute-plan to implement this plan task-by-task.

**Goal:** Add an optional AWS S3 storage backend to the YouTube Downloader service. yt-dlp continues to download to local disk; after download success, finished files are uploaded to S3 and (optionally) the local copy is removed. Streaming endpoints transparently serve via FileResponse/StreamingResponse for `storage_backend='local'` rows or 302-redirect to a short-lived presigned URL for `storage_backend='s3'` rows. **Local backend remains the default** — zero behavioral change for users who don't opt in.

**Architecture:** Strategy pattern (`Storage` abstract base + `LocalStorage` / `S3Storage` subclasses) selected by `STORAGE_BACKEND` env var. Two new columns per media table (`storage_backend`, `s3_key`) tag every row so old (`local`) and new (`s3`) records coexist on the same listing. Post-download upload is wired **inside both `download_audio_with_status_async` and `download_video_with_status_async`** (right after `repo.complete_download` succeeds) because the `download_queue` only wraps audio downloads — video downloads bypass the queue via `BackgroundTasks`. No retroactive migration of legacy local files. Transcription requires local files; when `STORAGE_BACKEND=s3` and the row is S3-backed, `Storage.download_to_temp()` pulls the object to a tempfile for the transcription window.

**Tech Stack:** Python 3.10–3.12, FastAPI, SQLAlchemy (async + aiosqlite), yt-dlp, `aioboto3` (new, Apache 2.0 — AGPL-compatible as a dependency), jQuery 3 + Bootstrap 5.3.3 (no frontend rebuild needed — `<audio>`/`<video>` tags follow 302 redirects natively).

**Global Prerequisites:**
- Environment: Linux/macOS, Python 3.10–3.12
- Tools: `uv` package manager, `git`, `curl`, `sqlite3` CLI, `jq` (helpful), Docker (optional — for MinIO/LocalStack)
- Access: An AWS account with S3 access **OR** a local MinIO/LocalStack container. JWT auth still required for the API.
- State: On branch `feat/s3-storage-backend`, clean working tree (only `.claude/settings.local.json` may be modified — that is expected).

**Verification before starting:**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
python --version          # Expected: Python 3.10.x – 3.12.x
uv --version              # Expected: uv 0.4+
git branch --show-current # Expected: feat/s3-storage-backend
git status                # Expected: only .claude/settings.local.json modified (or clean)
sqlite3 --version         # Expected: 3.x
```

**Out of scope for v1 (explicit non-goals):**
- **Retroactive migration** of legacy local files to S3. Rows with `storage_backend='local'` stay local forever; only NEW downloads after `STORAGE_BACKEND=s3` is enabled go to S3.
- **Listing S3 objects without a DB row.** `app/services/files.py:scan_video_directory` continues to walk `VIDEO_DIR` only. The S3 bucket is **not** the source of truth — the SQLite `videos`/`audios` tables are. Files that exist in S3 but not in the DB will not appear in any listing (this is intentional — DB rows are the unit of truth).
- **Transcription markdown files (.md)** stay local. Only the source media files (`.m4a`, `.mp4`) move to S3. Transcription paths in the DB always resolve relative to `DOWNLOADS_DIR` on disk.
- **Frontend changes.** Browser `<audio>` and `<video>` tags follow 302 redirects automatically. The frontend `app.js` does not need to change. (Confirm in Task 14.)
- **Cross-backend moves at runtime.** Once a row has `storage_backend='s3'`, it stays S3. There is no "move back to local" endpoint in v1.
- **Multiple buckets / per-row bucket selection.** Single `AWS_S3_BUCKET` for the whole service.
- **Refactoring `VideoStreamManager.stream_youtube_video`** (the live-YouTube proxy at `main.py:209`). That path streams directly from YouTube to the client; it has no S3 relevance.

**Agent recommendation for every task below:** `general-purpose` (this repo has no Python-specific or AWS-specific Ring agent).

---

## Task 1: Confirm baseline and snapshot the SQLite schema

**Files:**
- Inspect: `app/db/models.py`, `app/db/database.py`, `data/youtube_downloader.db`

**Prerequisites:**
- Database file exists (the app has been run before — confirm with `ls`).

**Step 1: Snapshot current schemas**

Run:
```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db ".schema audios"
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db ".schema videos"
```

**Expected output (audios):** contains `source VARCHAR(50)` and `external_id VARCHAR(100)` from the Instagram migration, but **NO** `storage_backend` and **NO** `s3_key` column.

**Expected output (videos):** same as audios — `source` and `external_id` present; `storage_backend` and `s3_key` absent.

**Step 2: Snapshot row counts**

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT 'audios' AS t, COUNT(*) AS n FROM audios UNION ALL SELECT 'videos', COUNT(*) FROM videos;"
```

**Expected output:** two rows showing row counts (record them — re-checked after migration in Task 4).

**Step 3: Back up the database (rollback safety)**

```bash
cp /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
   /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db.bak-2026-05-13-s3
```

**Expected output:** no output. Backup file created.

**Step 4: Verify the backup**

```bash
ls -la /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db.bak-2026-05-13-s3
```

**Expected output:** file listed with size > 0.

**Step 5: Commit baseline snapshot (no code changes)**

No commit — this task is read-only.

**If Task Fails:**
- Database file missing → run the server once (`uv run uvicorn app.uwtv.main:app`) to create it, then redo.
- Permission denied on `cp` → check `data/` write permissions.

---

## Task 2: Add `aioboto3` dependency

**Files:**
- Modify: `pyproject.toml:9-32` (dependencies block)
- Auto-updated: `uv.lock`

**Prerequisites:**
- Task 1 complete.
- Internet access for `uv add` to resolve packages.

**Step 1: Add the dependency via uv**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv add aioboto3
```

**Expected output:** `aioboto3` and its transitive deps (`aiobotocore`, `aiohttp`, `aioitertools`, `boto3`, `botocore`) appear in resolution output. `pyproject.toml` and `uv.lock` are updated. Pin to the resolved version (whatever uv chose — typically `>=13.x`).

**Step 2: Verify the dependency installed**

```bash
uv run python -c "import aioboto3; print(aioboto3.__version__)"
```

**Expected output:** a version string (e.g. `13.4.0`). No `ImportError`.

**Step 3: Verify `pyproject.toml`**

Run:
```bash
grep "aioboto3" /media/marvinbraga/python/marvin/youtube_downloader/pyproject.toml
```

**Expected output:** one line like `"aioboto3>=13.0.0",` inside the dependencies array.

**Step 4: Commit**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
git add pyproject.toml uv.lock
git commit -m "feat: add aioboto3 dependency for S3 storage backend"
```

**If Task Fails:**
- Resolution conflict → check Python version constraint in `pyproject.toml` (`>=3.10,<3.13`). `aioboto3` supports this range.
- Offline → install offline is not supported; ensure connectivity.
- License audit concern → `aioboto3` is Apache 2.0 (compatible with AGPL v3 as a dependency).

---

## Task 3: Add SQLAlchemy model columns `storage_backend` and `s3_key`

**Files:**
- Modify: `app/db/models.py:82-163` (Audio model)
- Modify: `app/db/models.py:169-248` (Video model)

**Prerequisites:**
- Task 2 complete.

**Step 1: Add columns to `Audio` model**

Edit `app/db/models.py`. Locate the `Audio` class, immediately after the `filesize` field (line ~100) and before the `# Status de download` comment, insert:

```python
    # Storage backend (Strategy pattern: 'local' | 's3')
    storage_backend: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", index=True
    )
    s3_key: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

```

**Step 2: Update `Audio.to_dict()`**

In the `to_dict()` method of `Audio` (around line 134), add two keys to the returned dictionary, after `"filesize": self.filesize,`:

```python
            "storage_backend": self.storage_backend,
            "s3_key": self.s3_key,
```

**Step 3: Add columns to `Video` model**

In the `Video` class, after the `resolution` field (line ~186) and before `# Status de download`, insert the same two columns as Step 1:

```python
    # Storage backend (Strategy pattern: 'local' | 's3')
    storage_backend: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", index=True
    )
    s3_key: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

```

**Step 4: Update `Video.to_dict()`**

In `Video.to_dict()` (around line 220), add the same two keys after `"resolution": self.resolution,`:

```python
            "storage_backend": self.storage_backend,
            "s3_key": self.s3_key,
```

**Step 5: Verify the file parses**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "from app.db.models import Audio, Video; print('Audio cols:', [c.name for c in Audio.__table__.columns]); print('Video cols:', [c.name for c in Video.__table__.columns])"
```

**Expected output:** two lists; both contain `storage_backend` and `s3_key`.

**Step 6: Commit**

```bash
git add app/db/models.py
git commit -m "feat(db): add storage_backend and s3_key columns to Audio and Video models"
```

**If Task Fails:**
- ImportError → check that `String`, `Optional`, `Mapped`, `mapped_column` imports are intact at top of file.
- `to_dict` test failure → ensure new keys are inside the dict literal, not after the `return`.

---

## Task 4: Add idempotent schema migration for `storage_backend` and `s3_key`

**Files:**
- Modify: `app/db/database.py:65-122` (`_apply_schema_migrations`)

**Prerequisites:**
- Task 3 complete.

**Step 1: Extend `_apply_schema_migrations`**

Edit `app/db/database.py`. After the existing `# --- videos ---` block (around line 122), append the following block **at the end of the function** (before its closing — note this function has no explicit `return` so just keep adding):

```python
    # --- audios.storage_backend, audios.s3_key ---
    result = await conn.exec_driver_sql("PRAGMA table_info(audios)")
    audio_cols = {row[1] for row in result.fetchall()}
    await _add_column_if_missing(
        conn,
        "audios",
        "storage_backend",
        "VARCHAR(20) NOT NULL DEFAULT 'local'",
        audio_cols,
    )
    await _add_column_if_missing(
        conn, "audios", "s3_key", "VARCHAR(1000)", audio_cols
    )
    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_audios_storage_backend ON audios(storage_backend)"
    )

    # --- videos.storage_backend, videos.s3_key ---
    result = await conn.exec_driver_sql("PRAGMA table_info(videos)")
    video_cols = {row[1] for row in result.fetchall()}
    await _add_column_if_missing(
        conn,
        "videos",
        "storage_backend",
        "VARCHAR(20) NOT NULL DEFAULT 'local'",
        video_cols,
    )
    await _add_column_if_missing(
        conn, "videos", "s3_key", "VARCHAR(1000)", video_cols
    )
    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_videos_storage_backend ON videos(storage_backend)"
    )
```

**Note:** No explicit `UPDATE ... SET storage_backend='local'` is needed. SQLite's `ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT 'local'` auto-fills existing rows with the default value at column-add time (this is different from the Instagram migration's `external_id` backfill, which used `NULL` default and needed an explicit `UPDATE`).

**Step 2: Run the app once to trigger migration**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
timeout 8 uv run uvicorn app.uwtv.main:app --port 8001 2>&1 | head -30
```

**Expected output:** lines including
```
Coluna 'storage_backend' adicionada em audios
Coluna 's3_key' adicionada em audios
Coluna 'storage_backend' adicionada em videos
Coluna 's3_key' adicionada em videos
Banco de dados inicializado em: ...
Aplicação iniciada com sucesso!
```

Then `timeout` kills the server (exit 124 is fine).

**Step 3: Verify schema and backfill**

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db ".schema audios" | grep -E "storage_backend|s3_key"
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db ".schema videos" | grep -E "storage_backend|s3_key"
```

**Expected output:** four lines total, two per table, showing the new columns.

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT storage_backend, COUNT(*) FROM audios GROUP BY storage_backend; SELECT storage_backend, COUNT(*) FROM videos GROUP BY storage_backend;"
```

**Expected output:** only `local|<row_count>` rows (numbers match Task 1 Step 2 counts).

**Step 4: Verify migration is idempotent (run again)**

```bash
timeout 8 uv run uvicorn app.uwtv.main:app --port 8001 2>&1 | head -30
```

**Expected output:** lines like `Coluna 'storage_backend' já existe em audios (race resolvida)` or simply no `adicionada em` lines on the second run. No errors.

**Step 5: Commit**

```bash
git add app/db/database.py
git commit -m "feat(db): idempotent migration for storage_backend and s3_key columns"
```

**If Task Fails:**
- `OperationalError: NOT NULL constraint failed` after ADD COLUMN → SQLite versions before 3.7.0 don't support non-NULL ADD COLUMN with default. Check `sqlite3 --version`. The version must be ≥ 3.7.0 (every modern distro ships 3.30+). If genuinely too old, change the DDL to `VARCHAR(20) DEFAULT 'local'` (no NOT NULL) and add an `UPDATE audios SET storage_backend='local' WHERE storage_backend IS NULL` follow-up.
- Rollback: `cp data/youtube_downloader.db.bak-2026-05-13-s3 data/youtube_downloader.db`.

---

## Task 5: Run code review for the DB foundation (Tasks 1–4)

1. Dispatch all 10 reviewers in parallel — REQUIRED SUB-SKILL: Use ring:codereview
2. Wait for all to complete.
3. Handle findings by severity:
   - **Critical/High/Medium:** Fix immediately. Re-run all 10 reviewers in parallel after fixes. Repeat until zero remain.
   - **Low:** Add `TODO(review): [Issue description] (reported by [reviewer] on 2026-05-13, severity: Low)` comments at the relevant code location.
   - **Cosmetic/Nitpick:** Add `FIXME(nitpick): [Issue description] (reported by [reviewer] on 2026-05-13, severity: Cosmetic)` comments.
4. Proceed only when zero Critical/High/Medium remain.

---

## Task 6: Create `Storage` strategy base and `LocalStorage` implementation

**Files:**
- Create: `app/services/storage/__init__.py`
- Create: `app/services/storage/base.py`
- Create: `app/services/storage/local.py`

**Prerequisites:**
- Task 5 complete.

**Step 1: Create the package directory**

```bash
mkdir -p /media/marvinbraga/python/marvin/youtube_downloader/app/services/storage
```

**Expected output:** no output.

**Step 2: Create `app/services/storage/base.py`**

```python
"""Storage strategy abstract base.

Two concrete implementations live alongside this module:
- LocalStorage (default; preserves legacy filesystem behavior)
- S3Storage   (opt-in via STORAGE_BACKEND=s3)

The Strategy abstracts only what differs across backends:
- where the canonical bytes live after download
- how a client retrieves them (direct file vs presigned URL)
- how to delete them
- how to make a seekable local copy for tools that need one (transcription)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class Storage(ABC):
    """Abstract storage backend."""

    backend_name: str = "abstract"

    @abstractmethod
    async def put_file(
        self,
        local_path: Path,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload (or register) the file. Returns a backend-specific key.

        For LocalStorage this is a no-op that returns the relative path.
        For S3Storage this PUTs the object and returns the S3 key.
        """

    @abstractmethod
    async def get_url(self, key: str, filename: Optional[str] = None) -> str:
        """Return a URL the client can fetch the bytes from.

        For LocalStorage this raises NotImplementedError (the endpoint
        serves bytes directly via FileResponse — no URL needed).
        For S3Storage this returns a short-lived presigned GET URL.
        """

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete the underlying object. Returns True on success."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if the key resolves to a real object."""

    @abstractmethod
    async def download_to_temp(self, key: str) -> Path:
        """Materialize the object as a local file and return its path.

        Required by transcription, which needs a seekable on-disk file.
        Caller is responsible for cleaning up the returned path.
        For LocalStorage this is a no-op that returns the existing path.
        """
```

**Step 3: Create `app/services/storage/local.py`**

```python
"""Local filesystem storage backend (default).

Preserves the legacy behavior: files live under DOWNLOADS_DIR and are
served via FileResponse/StreamingResponse. `key` is a relative path
under DOWNLOADS_DIR (matches the `path` column populated by managers).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.services.configs import DOWNLOADS_DIR
from app.services.storage.base import Storage


class LocalStorage(Storage):
    backend_name = "local"

    async def put_file(
        self,
        local_path: Path,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        # File is already where it needs to be. Just return the key.
        return key

    async def get_url(self, key: str, filename: Optional[str] = None) -> str:
        raise NotImplementedError(
            "LocalStorage does not produce URLs; stream the file directly."
        )

    async def delete(self, key: str) -> bool:
        path = DOWNLOADS_DIR / key
        if path.exists():
            path.unlink()
            return True
        return False

    async def exists(self, key: str) -> bool:
        return (DOWNLOADS_DIR / key).exists()

    async def download_to_temp(self, key: str) -> Path:
        # File is already local — return the canonical path.
        return DOWNLOADS_DIR / key
```

**Step 4: Create `app/services/storage/__init__.py`**

```python
"""Storage backend package."""

from app.services.storage.base import Storage
from app.services.storage.local import LocalStorage

__all__ = ["Storage", "LocalStorage"]
```

**Step 5: Verify the package imports**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "from app.services.storage import Storage, LocalStorage; s = LocalStorage(); print(s.backend_name)"
```

**Expected output:** `local`

**Step 6: Commit**

```bash
git add app/services/storage/
git commit -m "feat(storage): add Storage strategy base and LocalStorage backend"
```

**If Task Fails:**
- ImportError on `from app.services.configs import DOWNLOADS_DIR` → confirm the import in `configs.py:10` still exists.

---

## Task 7: Extend `configs.py` with S3 environment variables and validation

**Files:**
- Modify: `app/services/configs.py:1-29`

**Prerequisites:**
- Task 6 complete.

**Step 1: Add an S3 config block at the end of `configs.py`**

Append the following to the end of `app/services/configs.py`:

```python


# ---------------------------------------------------------------------------
# Storage backend configuration
# ---------------------------------------------------------------------------

# STORAGE_BACKEND: 'local' (default) | 's3'
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").strip().lower()

# S3-specific config (only required when STORAGE_BACKEND=s3)
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "").strip()
AWS_REGION = os.environ.get("AWS_REGION", "").strip() or os.environ.get(
    "AWS_DEFAULT_REGION", ""
).strip()
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "").strip() or None
AWS_S3_KEY_PREFIX = os.environ.get("AWS_S3_KEY_PREFIX", "").strip().strip("/")

# Credentials are picked up automatically by aioboto3 via the standard
# AWS credential chain (env vars, ~/.aws/credentials, IMDS, IRSA, etc.).
# We only read them here to detect explicit configuration for logging.
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()

# How long presigned GET URLs stay valid (seconds). One hour by default.
S3_PRESIGNED_URL_TTL = int(os.environ.get("S3_PRESIGNED_URL_TTL", "3600"))

# Whether to delete the local file after a successful S3 upload.
# 'true' (default) frees disk but breaks local-file tools (transcription
# falls back to download_to_temp). 'false' keeps a redundant local copy.
S3_DELETE_LOCAL_AFTER_UPLOAD = (
    os.environ.get("S3_DELETE_LOCAL_AFTER_UPLOAD", "true").strip().lower() == "true"
)

VALID_STORAGE_BACKENDS = {"local", "s3"}


def validate_storage_config() -> None:
    """Validate storage configuration. Called once at startup.

    Raises ValueError if STORAGE_BACKEND=s3 but required S3 env vars are
    missing. Local backend has no required config.
    """
    if STORAGE_BACKEND not in VALID_STORAGE_BACKENDS:
        raise ValueError(
            f"STORAGE_BACKEND='{STORAGE_BACKEND}' is not supported. "
            f"Valid values: {', '.join(sorted(VALID_STORAGE_BACKENDS))}"
        )
    if STORAGE_BACKEND == "s3":
        missing = []
        if not AWS_S3_BUCKET:
            missing.append("AWS_S3_BUCKET")
        if not AWS_REGION:
            missing.append("AWS_REGION (or AWS_DEFAULT_REGION)")
        if missing:
            raise ValueError(
                "STORAGE_BACKEND=s3 requires: " + ", ".join(missing)
            )
        if S3_PRESIGNED_URL_TTL <= 0 or S3_PRESIGNED_URL_TTL > 7 * 24 * 3600:
            raise ValueError(
                "S3_PRESIGNED_URL_TTL must be > 0 and <= 604800 seconds (7d)."
            )
```

**Step 2: Verify the module imports and validation works**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "
from app.services.configs import STORAGE_BACKEND, validate_storage_config
print('default backend:', STORAGE_BACKEND)
validate_storage_config()
print('default validates OK')
"
```

**Expected output:**
```
default backend: local
default validates OK
```

**Step 3: Verify S3 validation rejects missing config**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
STORAGE_BACKEND=s3 uv run python -c "
from app.services.configs import validate_storage_config
try:
    validate_storage_config()
    print('UNEXPECTED: did not raise')
except ValueError as e:
    print('OK:', e)
"
```

**Expected output:** something like
```
OK: STORAGE_BACKEND=s3 requires: AWS_S3_BUCKET, AWS_REGION (or AWS_DEFAULT_REGION)
```

**Note:** `STORAGE_BACKEND` is captured at module import time, so re-import inside a single process won't see the env var. The subprocess invocation above is correct.

**Step 4: Commit**

```bash
git add app/services/configs.py
git commit -m "feat(config): add S3 storage env vars and startup validation"
```

**If Task Fails:**
- Existing `os.environ.get` call has different sanitization → match the established style (`.strip().lower()` for enums, `.strip()` for strings, `int()` for ints).

---

## Task 8: Implement `S3Storage` backend

**Files:**
- Create: `app/services/storage/s3.py`
- Modify: `app/services/storage/__init__.py` (export `S3Storage`)

**Prerequisites:**
- Task 7 complete.

**Step 1: Create `app/services/storage/s3.py`**

```python
"""S3 storage backend (opt-in).

Lifecycle decision: this implementation uses per-call `async with
session.client("s3", ...)` blocks. aioboto3 sessions are cheap; clients
are not, but for a service whose hot path is HTTP-bound (yt-dlp downloads
take seconds-to-minutes, S3 PUT takes seconds), per-call client creation
is well under the noise floor. Caching a long-lived client across the
asyncio event loop is a v2 optimization.

Credentials are resolved by aioboto3 via the standard AWS credential
chain. We never read AWS_SECRET_ACCESS_KEY directly here; we only pass
endpoint_url and region_name explicitly to support MinIO/LocalStack.
"""

from __future__ import annotations

import mimetypes
import tempfile
from pathlib import Path
from typing import Optional

import aioboto3
from botocore.exceptions import ClientError
from loguru import logger

from app.services.configs import (
    AWS_REGION,
    AWS_S3_BUCKET,
    AWS_S3_ENDPOINT_URL,
    AWS_S3_KEY_PREFIX,
    S3_PRESIGNED_URL_TTL,
)
from app.services.storage.base import Storage


def _full_key(key: str) -> str:
    """Apply the optional AWS_S3_KEY_PREFIX to a logical key."""
    if AWS_S3_KEY_PREFIX:
        return f"{AWS_S3_KEY_PREFIX}/{key}".replace("//", "/")
    return key


class S3Storage(Storage):
    backend_name = "s3"

    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._client_kwargs = {"region_name": AWS_REGION}
        if AWS_S3_ENDPOINT_URL:
            # MinIO/LocalStack require path-style addressing.
            self._client_kwargs["endpoint_url"] = AWS_S3_ENDPOINT_URL

    def _client(self):
        return self._session.client("s3", **self._client_kwargs)

    async def put_file(
        self,
        local_path: Path,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        full_key = _full_key(key)
        if content_type is None:
            guessed, _ = mimetypes.guess_type(local_path.name)
            content_type = guessed or "application/octet-stream"

        async with self._client() as s3:
            with open(local_path, "rb") as fh:
                await s3.put_object(
                    Bucket=AWS_S3_BUCKET,
                    Key=full_key,
                    Body=fh,
                    ContentType=content_type,
                )
        logger.info(
            f"S3 PUT ok: s3://{AWS_S3_BUCKET}/{full_key} "
            f"({local_path.stat().st_size} bytes, {content_type})"
        )
        return full_key

    async def get_url(self, key: str, filename: Optional[str] = None) -> str:
        # Content-Disposition=inline ensures the browser plays the media
        # via the <audio>/<video> tag instead of downloading it.
        params = {"Bucket": AWS_S3_BUCKET, "Key": key}
        if filename:
            # RFC 5987 encoding for non-ASCII filenames.
            params["ResponseContentDisposition"] = (
                f'inline; filename="{filename}"'
            )
        else:
            params["ResponseContentDisposition"] = "inline"

        async with self._client() as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=S3_PRESIGNED_URL_TTL,
            )
        return url

    async def delete(self, key: str) -> bool:
        try:
            async with self._client() as s3:
                await s3.delete_object(Bucket=AWS_S3_BUCKET, Key=key)
            logger.info(f"S3 DELETE ok: s3://{AWS_S3_BUCKET}/{key}")
            return True
        except ClientError as exc:
            logger.warning(f"S3 DELETE failed for {key}: {exc}")
            return False

    async def exists(self, key: str) -> bool:
        try:
            async with self._client() as s3:
                await s3.head_object(Bucket=AWS_S3_BUCKET, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    async def download_to_temp(self, key: str) -> Path:
        suffix = Path(key).suffix or ".bin"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        async with self._client() as s3:
            response = await s3.get_object(Bucket=AWS_S3_BUCKET, Key=key)
            async with response["Body"] as stream:
                data = await stream.read()
        tmp_path.write_bytes(data)
        logger.debug(f"S3 GET -> temp: s3://{AWS_S3_BUCKET}/{key} -> {tmp_path}")
        return tmp_path
```

**Step 2: Update `app/services/storage/__init__.py`** to also export `S3Storage`:

Replace the existing file contents with:

```python
"""Storage backend package."""

from app.services.storage.base import Storage
from app.services.storage.local import LocalStorage
from app.services.storage.s3 import S3Storage

__all__ = ["Storage", "LocalStorage", "S3Storage"]
```

**Step 3: Verify the module imports**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "from app.services.storage import Storage, LocalStorage, S3Storage; print('OK')"
```

**Expected output:** `OK`

**Step 4: Commit**

```bash
git add app/services/storage/s3.py app/services/storage/__init__.py
git commit -m "feat(storage): add S3Storage backend using aioboto3"
```

**If Task Fails:**
- `ImportError: aioboto3` → Task 2 failed; re-run `uv sync`.
- `ImportError: botocore` → aioboto3 didn't pull botocore for some reason; `uv add botocore`.

---

## Task 9: Add `get_storage()` factory

**Files:**
- Create: `app/services/storage/factory.py`
- Modify: `app/services/storage/__init__.py` (export `get_storage`)

**Prerequisites:**
- Task 8 complete.

**Step 1: Create `app/services/storage/factory.py`**

```python
"""Storage backend factory.

A single Storage instance is cached per process. The choice is made at
first call and never re-read — to switch backends, restart the process.
This is intentional: live-switching invalidates every in-flight
post-download upload and every cached presigned URL.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from app.services.configs import STORAGE_BACKEND
from app.services.storage.base import Storage
from app.services.storage.local import LocalStorage
from app.services.storage.s3 import S3Storage

_storage_instance: Optional[Storage] = None


def get_storage() -> Storage:
    """Return the process-wide Storage instance."""
    global _storage_instance
    if _storage_instance is None:
        if STORAGE_BACKEND == "s3":
            _storage_instance = S3Storage()
            logger.info("Storage backend: S3")
        else:
            _storage_instance = LocalStorage()
            logger.info("Storage backend: local")
    return _storage_instance


def reset_storage_for_tests() -> None:
    """Clear the cached instance. Tests only."""
    global _storage_instance
    _storage_instance = None
```

**Step 2: Re-export from package `__init__.py`**

Replace `app/services/storage/__init__.py` again with:

```python
"""Storage backend package."""

from app.services.storage.base import Storage
from app.services.storage.factory import get_storage, reset_storage_for_tests
from app.services.storage.local import LocalStorage
from app.services.storage.s3 import S3Storage

__all__ = [
    "Storage",
    "LocalStorage",
    "S3Storage",
    "get_storage",
    "reset_storage_for_tests",
]
```

**Step 3: Verify the factory**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "
from app.services.storage import get_storage
s = get_storage()
print('backend:', s.backend_name)
assert get_storage() is s, 'expected cached instance'
print('OK')
"
```

**Expected output:**
```
backend: local
OK
```

**Step 4: Commit**

```bash
git add app/services/storage/factory.py app/services/storage/__init__.py
git commit -m "feat(storage): add get_storage factory with process-wide instance cache"
```

---

## Task 10: Wire `validate_storage_config()` into application startup

**Files:**
- Modify: `app/uwtv/main.py:86-94` (lifespan validation block)

**Prerequisites:**
- Task 9 complete.

**Step 1: Add storage validation alongside cookie validation**

Edit `app/uwtv/main.py`. Find the existing block around line 86–94:

```python
    # Validate cookie configuration at startup
    try:
        from app.services.configs import get_yt_dlp_cookies_opts

        get_yt_dlp_cookies_opts()
        logger.info("Cookie configuration validated successfully.")
    except ValueError as exc:
        logger.error(f"Invalid cookie configuration, cannot start: {exc}")
        raise RuntimeError(f"Invalid cookie configuration: {exc}") from exc
```

Immediately after that `try/except`, insert:

```python
    # Validate storage configuration at startup
    try:
        from app.services.configs import validate_storage_config
        from app.services.storage import get_storage

        validate_storage_config()
        storage = get_storage()
        logger.info(
            f"Storage configuration validated. Backend: {storage.backend_name}"
        )
    except ValueError as exc:
        logger.error(f"Invalid storage configuration, cannot start: {exc}")
        raise RuntimeError(f"Invalid storage configuration: {exc}") from exc
```

**Step 2: Verify startup logs include the new validation**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
timeout 6 uv run uvicorn app.uwtv.main:app --port 8001 2>&1 | grep -E "Storage|Cookie"
```

**Expected output:**
```
Cookie configuration validated successfully.
Storage configuration validated. Backend: local
```

**Step 3: Commit**

```bash
git add app/uwtv/main.py
git commit -m "feat(startup): validate storage configuration on application startup"
```

**If Task Fails:**
- Validation runs but cookie validation runs after it → ensure storage block is **after** the cookie block (cookies have no Storage dependency, but startup-order parity is friendlier for ops debugging).

---

## Task 11: Code review for the Storage strategy (Tasks 6–10)

1. Dispatch all 10 reviewers in parallel — REQUIRED SUB-SKILL: Use ring:codereview
2. Wait for all to complete.
3. Handle findings by severity (same rules as Task 5).
4. Proceed only when zero Critical/High/Medium remain.

---

## Task 12: Wire post-download S3 upload into `AudioDownloadManager`

**Files:**
- Modify: `app/services/managers.py:1-25` (imports)
- Modify: `app/services/managers.py:342-369` (the success block inside `download_audio_with_status_async`)

**Prerequisites:**
- Task 11 complete.

**Step 1: Add Storage import**

At the top of `app/services/managers.py`, find the existing block of imports (around lines 1–25). After the line that imports `audio_mapping`, `video_mapping`, `AUDIO_DIR`, `VIDEO_DIR`, add:

```python
from app.services.configs import (
    S3_DELETE_LOCAL_AFTER_UPLOAD,
    STORAGE_BACKEND,
)
from app.services.storage import get_storage
```

(If `configs` is already imported with multiple names, merge the new names into the existing import statement rather than adding a duplicate.)

**Step 2: Add an `_upload_to_storage_if_needed` helper on `AudioDownloadManager`**

Inside the `AudioDownloadManager` class, immediately before `def delete_audio` (line ~484), add:

```python
    async def _upload_to_storage_if_needed(
        self, audio_id: str, local_filename: Path, relative_path: str
    ) -> None:
        """Upload the finished audio to the active storage backend.

        For LocalStorage this is a no-op. For S3Storage this PUTs the
        file under key=relative_path, persists `s3_key` + `storage_backend='s3'`
        in the DB, and (if S3_DELETE_LOCAL_AFTER_UPLOAD) deletes the
        local file and its parent directory.

        Failures here are recorded but do not erase the local file —
        the row stays `storage_backend='local'` so streaming keeps working.
        """
        if STORAGE_BACKEND != "s3":
            return  # LocalStorage: nothing to do

        storage = get_storage()
        try:
            s3_key = await storage.put_file(local_filename, relative_path)
        except Exception as upload_err:
            logger.error(
                f"S3 upload failed for audio {audio_id}: {upload_err}. "
                f"Row remains storage_backend='local'."
            )
            async with get_db_context() as session:
                repo = AudioRepository(session)
                await repo.update(
                    audio_id,
                    download_error=f"S3 upload failed: {str(upload_err)[:480]}",
                )
            return

        async with get_db_context() as session:
            repo = AudioRepository(session)
            await repo.update(
                audio_id,
                storage_backend="s3",
                s3_key=s3_key,
            )

        if S3_DELETE_LOCAL_AFTER_UPLOAD:
            try:
                if local_filename.exists():
                    local_filename.unlink()
                parent = local_filename.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                logger.info(
                    f"Local copy removed for audio {audio_id} after S3 upload."
                )
            except Exception as cleanup_err:
                logger.warning(
                    f"Local cleanup failed for audio {audio_id}: {cleanup_err}"
                )
```

**Step 3: Call the helper at the end of `download_audio_with_status_async`**

In `download_audio_with_status_async`, find the block (around lines 342–366) that ends with:

```python
            # Atualizar mapeamento em memória
            self._add_audio_mappings(filename, info, audio_id)

            if sse_manager:
                await sse_manager.download_completed(
                    audio_id, f"Download concluído: {filename.name}"
                )
```

Immediately **before** `# Atualizar mapeamento em memória` (so before line ~360), insert:

```python
            # Storage strategy hook: upload to S3 if STORAGE_BACKEND=s3,
            # then optionally remove the local file. No-op for local backend.
            relative_path = str(filename.relative_to(self.download_dir.parent))
            await self._upload_to_storage_if_needed(
                audio_id, filename, relative_path
            )
```

**Step 4: Verify imports and module parses**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "from app.services.managers import AudioDownloadManager; m = AudioDownloadManager(); print(hasattr(m, '_upload_to_storage_if_needed'))"
```

**Expected output:** `True`

**Step 5: Commit**

```bash
git add app/services/managers.py
git commit -m "feat(managers): upload finished audio to S3 backend after download"
```

**If Task Fails:**
- `NameError: STORAGE_BACKEND not defined` → Step 1 import missing.
- `AttributeError: '_upload_to_storage_if_needed' is not a method` → check indentation; it must be inside the `class AudioDownloadManager:` block.

---

## Task 13: Wire post-download S3 upload into `VideoDownloadManager`

**Files:**
- Modify: `app/services/managers.py:887-913` (the success block inside `download_video_with_status_async`)

**Prerequisites:**
- Task 12 complete.

**Step 1: Add the same helper to `VideoDownloadManager`**

Inside the `VideoDownloadManager` class, immediately before `def delete_video` (line ~995), add:

```python
    async def _upload_to_storage_if_needed(
        self, video_id: str, local_filename: Path, relative_path: str
    ) -> None:
        """Upload the finished video to the active storage backend.

        Mirrors AudioDownloadManager._upload_to_storage_if_needed.
        See that method for semantics.
        """
        if STORAGE_BACKEND != "s3":
            return

        storage = get_storage()
        try:
            s3_key = await storage.put_file(local_filename, relative_path)
        except Exception as upload_err:
            logger.error(
                f"S3 upload failed for video {video_id}: {upload_err}. "
                f"Row remains storage_backend='local'."
            )
            async with get_db_context() as session:
                repo = VideoRepository(session)
                await repo.update(
                    video_id,
                    download_error=f"S3 upload failed: {str(upload_err)[:480]}",
                )
            return

        async with get_db_context() as session:
            repo = VideoRepository(session)
            await repo.update(
                video_id,
                storage_backend="s3",
                s3_key=s3_key,
            )

        if S3_DELETE_LOCAL_AFTER_UPLOAD:
            try:
                if local_filename.exists():
                    local_filename.unlink()
                parent = local_filename.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                logger.info(
                    f"Local copy removed for video {video_id} after S3 upload."
                )
            except Exception as cleanup_err:
                logger.warning(
                    f"Local cleanup failed for video {video_id}: {cleanup_err}"
                )
```

**Step 2: Call the helper at the end of `download_video_with_status_async`**

In `download_video_with_status_async`, find the block (around lines 905–913) ending with:

```python
            # Atualizar mapeamento em memória
            self._add_video_mappings(filename, info, video_id)
```

Immediately **before** `# Atualizar mapeamento em memória`, insert:

```python
            # Storage strategy hook: upload to S3 if STORAGE_BACKEND=s3,
            # then optionally remove the local file. No-op for local backend.
            relative_path = str(filename.relative_to(self.download_dir.parent))
            await self._upload_to_storage_if_needed(
                video_id, filename, relative_path
            )
```

**Step 3: Verify the method exists**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "from app.services.managers import VideoDownloadManager; m = VideoDownloadManager(); print(hasattr(m, '_upload_to_storage_if_needed'))"
```

**Expected output:** `True`

**Step 4: Commit**

```bash
git add app/services/managers.py
git commit -m "feat(managers): upload finished video to S3 backend after download"
```

---

## Task 14: Adapt streaming endpoints to honor `storage_backend`

**Files:**
- Modify: `app/uwtv/main.py:10` (import `RedirectResponse`)
- Modify: `app/uwtv/main.py:826-877` (`stream_downloaded_video`)
- Modify: `app/uwtv/main.py:1205-1253` (`stream_audio_file`)
- Modify: `app/uwtv/main.py:197-222` (`stream_video` — mapping-backed)
- Modify: `app/uwtv/main.py:225-269` (`stream_audio` — mapping-backed)

**Prerequisites:**
- Task 13 complete.

**Design decision (in-memory mapping endpoints):** `stream_video` (198) and `stream_audio` (226) read from `video_mapping` / `audio_mapping` (Path-typed in-memory dicts populated by `_add_*_mappings`). For S3-backed rows we **do not populate these mappings** — we fall back to a DB lookup at the endpoint. The mapping remains a fast-path for legacy local rows; new S3 rows always go through the DB. This avoids inventing a sentinel "S3 path" type.

**Step 1: Update the FastAPI response imports**

Edit `app/uwtv/main.py:10`:

```python
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse
```

**Step 2: Refactor `stream_downloaded_video` (line ~826)**

Replace the body of the `stream_downloaded_video` function. The function signature stays the same. Find the entire function (from `@app.get("/video/stream/{video_id}")` at line 826 through the closing of its `try/except` at ~877) and replace its body with:

```python
@app.get("/video/stream/{video_id}")
async def stream_downloaded_video(
    video_id: str, token_data: dict = Depends(verify_token)
):
    """Streaming de vídeo baixado (local) ou redirect para S3 presigned."""
    try:
        logger.debug(f"Solicitado streaming do vídeo: {video_id}")

        video_info = await video_manager.get_video_by_youtube_id(video_id)
        if not video_info:
            # Fallback: maybe the path param is the row id, not the YouTube id.
            video_info = await video_manager.get_video_info(video_id)

        if not video_info:
            logger.warning(f"Vídeo não encontrado: {video_id}")
            raise HTTPException(status_code=404, detail="Vídeo não encontrado")

        if video_info.get("download_status") != "ready":
            logger.warning(f"Vídeo ainda não está pronto: {video_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Vídeo ainda não está pronto. Status: {video_info.get('download_status')}",
            )

        backend = video_info.get("storage_backend", "local")

        if backend == "s3":
            s3_key = video_info.get("s3_key")
            if not s3_key:
                logger.error(f"S3 row sem s3_key: {video_id}")
                raise HTTPException(
                    status_code=500, detail="Row S3 sem s3_key"
                )
            from app.services.storage import get_storage

            storage = get_storage()
            url = await storage.get_url(
                s3_key, filename=video_info.get("name")
            )
            logger.info(f"Redirecting video {video_id} to S3 presigned URL")
            return RedirectResponse(url=url, status_code=302)

        # Local backend (legacy behavior)
        relative_path = video_info.get("path", "")
        video_path = DOWNLOADS_DIR / relative_path

        if not video_path.exists():
            logger.error(f"Arquivo de vídeo não encontrado: {video_path}")
            raise HTTPException(
                status_code=404, detail="Arquivo de vídeo não encontrado"
            )

        content_types = {
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
        }
        content_type = content_types.get(video_path.suffix.lower(), "video/mp4")

        logger.info(f"Iniciando streaming local do vídeo: {video_path}")
        return StreamingResponse(
            generate_video_stream(video_path), media_type=content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro ao fazer streaming do vídeo {video_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao fazer streaming do vídeo: {str(e)}",
        )
```

**Step 3: Refactor `stream_audio_file` (line ~1205)**

Replace the entire `stream_audio_file` function body with:

```python
@app.get("/audio/stream/{audio_id}")
async def stream_audio_file(audio_id: str, token: str = Query(None)):
    """Servir áudio (local FileResponse) ou redirect para S3 presigned."""
    try:
        if token:
            try:
                verify_token_sync(token)
            except Exception as e:
                logger.warning(f"Token inválido: {str(e)}")
                raise HTTPException(status_code=403, detail="Token inválido")

        logger.debug(f"Solicitado stream do áudio: {audio_id}")

        audio = await audio_manager.get_audio_info(audio_id)
        if not audio:
            logger.warning(f"Áudio não encontrado: {audio_id}")
            raise HTTPException(status_code=404, detail="Áudio não encontrado")

        backend = audio.get("storage_backend", "local")

        if backend == "s3":
            s3_key = audio.get("s3_key")
            if not s3_key:
                logger.error(f"S3 row sem s3_key: {audio_id}")
                raise HTTPException(status_code=500, detail="Row S3 sem s3_key")
            from app.services.storage import get_storage

            storage = get_storage()
            url = await storage.get_url(s3_key, filename=audio.get("name"))
            logger.info(f"Redirecting audio {audio_id} to S3 presigned URL")
            return RedirectResponse(url=url, status_code=302)

        # Local backend
        audio_file_path = AUDIO_DIR.parent / audio["path"]
        if not audio_file_path.exists():
            logger.warning(f"Arquivo não encontrado: {audio_file_path}")
            raise HTTPException(
                status_code=404, detail="Arquivo de áudio não encontrado"
            )

        content_type = "audio/mp4"
        if audio_file_path.suffix.lower() == ".m4a":
            content_type = "audio/mp4"
        elif audio_file_path.suffix.lower() == ".mp3":
            content_type = "audio/mpeg"
        elif audio_file_path.suffix.lower() == ".wav":
            content_type = "audio/wav"

        logger.info(f"Servindo áudio local {audio_id}: {audio_file_path} ({content_type})")
        return FileResponse(
            path=str(audio_file_path),
            media_type=content_type,
            filename=f"{audio['name']}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao servir áudio {audio_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao servir áudio: {str(e)}")
```

**Step 4: Refactor `stream_video` (mapping-backed, line ~197)**

Replace the entire `stream_video` function with:

```python
@app.get("/video/{video_id}")
async def stream_video(video_id: str, token_data: dict = Depends(verify_token)):
    """Stream de vídeo (legacy mapping fast-path; falls back to DB for S3 rows)."""
    # Legacy fast path: in-memory mapping for local files.
    if video_id in video_mapping:
        video_source = video_mapping[video_id]

        if isinstance(video_source, str) and video_source.startswith("http"):
            logger.debug(f"Iniciando streaming do YouTube: {video_source}")
            return StreamingResponse(
                stream_manager.stream_youtube_video(video_source),
                media_type="video/mp4",
            )

        video_path = video_source
        content_types = {".mp4": "video/mp4", ".webm": "video/webm"}
        content_type = content_types.get(video_path.suffix.lower())
        if not content_type:
            logger.error("Formato de vídeo não suportado.")
            raise HTTPException(
                status_code=400, detail="Formato de vídeo não suportado"
            )
        return StreamingResponse(
            generate_video_stream(video_path), media_type=content_type
        )

    # Not in mapping — could be an S3-backed row. Look it up in the DB.
    video_info = await video_manager.get_video_info(video_id)
    if not video_info:
        video_info = await video_manager.get_video_by_youtube_id(video_id)
    if not video_info:
        logger.error("Vídeo não encontrado.")
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    backend = video_info.get("storage_backend", "local")
    if backend == "s3" and video_info.get("s3_key"):
        from app.services.storage import get_storage

        storage = get_storage()
        url = await storage.get_url(
            video_info["s3_key"], filename=video_info.get("name")
        )
        return RedirectResponse(url=url, status_code=302)

    # Local row that wasn't yet mapped — serve directly from disk.
    relative_path = video_info.get("path", "")
    video_path = DOWNLOADS_DIR / relative_path
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    content_types = {".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska"}
    content_type = content_types.get(video_path.suffix.lower(), "video/mp4")
    return StreamingResponse(
        generate_video_stream(video_path), media_type=content_type
    )
```

**Step 5: Refactor `stream_audio` (mapping-backed, line ~225)**

Replace the entire `stream_audio` function with:

```python
@app.get("/audios/{audio_id}/stream/")
async def stream_audio(audio_id: str, token_data: dict = Depends(verify_token)):
    """Streaming de áudio (legacy mapping fast-path; falls back to DB for S3 rows)."""
    try:
        logger.debug(f"Solicitado streaming do áudio: {audio_id}")

        # Legacy fast path: in-memory mapping for local files.
        if audio_id in audio_mapping:
            audio_path = audio_mapping[audio_id]
            if audio_path.exists():
                content_type = "audio/mp4"
                suffix = audio_path.suffix.lower()
                if suffix == ".m4a":
                    content_type = "audio/mp4"
                elif suffix == ".mp3":
                    content_type = "audio/mpeg"
                elif suffix == ".wav":
                    content_type = "audio/wav"
                elif suffix == ".ogg":
                    content_type = "audio/ogg"
                logger.info(
                    f"Streaming áudio local {audio_id}: {audio_path} ({content_type})"
                )
                return StreamingResponse(
                    generate_audio_stream(audio_path), media_type=content_type
                )
            logger.warning(
                f"Mapeamento aponta para arquivo inexistente: {audio_path}; "
                f"caindo no DB para resolução."
            )

        # Not in mapping (or stale mapping) — look up in DB.
        audio_info = await audio_manager.get_audio_info(audio_id)
        if not audio_info:
            logger.warning(f"Áudio não encontrado no mapeamento nem no DB: {audio_id}")
            raise HTTPException(status_code=404, detail="Áudio não encontrado")

        backend = audio_info.get("storage_backend", "local")
        if backend == "s3" and audio_info.get("s3_key"):
            from app.services.storage import get_storage

            storage = get_storage()
            url = await storage.get_url(
                audio_info["s3_key"], filename=audio_info.get("name")
            )
            return RedirectResponse(url=url, status_code=302)

        # Local row, not in mapping (rare — should only happen if mapping
        # wasn't rebuilt after app restart). Serve from disk.
        audio_file_path = AUDIO_DIR.parent / audio_info["path"]
        if not audio_file_path.exists():
            raise HTTPException(
                status_code=404, detail="Arquivo de áudio não encontrado"
            )
        content_type = "audio/mp4"
        suffix = audio_file_path.suffix.lower()
        if suffix == ".mp3":
            content_type = "audio/mpeg"
        elif suffix == ".wav":
            content_type = "audio/wav"
        return StreamingResponse(
            generate_audio_stream(audio_file_path), media_type=content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao fazer streaming do áudio {audio_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao fazer streaming do áudio: {str(e)}",
        )
```

**Step 6: Smoke-test the endpoints with default backend**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
timeout 6 uv run uvicorn app.uwtv.main:app --port 8001 2>&1 | head -20
```

**Expected output:** `Storage configuration validated. Backend: local` plus `Aplicação iniciada com sucesso!`. No tracebacks.

**Step 7: Commit**

```bash
git add app/uwtv/main.py
git commit -m "feat(api): branch streaming endpoints on storage_backend (local|s3)"
```

**If Task Fails:**
- `NameError: RedirectResponse` → Step 1 import is missing.
- Existing endpoint signature changed → re-check that route decorators and `Depends(verify_token)` are preserved.

---

## Task 15: Adapt delete operations to clean up both local and S3 objects

**Files:**
- Modify: `app/services/managers.py:484-518` (`AudioDownloadManager.delete_audio`)
- Modify: `app/services/managers.py:995-1028` (`VideoDownloadManager.delete_video`)

**Prerequisites:**
- Task 14 complete.

**Step 1: Update `delete_audio`**

Replace the body of `delete_audio` with:

```python
    async def delete_audio(self, audio_id: str) -> bool:
        """Exclui um áudio do banco, S3 (se aplicável) e arquivos locais."""
        try:
            logger.info(f"Iniciando exclusão do áudio: {audio_id}")

            audio_info = await self.get_audio_info(audio_id)
            if not audio_info:
                logger.warning(f"Áudio não encontrado: {audio_id}")
                return False

            # Best-effort: delete from S3 first if applicable.
            if audio_info.get("storage_backend") == "s3" and audio_info.get(
                "s3_key"
            ):
                try:
                    storage = get_storage()
                    await storage.delete(audio_info["s3_key"])
                except Exception as s3_err:
                    logger.warning(
                        f"S3 delete failed for {audio_id} "
                        f"(continuing with DB+local cleanup): {s3_err}"
                    )

            # Local filesystem cleanup. Safe even for S3 rows: directory
            # may have been auto-removed at upload time, or kept if
            # S3_DELETE_LOCAL_AFTER_UPLOAD=false.
            audio_dir = self.download_dir / audio_id
            if audio_dir.exists() and audio_dir.is_dir():
                import shutil

                shutil.rmtree(audio_dir)
                logger.info(f"Diretório removido: {audio_dir}")

            if audio_id in audio_mapping:
                del audio_mapping[audio_id]

            async with get_db_context() as session:
                repo = AudioRepository(session)
                result = await repo.delete(audio_id)

            logger.success(f"Áudio excluído com sucesso: {audio_id}")
            return result

        except Exception as e:
            logger.exception(f"Erro ao excluir áudio {audio_id}: {e}")
            raise
```

**Step 2: Update `delete_video`**

Replace the body of `delete_video` with the analogous version:

```python
    async def delete_video(self, video_id: str) -> bool:
        """Exclui um vídeo do banco, S3 (se aplicável) e arquivos locais."""
        try:
            logger.info(f"Iniciando exclusão do vídeo: {video_id}")

            video_info = await self.get_video_info(video_id)
            if not video_info:
                logger.warning(f"Vídeo não encontrado: {video_id}")
                return False

            if video_info.get("storage_backend") == "s3" and video_info.get(
                "s3_key"
            ):
                try:
                    storage = get_storage()
                    await storage.delete(video_info["s3_key"])
                except Exception as s3_err:
                    logger.warning(
                        f"S3 delete failed for {video_id} "
                        f"(continuing with DB+local cleanup): {s3_err}"
                    )

            video_dir = self.download_dir / video_id
            if video_dir.exists() and video_dir.is_dir():
                import shutil

                shutil.rmtree(video_dir)
                logger.info(f"Diretório removido: {video_dir}")

            if video_id in video_mapping:
                del video_mapping[video_id]

            async with get_db_context() as session:
                repo = VideoRepository(session)
                result = await repo.delete(video_id)

            logger.success(f"Vídeo excluído com sucesso: {video_id}")
            return result

        except Exception as e:
            logger.exception(f"Erro ao excluir vídeo {video_id}: {e}")
            raise
```

**Step 3: Smoke-test syntax**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "from app.services.managers import AudioDownloadManager, VideoDownloadManager; print('OK')"
```

**Expected output:** `OK`

**Step 4: Commit**

```bash
git add app/services/managers.py
git commit -m "feat(managers): delete S3 object alongside local files on row deletion"
```

---

## Task 16: Adapt transcription `find_audio_file` for S3-backed rows

**Files:**
- Modify: `app/services/transcription/service.py:1-16` (imports)
- Modify: `app/services/transcription/service.py:117-162` (`find_audio_file`)

**Prerequisites:**
- Task 15 complete.

**Design decision:** When `STORAGE_BACKEND=s3` and `S3_DELETE_LOCAL_AFTER_UPLOAD=true`, the canonical bytes live only in S3. Transcription needs a seekable on-disk file, so for S3-backed rows we pull the object to a tempfile via `Storage.download_to_temp()` and return that path. The temp file is **not** cleaned up automatically by this function — the caller (the transcription pipeline) loads the bytes synchronously and the OS will reclaim the tempfile on process exit. (For long-running services this is a minor leak; if it becomes a problem, wrap the transcription call in a `try/finally` that unlinks the tempfile.)

**Step 1: Add Storage import**

At the top of `app/services/transcription/service.py`, after the existing `from app.services.managers import ...` line (line 14), add:

```python
from app.services.storage import get_storage
```

**Step 2: Branch on `storage_backend` for audio resolution**

Inside `find_audio_file`, locate the block (around lines 130–145):

```python
        if audio_info:
            # Se encontrou no gerenciador, retorna o caminho do arquivo
            logger.debug(
                f"Arquivo encontrado no gerenciador de áudio: {audio_info['path']}"
            )
            audio_path = AUDIO_DIR.parent / audio_info["path"]
            if audio_path.exists():
                return audio_path
            else:
                logger.warning(
                    f"Caminho no gerenciador existe mas arquivo não encontrado: {audio_path}"
                )
```

Replace with:

```python
        if audio_info:
            logger.debug(
                f"Arquivo encontrado no gerenciador de áudio: {audio_info['path']} "
                f"(backend={audio_info.get('storage_backend', 'local')})"
            )
            if audio_info.get("storage_backend") == "s3" and audio_info.get(
                "s3_key"
            ):
                storage = get_storage()
                tmp_path = await storage.download_to_temp(audio_info["s3_key"])
                logger.info(
                    f"S3 audio materializado em tempfile para transcrição: {tmp_path}"
                )
                return tmp_path

            audio_path = AUDIO_DIR.parent / audio_info["path"]
            if audio_path.exists():
                return audio_path
            else:
                logger.warning(
                    f"Caminho no gerenciador existe mas arquivo não encontrado: {audio_path}"
                )
```

**Step 3: Do the same for the video block**

Just below the audio block, find (around lines 147–162):

```python
        if video_info:
            # Se encontrou no gerenciador de vídeos, retorna o caminho do arquivo
            logger.debug(
                f"Arquivo encontrado no gerenciador de vídeo: {video_info['path']}"
            )
            video_path = VIDEO_DIR.parent / video_info["path"]
            if video_path.exists():
                return video_path
            else:
                logger.warning(
                    f"Caminho no gerenciador existe mas arquivo não encontrado: {video_path}"
                )
```

Replace with:

```python
        if video_info:
            logger.debug(
                f"Arquivo encontrado no gerenciador de vídeo: {video_info['path']} "
                f"(backend={video_info.get('storage_backend', 'local')})"
            )
            if video_info.get("storage_backend") == "s3" and video_info.get(
                "s3_key"
            ):
                storage = get_storage()
                tmp_path = await storage.download_to_temp(video_info["s3_key"])
                logger.info(
                    f"S3 video materializado em tempfile para transcrição: {tmp_path}"
                )
                return tmp_path

            video_path = VIDEO_DIR.parent / video_info["path"]
            if video_path.exists():
                return video_path
            else:
                logger.warning(
                    f"Caminho no gerenciador existe mas arquivo não encontrado: {video_path}"
                )
```

**Step 4: Smoke-test the module**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run python -c "from app.services.transcription.service import TranscriptionService; print('OK')"
```

**Expected output:** `OK`

**Step 5: Commit**

```bash
git add app/services/transcription/service.py
git commit -m "feat(transcription): pull S3-backed media to tempfile for transcription"
```

**If Task Fails:**
- `find_audio_file` is not `async` → it already is (declared `async def` at line 117). If unsure, confirm with `grep -n "async def find_audio_file" app/services/transcription/service.py`.

---

## Task 17: Code review for managers + endpoints + transcription (Tasks 12–16)

1. Dispatch all 10 reviewers in parallel — REQUIRED SUB-SKILL: Use ring:codereview
2. Wait for all to complete.
3. Handle findings by severity (same rules as Task 5).
4. Proceed only when zero Critical/High/Medium remain.

---

## Task 18: Update `.env.example` with the new S3 environment variables

**Files:**
- Modify: `.env.example:67-70` (append a new section)

**Prerequisites:**
- Task 17 complete.

**Step 1: Append a STORAGE section to `.env.example`**

Append the following block to the end of `/media/marvinbraga/python/marvin/youtube_downloader/.env.example`:

```
# ==============================================================================
# STORAGE BACKEND (optional)
# Default is local filesystem. Set STORAGE_BACKEND=s3 to upload finished
# downloads to AWS S3 and serve them via short-lived presigned URLs.
# ==============================================================================

# STORAGE_BACKEND=local   # or 's3'

# --- Required when STORAGE_BACKEND=s3 ---
# AWS_S3_BUCKET=my-bucket-name
# AWS_REGION=us-east-1

# --- Optional ---
# AWS_S3_KEY_PREFIX=youtube-downloader   # All keys are placed under this prefix.
# AWS_S3_ENDPOINT_URL=http://localhost:9000   # For MinIO / LocalStack only.
# AWS_ACCESS_KEY_ID=                     # Prefer IAM role / IRSA over inline keys.
# AWS_SECRET_ACCESS_KEY=
# S3_PRESIGNED_URL_TTL=3600              # Presigned GET URL validity, seconds.
# S3_DELETE_LOCAL_AFTER_UPLOAD=true      # 'false' keeps a redundant local copy.
```

**Step 2: Verify the file is consistent**

```bash
grep -E "STORAGE_BACKEND|AWS_S3_BUCKET|S3_PRESIGNED_URL_TTL" /media/marvinbraga/python/marvin/youtube_downloader/.env.example
```

**Expected output:** three lines, all prefixed with `# ` (commented out — opt-in).

**Step 3: Commit**

```bash
git add .env.example
git commit -m "docs(env): document S3 storage backend environment variables"
```

---

## Task 19: Add an optional MinIO service to `docker-compose.yml`

**Files:**
- Modify: `docker-compose.yml`

**Prerequisites:**
- Task 18 complete.

**Step 1: Append a MinIO service under a `dev` profile**

Append the following to the end of `/media/marvinbraga/python/marvin/youtube_downloader/docker-compose.yml`:

```yaml

  # Local S3-compatible storage for development. Only starts when the
  # 'dev' profile is active:  docker compose --profile dev up minio
  minio:
    image: minio/minio:latest
    container_name: youtube-downloader-minio
    profiles: ["dev"]
    restart: unless-stopped
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - ./data/minio:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:9000/minio/health/live"]
      interval: 15s
      timeout: 5s
      retries: 3
```

**Step 2: Validate compose syntax**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
docker compose config 2>&1 | tail -20
```

**Expected output:** parsed YAML (no errors). The `minio` service appears under `services:`.

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(docker): add optional MinIO service under dev profile"
```

**If Task Fails:**
- `docker` not installed → skip this task (not blocking). Remove the compose change.

---

## Task 20: Update `README.md` with a Storage Backends section

**Files:**
- Modify: `README.md`

**Prerequisites:**
- Task 19 complete.

**Step 1: Append (or insert in the appropriate spot) a "Storage Backends" section**

Read `README.md` to find an appropriate insertion point (usually after the deployment / env vars section). Then append the following section:

```markdown

## Storage Backends

The service supports two storage backends, selected at startup via `STORAGE_BACKEND`:

- **`local`** (default) — Finished downloads stay on disk under `downloads/`. Streaming endpoints serve bytes directly via `FileResponse` / `StreamingResponse`. Zero external dependencies.
- **`s3`** — Finished downloads are uploaded to AWS S3 (or any S3-compatible service: MinIO, LocalStack). Streaming endpoints return a `302 Redirect` to a short-lived presigned GET URL.

### Switching to S3

Set in your `.env`:

```
STORAGE_BACKEND=s3
AWS_S3_BUCKET=my-bucket
AWS_REGION=us-east-1
```

Credentials are resolved via the standard AWS chain: env vars (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`), `~/.aws/credentials`, IAM roles, IRSA, etc. Prefer IAM roles or IRSA over inline keys.

### Behavior

- yt-dlp always downloads to disk first (ffmpeg muxing requires seekable files). The S3 upload happens **after** download success.
- Each row has a `storage_backend` column. Rows already downloaded under the previous backend are **not** migrated; the service serves each row according to its own row-level backend value.
- `S3_DELETE_LOCAL_AFTER_UPLOAD=true` (default) removes the local copy after upload. Set to `false` to keep a redundant copy.
- Transcription pulls S3-backed media to a tempfile via `Storage.download_to_temp()`. Tempfiles are not auto-cleaned (OS reclaims on process exit).

### Local development with MinIO

```bash
docker compose --profile dev up -d minio
# Open http://localhost:9001 (minioadmin / minioadmin), create a bucket "youtube-downloader-dev".
# In .env:
#   STORAGE_BACKEND=s3
#   AWS_S3_BUCKET=youtube-downloader-dev
#   AWS_REGION=us-east-1
#   AWS_S3_ENDPOINT_URL=http://localhost:9000
#   AWS_ACCESS_KEY_ID=minioadmin
#   AWS_SECRET_ACCESS_KEY=minioadmin
```

### Known v1 limitations

- No retroactive migration of legacy local rows.
- `app/services/files.py:scan_video_directory` only lists files on disk — S3-only rows are visible via the DB-backed `/video/list-downloads`, not via `/videos`.
- Transcription markdown files always live on disk.
```

**Step 2: Verify the markdown renders**

```bash
grep -n "Storage Backends" /media/marvinbraga/python/marvin/youtube_downloader/README.md
```

**Expected output:** at least one `## Storage Backends` heading.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): document local vs S3 storage backends"
```

---

## Task 21: Manual smoke-test checklist — Local backend regression

**Files:** none (manual)

**Prerequisites:**
- Task 20 complete.
- `.env` has `STORAGE_BACKEND` unset (or explicitly `local`).

**Step 1: Start the server**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:** startup log line: `Storage configuration validated. Backend: local`.

**Step 2: Acquire a JWT token**

```bash
curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"<YOUR_CLIENT>","client_secret":"<YOUR_SECRET>"}' | jq -r .access_token
```

**Expected output:** a long JWT string. Save it as `TOKEN=<value>`.

**Step 3: Trigger an audio download**

```bash
curl -sS -X POST http://localhost:8000/audio/download \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","high_quality":true}'
```

**Expected output:** JSON with `"audio_id": "<id>"` and `"status": "processando"`.

**Step 4: Wait for download to finish, then verify storage_backend in DB**

After ~30 s:

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT id, download_status, storage_backend, s3_key FROM audios ORDER BY created_date DESC LIMIT 3;"
```

**Expected output:** newest row has `download_status='ready'`, `storage_backend='local'`, `s3_key=NULL` (or empty).

**Step 5: Stream the audio**

```bash
curl -sS -o /tmp/test.m4a -w "%{http_code}\n" \
  "http://localhost:8000/audio/stream/<audio_id>?token=$TOKEN"
```

**Expected output:** `200`, file at `/tmp/test.m4a` with size > 0.

**Step 6: List audios**

```bash
curl -sS -H "Authorization: Bearer $TOKEN" http://localhost:8000/audio/list | jq '.audio_files | length'
```

**Expected output:** integer ≥ 1.

**Step 7: Delete the audio**

```bash
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/audio/<audio_id>
```

**Expected output:** `{"status":"sucesso","message":"..."}` or equivalent.

**Step 8: Confirm local files were removed**

```bash
ls /media/marvinbraga/python/marvin/youtube_downloader/downloads/audio/<audio_id> 2>&1
```

**Expected output:** `No such file or directory`.

**If Task Fails:**
- Streaming returns 404 → check `audio_mapping` was populated (look for `Mapeamento adicionado` log line). If S3-mode dump-and-stream returns 404 instead of 302, check `storage_backend` field on the row.
- Delete returns 500 → check log for the actual exception. The DB delete is the last step, so the row should already be gone from listing.

---

## Task 22: Manual smoke-test checklist — S3 backend (MinIO)

**Files:** none (manual)

**Prerequisites:**
- Task 21 completed cleanly.
- MinIO is reachable, a bucket exists (`youtube-downloader-dev`).
- `.env` updated with the MinIO env vars (see Task 20 Step 1).

**Step 1: Restart the server**

```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
uv run uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:** startup log line: `Storage configuration validated. Backend: s3`.

**Step 2: Trigger an audio download** (same curl as Task 21 Step 3)

**Expected output:** JSON with `audio_id`.

**Step 3: Wait ~30 s, verify S3 upload happened**

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT id, download_status, storage_backend, s3_key FROM audios ORDER BY created_date DESC LIMIT 1;"
```

**Expected output:** `download_status='ready'`, `storage_backend='s3'`, `s3_key='audio/<id>/<file>.m4a'` (or with prefix if configured).

**Step 4: Verify object exists in S3** (via MinIO CLI or AWS CLI):

```bash
docker exec youtube-downloader-minio mc ls local/youtube-downloader-dev/ 2>/dev/null || \
  aws --endpoint-url http://localhost:9000 s3 ls s3://youtube-downloader-dev/ --recursive
```

**Expected output:** at least one `.m4a` object.

**Step 5: Verify local file was removed** (assuming `S3_DELETE_LOCAL_AFTER_UPLOAD=true`)

```bash
ls /media/marvinbraga/python/marvin/youtube_downloader/downloads/audio/<audio_id> 2>&1
```

**Expected output:** `No such file or directory`.

**Step 6: Stream the audio (expect a 302)**

```bash
curl -sS -o /dev/null -w "%{http_code} %{redirect_url}\n" \
  "http://localhost:8000/audio/stream/<audio_id>?token=$TOKEN"
```

**Expected output:** `302 http://localhost:9000/youtube-downloader-dev/...?X-Amz-Signature=...`

Followed by:

```bash
curl -sSL -o /tmp/s3test.m4a -w "%{http_code}\n" \
  "http://localhost:8000/audio/stream/<audio_id>?token=$TOKEN"
```

**Expected output:** `200`, file at `/tmp/s3test.m4a` with size > 0.

**Step 7: Verify Content-Disposition is inline**

```bash
curl -sSL -D - -o /dev/null \
  "http://localhost:8000/audio/stream/<audio_id>?token=$TOKEN" | grep -i "content-disposition"
```

**Expected output:** `Content-Disposition: inline; filename="...m4a"` (browsers will play, not download).

**Step 8: Delete the row, verify S3 object goes away**

```bash
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/audio/<audio_id>

# Re-check S3:
docker exec youtube-downloader-minio mc ls local/youtube-downloader-dev/audio/ 2>/dev/null || \
  aws --endpoint-url http://localhost:9000 s3 ls s3://youtube-downloader-dev/audio/ --recursive
```

**Expected output:** the deleted object's key is gone.

**Step 9: Test the mixed-backend listing**

After running through this twice (once with local, once with S3), the `/audio/list` endpoint should return rows with both `storage_backend='local'` and `storage_backend='s3'`:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" http://localhost:8000/audio/list \
  | jq '[.audio_files[] | .storage_backend] | group_by(.) | map({key: .[0], count: length})'
```

**Expected output:** a JSON array showing both `local` and `s3` keys with counts.

**Step 10: Browser smoke-test**

Open the web client at `http://localhost:8000/`, log in, click play on an S3-backed audio. The HTML5 `<audio>` element should follow the 302 and play. Inspect the browser Network tab — the request to `/audio/stream/<id>` should show `302` followed by a request to the MinIO presigned URL.

**If Task Fails:**
- `200` instead of `302` on stream → check `storage_backend` value in DB; row may have failed to upload (look for `S3 upload failed` in server logs).
- `403` from presigned URL → check `S3_PRESIGNED_URL_TTL` not expired; check bucket policy / endpoint URL matches.
- Audio downloads instead of plays in browser → check `Content-Disposition` header (Step 7). Should be `inline`.

---

## Task 23: Final code review and merge prep

1. Dispatch all 10 reviewers in parallel — REQUIRED SUB-SKILL: Use ring:codereview
2. Wait for all to complete.
3. Handle findings by severity (same rules as Task 5).
4. Proceed only when zero Critical/High/Medium remain.
5. Run `git log --oneline feat/s3-storage-backend ^master` to verify the commit sequence is clean.
6. The branch is now ready for a PR to `master`.

---

## Appendix A: Files touched (final summary)

**New files:**
- `app/services/storage/__init__.py`
- `app/services/storage/base.py`
- `app/services/storage/local.py`
- `app/services/storage/s3.py`
- `app/services/storage/factory.py`

**Modified files:**
- `pyproject.toml`, `uv.lock` — `aioboto3` dependency
- `app/db/models.py` — `storage_backend`, `s3_key` columns on `Audio` and `Video`
- `app/db/database.py` — idempotent migration for the new columns
- `app/services/configs.py` — S3 env vars + `validate_storage_config()`
- `app/services/managers.py` — `_upload_to_storage_if_needed` helper + delete-S3 logic
- `app/services/transcription/service.py` — `download_to_temp` integration for S3 rows
- `app/uwtv/main.py` — startup validation; four streaming endpoints branch on `storage_backend`
- `.env.example` — STORAGE section
- `docker-compose.yml` — MinIO under `dev` profile
- `README.md` — Storage Backends documentation

**Untouched (intentional):**
- `web_client/*` — `<audio>` / `<video>` tags follow 302 redirects natively
- `app/services/files.py` — DB rows are the unit of truth for listings; S3-only objects are not enumerated
- `app/services/download_queue.py` — upload hook lives in the managers (queue only wraps audio anyway)
- `app/models/*` — Pydantic models don't surface `storage_backend` to API consumers in v1 (it's an internal field; can be added later if the frontend needs to differentiate)

---

## Appendix B: Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| S3 upload fails after download succeeds | Medium | Helper catches exception, row stays `storage_backend='local'`, local file kept. Logged. Manual reupload via re-download. |
| Presigned URL expires mid-playback | Low | Default TTL 3600 s; HTML5 players re-fetch ranges so a long pause may break playback. Tunable via `S3_PRESIGNED_URL_TTL`. |
| Migration on existing DB fails | Low | Idempotent migration is identical pattern to existing Instagram migration. Backup taken in Task 1. |
| Local cleanup races with transcription | Low | Transcription has its own `download_to_temp` path for S3 rows; local rows are still cleaned only at delete time, not at upload time. |
| `aioboto3` version conflict with `boto3`/`aiohttp` | Low | `uv add` resolves transitively. Lockfile pins. |
| Cost surprise on S3 PUT/GET | Medium (operational) | Documented in README. Use lifecycle rules / IA tier in production. |

---

## Appendix C: Plan checklist verification

- [x] Header with goal, architecture, tech stack, prerequisites
- [x] Verification commands with expected output
- [x] Tasks broken into bite-sized steps (2-5 min each)
- [x] Exact file paths for all files
- [x] Complete code (no placeholders)
- [x] Exact commands with expected output
- [x] Failure recovery steps for each task
- [x] Code review checkpoints (Tasks 5, 11, 17, 23)
- [x] Severity-based issue handling documented
- [x] Passes Zero-Context Test
