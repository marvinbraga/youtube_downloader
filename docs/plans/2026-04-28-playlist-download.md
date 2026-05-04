# Playlist Download Support Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use ring:executing-plans to implement this plan task-by-task.

**Goal:** Add `POST /audio/playlist` and `POST /video/playlist` endpoints that extract all items from a YouTube playlist, create a Folder record named after the playlist, and queue or launch each item individually, returning a summary response.

**Architecture:** Two new manager methods (`extract_playlist_info` on `AudioDownloadManager` and `VideoDownloadManager`) do flat info extraction without `noplaylist`. The audio endpoint re-uses the existing `register_audio_for_download` + `download_queue.add_download` flow per item. The video endpoint spawns a single orchestration `BackgroundTask` that processes items serially (one coroutine per video) rather than 50 concurrent tasks.

**Tech Stack:** Python 3.8+, FastAPI, yt-dlp, SQLAlchemy async (SQLite), Pydantic v2, loguru

**Implementation Agent:** `ring-dev-team:ring:backend-engineer-django` for all Tasks 1-5 and 7-8. `ring:requesting-code-review` for Task 6.

**Global Prerequisites:**
- Environment: Linux, Python 3.8+ with `uv` package manager
- Tools: `uv`, `uvicorn`, `sqlite3`, `curl`
- Runtime: JS runtime (`deno` or `node`) in PATH or at `~/.deno/bin/deno` / `~/.nvm/versions/node/v20.19.6/bin/node`
- Working directory for all commands: `/media/marvinbraga/python/marvin/youtube_downloader`
- Cookie env variable: either `YT_COOKIES_FROM_BROWSER=chrome` (or other browser) or `YT_COOKIES_FILE=/path/to/cookies.txt`

**Verification before starting:**
```bash
cd /media/marvinbraga/python/marvin/youtube_downloader
python --version
# Expected: Python 3.8+ (e.g., Python 3.11.x)

uv --version
# Expected: uv 0.x.x

python -c "from app.uwtv.main import app; print('OK')"
# Expected: OK

sqlite3 data/youtube_downloader.db "SELECT name FROM sqlite_master WHERE type='table';"
# Expected: folders  audios  videos  (one per line)

# Verify cookie env var is set (required for yt-dlp playlist extraction):
echo "YT_COOKIES_FROM_BROWSER=${YT_COOKIES_FROM_BROWSER:-<NOT SET>}"
echo "YT_COOKIES_FILE=${YT_COOKIES_FILE:-<NOT SET>}"
# Expected: At least one must show a non-empty value.
# If both are NOT SET, set one before proceeding:
#   export YT_COOKIES_FROM_BROWSER=chrome   # or: brave, firefox, edge, opera, safari, vivaldi
#   export YT_COOKIES_FILE=/path/to/cookies.txt
```

---

## Design Decisions (documented here to prevent mid-implementation surprises)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| yt-dlp flat entry URL format | Construct `https://www.youtube.com/watch?v={id}` from `entry["id"]` | `extract_flat=True` returns bare IDs in `url` field, not full URLs |
| Redundant `extract_info` on each item | Accept redundancy; pass `pre_fetched_title` optional param | Simple; playlist already gave us titles; saves 1 network call per item |
| Skip-existing detection | Check existence BEFORE calling `register_*`; return tuple semantics avoided | Keeps `register_*` unchanged; we call `get_audio/video_by_youtube_id` ourselves |
| Folder placement of skipped items | Always assign `folder_id` even for existing items | Associates historical downloads with new playlist folder |
| Video playlist concurrency | Single orchestration `BackgroundTask` processes videos serially | Avoids thrashing 50+ executor threads simultaneously |
| Duplicate folder names | Always create a new Folder per request | Simplest; playlists can be re-downloaded intentionally |
| Non-playlist URL validation | Return HTTP 400 if yt-dlp returns no `entries` | Prevents silent single-item "playlists" |
| Pydantic URL type | Use `HttpUrl` consistent with existing `AudioDownloadRequest` | Codebase consistency |
| `PlaylistTaskItem.item_id` | Single `item_id` field (audio_id or video_id) + `item_type` field | Avoids two near-identical response models |

---

## Task 1: Create Playlist Pydantic Models

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/models/audio.py` (append after line 62)

**Prerequisites:**
- `app/models/audio.py` must exist (verify: `ls app/models/audio.py`)

**Step 1: Read current end of file to confirm append location**

Run: `python -c "import app.models.audio; print('imports OK')"`

Expected output:
```
imports OK
```

**Step 2: Append playlist models to `app/models/audio.py`**

Open `/media/marvinbraga/python/marvin/youtube_downloader/app/models/audio.py` and append the following block at the end (after line 62, after `TranscriptionResponse`):

```python


class PlaylistDownloadRequest(BaseModel):
    """Request para download de playlist completa (áudio ou vídeo)"""

    url: HttpUrl
    high_quality: bool = False  # audio only
    resolution: str = "1080p"   # video only; valid values: 360p 480p 720p 1080p 1440p 2160p best
    skip_existing: bool = True  # skip items that already exist in DB


class PlaylistTaskItem(BaseModel):
    """Representa um item enfileirado/iniciado durante o download de uma playlist"""

    item_id: str          # audio_id or video_id (youtube_id)
    item_type: str        # "audio" or "video"
    task_id: Optional[str] = None  # populated for audio (queue); None for video (background)
    title: str
    url: str
    skipped: bool = False  # True if item already existed and skip_existing=True


class PlaylistDownloadResponse(BaseModel):
    """Resposta do endpoint de playlist"""

    playlist_title: str
    playlist_url: str
    folder_id: str
    total_items: int
    queued_items: int
    skipped_items: int
    tasks: List[PlaylistTaskItem]
```

**Step 3: Verify import works**

Run: `python -c "from app.models.audio import PlaylistDownloadRequest, PlaylistTaskItem, PlaylistDownloadResponse; print('OK')"`

Expected output:
```
OK
```

**Step 4: Commit**

```bash
git add app/models/audio.py
git commit -m "feat: add PlaylistDownloadRequest, PlaylistTaskItem, PlaylistDownloadResponse models"
```

Expected output (last line):
```
 1 file changed, 30 insertions(+)
```

**If Task Fails:**

1. **Import error — `Optional` or `List` not in scope:** The existing file already has `from typing import Optional, List` at line 4. If you see `NameError`, confirm the existing imports are present.
2. **`HttpUrl` missing:** Already imported at line 5 (`from pydantic import BaseModel, HttpUrl`). No change needed.
3. **Rollback:** `git checkout -- app/models/audio.py`

---

## Task 2: Add `extract_playlist_info` to `AudioDownloadManager`

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`
- Insert after line 520 (before `class VideoDownloadManager:`)

**Prerequisites:**
- Task 1 complete
- `app/services/managers.py` must exist

**Step 1: Verify current end of `AudioDownloadManager`**

Run: `python -c "from app.services.managers import AudioDownloadManager; print('import OK')"`

Expected output:
```
import OK
```

**Step 2: Add `extract_playlist_info` method**

In `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`, locate the line (line 517-521):

```python
    # Mantém compatibilidade com código legado
    def migrate_has_transcription_to_status(self) -> None:
        """Migração não necessária com SQLite - mantida para compatibilidade"""
        logger.info("Migração de has_transcription não necessária com SQLite")
```

Insert the following new method BEFORE that block (i.e., after `delete_audio` ends, before the legacy compat method). The insertion point is between the `raise` on the except clause of `delete_audio` (approximately line 514) and the comment on line 517.

Add after `delete_audio`'s closing `raise` and before `# Mantém compatibilidade`:

```python
    async def extract_playlist_info(self, url: str) -> dict:
        """Extrai informações de uma playlist do YouTube sem baixar.

        Returns a dict with shape:
            {
                "title": str,           # playlist title
                "webpage_url": str,     # canonical playlist URL
                "entries": [            # list of video entries
                    {"id": str, "title": str, "url": str},  # url is full watch URL
                    ...
                ]
            }

        Raises ValueError if the URL yields no entries (e.g. single video URL).
        Runs yt-dlp in executor to avoid blocking the event loop.
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,  # Do NOT add noplaylist here — we want the full playlist
            "js_runtimes": YDL_JS_RUNTIMES,
            "remote_components": YDL_REMOTE_COMPONENTS,
            **get_yt_dlp_cookies_opts(),
        }

        def _extract():
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(str(url), download=False)

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _extract)

        entries_raw = info.get("entries") or []
        if not entries_raw:
            raise ValueError(
                f"URL does not appear to be a playlist or returned no entries: {url}"
            )

        # yt-dlp extract_flat returns bare IDs in the 'url' field for YouTube.
        # Build canonical watch URLs from each entry's 'id'.
        entries = []
        for entry in entries_raw:
            video_id = entry.get("id", "")
            title = entry.get("title") or entry.get("webpage_title") or f"Video_{video_id}"
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            entries.append({"id": video_id, "title": title, "url": watch_url})

        return {
            "title": info.get("title") or info.get("webpage_title") or "Playlist",
            "webpage_url": info.get("webpage_url") or str(url),
            "entries": entries,
        }

```

**Step 3: Verify import and method signature**

Run: `python -c "from app.services.managers import AudioDownloadManager; import inspect; m = AudioDownloadManager(); print(inspect.iscoroutinefunction(m.extract_playlist_info))"`

Expected output:
```
True
```

**Step 4: Commit**

```bash
git add app/services/managers.py
git commit -m "feat: add extract_playlist_info to AudioDownloadManager"
```

Expected output (last line):
```
 1 file changed, 47 insertions(+)
```

**If Task Fails:**

1. **`asyncio` not imported:** It is already imported at line 1 of `managers.py`. No change needed.
2. **IndentationError:** Method must be indented 4 spaces (class body level), matching all other methods.
3. **Rollback:** `git checkout -- app/services/managers.py`

---

## Task 3: Add `extract_playlist_info` to `VideoDownloadManager`

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`
- Insert inside `VideoDownloadManager` class, after `update_transcription_status` (approximately after line 963)

**Prerequisites:**
- Task 2 complete

**Step 1: Verify `VideoDownloadManager` imports cleanly**

Run: `python -c "from app.services.managers import VideoDownloadManager; print('OK')"`

Expected output:
```
OK
```

**Step 2: Add `extract_playlist_info` method to `VideoDownloadManager`**

In `/media/marvinbraga/python/marvin/youtube_downloader/app/services/managers.py`, locate the end of the `VideoDownloadManager.update_transcription_status` method (the last method in the class, ending approximately at line 963 with `logger.warning(f"Vídeo não encontrado: {video_id}")`).

Append the following method inside `VideoDownloadManager` after `update_transcription_status`:

```python
    async def extract_playlist_info(self, url: str) -> dict:
        """Extrai informações de uma playlist do YouTube sem baixar.

        Identical semantics to AudioDownloadManager.extract_playlist_info.
        Returns:
            {
                "title": str,
                "webpage_url": str,
                "entries": [{"id": str, "title": str, "url": str}, ...]
            }

        Raises ValueError if the URL yields no entries.
        Runs yt-dlp in executor to avoid blocking the event loop.
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,  # No noplaylist — we want the full playlist
            "js_runtimes": YDL_JS_RUNTIMES,
            "remote_components": YDL_REMOTE_COMPONENTS,
            **get_yt_dlp_cookies_opts(),
        }

        def _extract():
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(str(url), download=False)

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _extract)

        entries_raw = info.get("entries") or []
        if not entries_raw:
            raise ValueError(
                f"URL does not appear to be a playlist or returned no entries: {url}"
            )

        entries = []
        for entry in entries_raw:
            video_id = entry.get("id", "")
            title = entry.get("title") or entry.get("webpage_title") or f"Video_{video_id}"
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            entries.append({"id": video_id, "title": title, "url": watch_url})

        return {
            "title": info.get("title") or info.get("webpage_title") or "Playlist",
            "webpage_url": info.get("webpage_url") or str(url),
            "entries": entries,
        }
```

**Step 3: Verify both managers have the method**

Run: `python -c "from app.services.managers import AudioDownloadManager, VideoDownloadManager; import inspect; print(inspect.iscoroutinefunction(AudioDownloadManager().extract_playlist_info), inspect.iscoroutinefunction(VideoDownloadManager().extract_playlist_info))"`

Expected output:
```
True True
```

**Step 4: Commit**

```bash
git add app/services/managers.py
git commit -m "feat: add extract_playlist_info to VideoDownloadManager"
```

Expected output (last line):
```
 1 file changed, 44 insertions(+)
```

**If Task Fails:**

1. **Method not found:** Ensure indentation is exactly 4 spaces, matching other methods in `VideoDownloadManager`.
2. **Rollback:** `git checkout -- app/services/managers.py`

---

## Task 4: Add `POST /audio/playlist` Endpoint

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/uwtv/main.py`

**Prerequisites:**
- Tasks 1, 2, 3 complete
- `python -c "from app.uwtv.main import app"` returns no errors

**Step 1: Update import in `main.py` to include new models**

In `/media/marvinbraga/python/marvin/youtube_downloader/app/uwtv/main.py`, locate the existing `from app.models.audio import (` block (lines 22-28):

```python
from app.models.audio import (
    AudioDownloadRequest,
    VideoDownloadRequest,
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionProvider,
)
```

Replace it with:

```python
from app.models.audio import (
    AudioDownloadRequest,
    VideoDownloadRequest,
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionProvider,
    PlaylistDownloadRequest,
    PlaylistTaskItem,
    PlaylistDownloadResponse,
)
```

**Step 2: Verify import**

Run: `python -c "from app.uwtv.main import app; print('import OK')"`

Expected output:
```
import OK
```

**Step 3: Add the `POST /audio/playlist` endpoint**

In `/media/marvinbraga/python/marvin/youtube_downloader/app/uwtv/main.py`, locate the line containing:

```python
@app.post("/video/download")
async def download_video(
```

Insert the following complete endpoint BEFORE that line (i.e., between `download_audio` and `download_video`):

```python

@app.post("/audio/playlist", response_model=PlaylistDownloadResponse)
async def download_audio_playlist(
    request: PlaylistDownloadRequest,
    token_data: dict = Depends(verify_token),
):
    """Download all audio tracks from a YouTube playlist.

    Creates a Folder named after the playlist, then queues each item
    individually via the existing download queue.

    Returns a PlaylistDownloadResponse with per-item task IDs.
    Responds with 400 if the URL is not a playlist or yields no entries.
    """
    try:
        logger.info(f"Audio playlist download requested: {request.url}")

        # Step 1 — Extract playlist metadata (runs in executor, non-blocking)
        try:
            playlist_info = await audio_manager.extract_playlist_info(str(request.url))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        entries = playlist_info["entries"]
        playlist_title = playlist_info["title"]
        playlist_url = playlist_info["webpage_url"]

        logger.info(
            f"Playlist '{playlist_title}' found with {len(entries)} entries"
        )

        # Step 2 — Create a Folder for this playlist
        # Truncate to 255 chars: Folder.name is String(255) in the DB model
        async with get_db_context() as session:
            folder_repo = FolderRepository(session)
            folder = Folder(
                name=playlist_title[:255],
                description=f"Playlist: {playlist_url}",
                icon="playlist",
            )
            created_folder = await folder_repo.create(folder)
            folder_id = created_folder.id

        logger.info(f"Folder created: {folder_id} ('{playlist_title}')")

        # Step 3 — Register and queue each entry
        tasks: List[PlaylistTaskItem] = []
        queued_count = 0
        skipped_count = 0

        for entry in entries:
            video_id = entry["id"]
            title = entry["title"]
            watch_url = entry["url"]

            # Check existence before registering (to track skipped vs queued)
            existing = await audio_manager.get_audio_by_youtube_id(video_id)
            already_exists = (
                existing is not None
                and existing.get("download_status") not in ("error", "")
            )

            if already_exists and request.skip_existing:
                # Always associate existing item with this playlist folder
                async with get_db_context() as session:
                    repo = AudioRepository(session)
                    await repo.update_folder(video_id, folder_id)

                tasks.append(
                    PlaylistTaskItem(
                        item_id=video_id,
                        item_type="audio",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=True,
                    )
                )
                skipped_count += 1
                logger.debug(f"Skipped existing audio: {video_id}")
                continue

            # Register (or reset if previously errored)
            try:
                audio_id = await audio_manager.register_audio_for_download(watch_url)
            except Exception as reg_err:
                logger.error(f"Failed to register {video_id}: {reg_err}")
                # Add as errored item but continue with rest of playlist
                tasks.append(
                    PlaylistTaskItem(
                        item_id=video_id,
                        item_type="audio",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=False,
                    )
                )
                continue

            # Move into playlist folder
            async with get_db_context() as session:
                repo = AudioRepository(session)
                await repo.update_folder(audio_id, folder_id)

            # Enqueue download
            task_id = await download_queue.add_download(
                audio_id=audio_id,
                url=watch_url,
                high_quality=request.high_quality,
                priority=0,
            )

            tasks.append(
                PlaylistTaskItem(
                    item_id=audio_id,
                    item_type="audio",
                    task_id=task_id,
                    title=title,
                    url=watch_url,
                    skipped=False,
                )
            )
            queued_count += 1

        logger.info(
            f"Playlist '{playlist_title}': {queued_count} queued, "
            f"{skipped_count} skipped, folder={folder_id}"
        )

        return PlaylistDownloadResponse(
            playlist_title=playlist_title,
            playlist_url=playlist_url,
            folder_id=folder_id,
            total_items=len(entries),
            queued_items=queued_count,
            skipped_items=skipped_count,
            tasks=tasks,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error processing audio playlist: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio playlist: {exc}",
        )

```

**Step 4: Verify application imports without errors**

Run: `python -c "from app.uwtv.main import app; print('app imported OK')"`

Expected output:
```
app imported OK
```

**Step 5: Commit**

```bash
git add app/uwtv/main.py
git commit -m "feat: add POST /audio/playlist endpoint"
```

Expected output (last line):
```
 1 file changed, 97 insertions(+)
```

**If Task Fails:**

1. **`NameError: name 'List' is not defined`:** Ensure `List` is imported from `typing` at the top of `main.py`. The existing import block (line 8) should already include it: `from typing import Optional, List`.
2. **`PlaylistDownloadResponse` not importable:** Ensure Task 1 is complete and the import block was updated in Step 1.
3. **Rollback:** `git checkout -- app/uwtv/main.py`

---

## Task 5: Add `POST /video/playlist` Endpoint

**Files:**
- Modify: `/media/marvinbraga/python/marvin/youtube_downloader/app/uwtv/main.py`

**Prerequisites:**
- Task 4 complete
- `python -c "from app.uwtv.main import app"` returns no errors

**Step 1: Add the `POST /video/playlist` endpoint**

In `/media/marvinbraga/python/marvin/youtube_downloader/app/uwtv/main.py`, locate the line containing:

```python
@app.get("/video/download-status/{video_id}")
```

Insert the following complete endpoint BEFORE that line (i.e., between `download_video` and `get_video_download_status`):

```python

@app.post("/video/playlist", response_model=PlaylistDownloadResponse)
async def download_video_playlist(
    request: PlaylistDownloadRequest,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(verify_token),
):
    """Download all videos from a YouTube playlist.

    Creates a Folder named after the playlist, registers each video in the DB,
    then starts a single orchestration background task that processes each
    video serially to avoid thrashing the executor with many concurrent downloads.

    Returns a PlaylistDownloadResponse immediately; actual downloads happen
    in the background.
    Responds with 400 if the URL is not a playlist or yields no entries.
    """
    try:
        logger.info(f"Video playlist download requested: {request.url}")

        # Step 1 — Extract playlist metadata (runs in executor, non-blocking)
        try:
            playlist_info = await video_manager.extract_playlist_info(str(request.url))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        entries = playlist_info["entries"]
        playlist_title = playlist_info["title"]
        playlist_url = playlist_info["webpage_url"]

        logger.info(
            f"Video playlist '{playlist_title}' found with {len(entries)} entries"
        )

        # Step 2 — Create a Folder for this playlist
        # Truncate to 255 chars: Folder.name is String(255) in the DB model
        async with get_db_context() as session:
            folder_repo = FolderRepository(session)
            folder = Folder(
                name=playlist_title[:255],
                description=f"Playlist: {playlist_url}",
                icon="playlist",
            )
            created_folder = await folder_repo.create(folder)
            folder_id = created_folder.id

        logger.info(f"Video playlist folder created: {folder_id} ('{playlist_title}')")

        # Step 3 — Register each entry synchronously (fast — just DB inserts)
        tasks: List[PlaylistTaskItem] = []
        to_download: list = []  # entries that need actual download
        skipped_count = 0

        for entry in entries:
            video_id = entry["id"]
            title = entry["title"]
            watch_url = entry["url"]

            existing = await video_manager.get_video_by_youtube_id(video_id)
            already_exists = (
                existing is not None
                and existing.get("download_status") not in ("error", "")
            )

            if already_exists and request.skip_existing:
                # Associate existing video with this playlist folder
                async with get_db_context() as session:
                    repo = VideoRepository(session)
                    await repo.update_folder(video_id, folder_id)

                tasks.append(
                    PlaylistTaskItem(
                        item_id=video_id,
                        item_type="video",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=True,
                    )
                )
                skipped_count += 1
                logger.debug(f"Skipped existing video: {video_id}")
                continue

            # Register in DB immediately (status = "downloading")
            try:
                registered_id = await video_manager.register_video_for_download(
                    watch_url, resolution=request.resolution
                )
            except Exception as reg_err:
                logger.error(f"Failed to register video {video_id}: {reg_err}")
                tasks.append(
                    PlaylistTaskItem(
                        item_id=video_id,
                        item_type="video",
                        task_id=None,
                        title=title,
                        url=watch_url,
                        skipped=False,
                    )
                )
                continue

            # Move into playlist folder
            async with get_db_context() as session:
                repo = VideoRepository(session)
                await repo.update_folder(registered_id, folder_id)

            tasks.append(
                PlaylistTaskItem(
                    item_id=registered_id,
                    item_type="video",
                    task_id=None,  # Videos have no queue task_id
                    title=title,
                    url=watch_url,
                    skipped=False,
                )
            )
            to_download.append(
                {"video_id": registered_id, "url": watch_url, "resolution": request.resolution}
            )

        queued_count = len(to_download)

        # Step 4 — Start single orchestration background task (serial downloads)
        async def _download_playlist_serially(items: list):
            """Downloads each video one at a time to avoid resource exhaustion."""
            for item in items:
                try:
                    await video_manager.download_video_with_status_async(
                        item["video_id"],
                        item["url"],
                        resolution=item["resolution"],
                        sse_manager=sse_manager,
                    )
                    logger.success(f"Playlist video done: {item['video_id']}")
                except Exception as exc:
                    logger.error(
                        f"Playlist video failed: {item['video_id']} — {exc}"
                    )
                    # Continue with next item even if one fails

        if to_download:
            background_tasks.add_task(_download_playlist_serially, to_download)

        logger.info(
            f"Video playlist '{playlist_title}': {queued_count} scheduled, "
            f"{skipped_count} skipped, folder={folder_id}"
        )

        return PlaylistDownloadResponse(
            playlist_title=playlist_title,
            playlist_url=playlist_url,
            folder_id=folder_id,
            total_items=len(entries),
            queued_items=queued_count,
            skipped_items=skipped_count,
            tasks=tasks,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error processing video playlist: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing video playlist: {exc}",
        )

```

**Step 2: Verify application imports without errors**

Run: `python -c "from app.uwtv.main import app; print('app imported OK')"`

Expected output:
```
app imported OK
```

**Step 3: Commit**

```bash
git add app/uwtv/main.py
git commit -m "feat: add POST /video/playlist endpoint"
```

Expected output (last line):
```
 1 file changed, 113 insertions(+)
```

**If Task Fails:**

1. **`list` type hint on Python < 3.9:** Replace `list` with `List` (already imported).
2. **`_download_playlist_serially` is a local async function and `background_tasks.add_task` does not await it:** This is intentional — FastAPI's `BackgroundTasks.add_task` accepts coroutine functions and calls them in the background. The function signature `async def` is correct.
3. **Rollback:** `git checkout -- app/uwtv/main.py`

---

## Task 6: Code Review Checkpoint

After Tasks 1-5 are complete, dispatch a code review.

**Step 1: Dispatch all 6 reviewers in parallel**

REQUIRED SUB-SKILL: Use ring:requesting-code-review

All reviewers run simultaneously: ring:code-reviewer, ring:business-logic-reviewer, ring:security-reviewer, ring:test-reviewer, ring:nil-safety-reviewer, ring:consequences-reviewer. Wait for all to complete.

**Step 2: Handle findings by severity**

- **Critical/High/Medium:** Fix immediately (do NOT add TODO comments). Re-run all 6 reviewers after fixes. Repeat until zero Critical/High/Medium issues remain.
- **Low:** Add `TODO(review): [issue] (reported by [reviewer] on 2026-04-28, severity: Low)` comment in code at relevant location.
- **Cosmetic/Nitpick:** Add `FIXME(nitpick): [issue] (reported by [reviewer] on 2026-04-28, severity: Cosmetic)` comment in code.

**Step 3: Proceed only when**

- Zero Critical/High/Medium issues remain
- All Low issues have `TODO(review):` comments
- All Cosmetic issues have `FIXME(nitpick):` comments

---

## Task 7: Smoke Test — Import and Server Start

**Prerequisites:**
- Tasks 1-6 complete

**Step 1: Import smoke test**

Run: `python -c "from app.uwtv.main import app; from app.models.audio import PlaylistDownloadRequest, PlaylistDownloadResponse, PlaylistTaskItem; from app.services.managers import AudioDownloadManager, VideoDownloadManager; import inspect; print('audio method:', inspect.iscoroutinefunction(AudioDownloadManager().extract_playlist_info)); print('video method:', inspect.iscoroutinefunction(VideoDownloadManager().extract_playlist_info)); print('ALL OK')"`

Expected output:
```
audio method: True
video method: True
ALL OK
```

**Step 2: Start server**

Run in a separate terminal (or background):
```bash
uv run uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output (last relevant lines):
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**If you see `RuntimeError: Invalid cookie configuration`:** Set `YT_COOKIES_FROM_BROWSER=chrome` (or another browser) or `YT_COOKIES_FILE=/path/to/cookies.txt` before starting.

**Step 3: Authenticate and get token**

Run (replace `your_client_id` and `your_client_secret` with values from `app/services/securities.py`'s `AUTHORIZED_CLIENTS`):
```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id": "your_client_id", "client_secret": "your_client_secret"}' | python -m json.tool
```

Expected output (structure):
```json
{
    "access_token": "eyJ...",
    "token_type": "bearer"
}
```

Set the token: `export TOKEN="eyJ..."`

**Step 4: Test `/audio/playlist` with a non-playlist URL (must return 400)**

```bash
curl -s -X POST http://localhost:8000/audio/playlist \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' | python -m json.tool
```

Expected output:
```json
{
    "detail": "URL does not appear to be a playlist or returned no entries: ..."
}
```

**Step 5: Test `/audio/playlist` with a real short playlist URL**

Use any YouTube playlist URL with 2-5 items for quick testing (find a short public playlist — search YouTube for "short playlist" or use your own). Replace `<YOUR_PLAYLIST_ID>` below:
```bash
curl -s -X POST http://localhost:8000/audio/playlist \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/playlist?list=<YOUR_PLAYLIST_ID>", "skip_existing": true, "high_quality": false}' \
  | python -m json.tool
```

Expected output (structure — values will differ):
```json
{
    "playlist_title": "Some Playlist Name",
    "playlist_url": "https://www.youtube.com/playlist?list=...",
    "folder_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "total_items": 3,
    "queued_items": 3,
    "skipped_items": 0,
    "tasks": [
        {
            "item_id": "xxxxxxxxxxx",
            "item_type": "audio",
            "task_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
            "title": "Video Title",
            "url": "https://www.youtube.com/watch?v=xxxxxxxxxxx",
            "skipped": false
        }
    ]
}
```

**Step 6: Verify folder was created in DB**

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT id, name, description FROM folders ORDER BY created_date DESC LIMIT 1;"
```

Expected output (values will differ):
```
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx|Some Playlist Name|Playlist: https://...
```

**Step 7: Verify audios were associated with the folder**

```bash
sqlite3 /media/marvinbraga/python/marvin/youtube_downloader/data/youtube_downloader.db \
  "SELECT id, title, folder_id, download_status FROM audios WHERE folder_id IS NOT NULL ORDER BY created_date DESC LIMIT 5;"
```

Expected output (rows for each playlist item):
```
xxxxxxxxxxx|Video Title|xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx|downloading
```

**Step 8: Test `/video/playlist` endpoint**

Use the same short playlist URL you found in Step 5 (replace `<YOUR_PLAYLIST_ID>`):
```bash
curl -s -X POST http://localhost:8000/video/playlist \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/playlist?list=<YOUR_PLAYLIST_ID>", "resolution": "720p", "skip_existing": true}' \
  | python -m json.tool
```

Expected output (structure):
```json
{
    "playlist_title": "Some Playlist Name",
    "playlist_url": "...",
    "folder_id": "...",
    "total_items": 3,
    "queued_items": 3,
    "skipped_items": 0,
    "tasks": [
        {
            "item_id": "xxxxxxxxxxx",
            "item_type": "video",
            "task_id": null,
            "title": "Video Title",
            "url": "...",
            "skipped": false
        }
    ]
}
```

**Note:** `task_id` is `null` for video items (no queue, background orchestration).

**If Task Fails:**

1. **`detail: URL does not appear to be a playlist` on a valid playlist URL:** yt-dlp may need authentication. Ensure cookie env variable is set.
2. **`500 Internal Server Error`:** Check uvicorn terminal output for the full traceback.
3. **Folder created but no audios associated:** Check that `update_folder` calls use the correct `audio_id` (the returned value from `register_audio_for_download`, not `video_id` from the entry).
4. **Rollback all changes:** `git reset --hard HEAD~5` (reverts the 5 commits from Tasks 1-5).

---

## Task 8: Final Commit and Verification

**Step 1: Final import smoke test**

Run: `python -c "from app.uwtv.main import app; print('FINAL OK')"`

Expected output:
```
FINAL OK
```

**Step 2: Verify git log shows all 5 feature commits**

Run: `git log --oneline -6`

Expected output (most recent first):
```
xxxxxxx feat: add POST /video/playlist endpoint
xxxxxxx feat: add POST /audio/playlist endpoint
xxxxxxx feat: add extract_playlist_info to VideoDownloadManager
xxxxxxx feat: add extract_playlist_info to AudioDownloadManager
xxxxxxx feat: add PlaylistDownloadRequest, PlaylistTaskItem, PlaylistDownloadResponse models
xxxxxxx (previous commit)
```

**Step 3: Verify API schema reflects new endpoints**

With server running:
```bash
curl -s http://localhost:8000/openapi.json | python -c "import sys,json; spec=json.load(sys.stdin); endpoints=[p for p in spec['paths'] if 'playlist' in p]; print(endpoints)"
```

Expected output:
```
['/audio/playlist', '/video/playlist']
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `app/models/audio.py` | Added `PlaylistDownloadRequest`, `PlaylistTaskItem`, `PlaylistDownloadResponse` |
| `app/services/managers.py` | Added `extract_playlist_info()` to `AudioDownloadManager` and `VideoDownloadManager` |
| `app/uwtv/main.py` | Updated imports; added `POST /audio/playlist` and `POST /video/playlist` endpoints |

**No schema migrations required.** The `folders`, `audios`, and `videos` tables already have all needed columns (`folder_id` FK on audios/videos, `Folder` table with all fields).
