# Services Documentation

Complete service layer documentation for YouTube Downloader.

## Overview

The service layer contains the core business logic for downloading, streaming, transcription, and real-time event management.

## Service Components

```
app/services/
├── configs.py            # Path configurations
├── download_queue.py     # Async download queue
├── files.py              # File streaming utilities
├── locks.py              # Concurrency locks
├── managers.py           # Download managers
├── securities.py         # JWT authentication
├── sse_manager.py        # Server-Sent Events
└── transcription/        # Transcription service
    ├── parsers.py        # Whisper parsers
    └── service.py        # Transcription logic
```

---

## Managers (`managers.py`)

### VideoStreamManager

Handles direct YouTube video streaming without downloading.

```python
class VideoStreamManager:
    ydl_opts = {
        'format': 'best[ext=mp4]',
        'quiet': True,
        'no_warnings': True
    }
```

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_direct_url` | `url: str` | `str` | Get direct stream URL from YouTube |
| `stream_youtube_video` | `url: str` | `AsyncGenerator` | Stream video in 1MB chunks |

**Usage:**

```python
manager = VideoStreamManager()

# Get direct URL
direct_url = await manager.get_direct_url("https://youtube.com/watch?v=VIDEO_ID")

# Stream video
async for chunk in manager.stream_youtube_video(youtube_url):
    yield chunk
```

---

### AudioDownloadManager

Manages audio downloads with database persistence and SSE notifications.

```python
class AudioDownloadManager:
    def __init__(self):
        self.download_dir = AUDIO_DIR
```

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `extract_youtube_id` | `url: str` | `Optional[str]` | Extract YouTube ID from URL |
| `get_audio_info` | `audio_id: str` | `Optional[Dict]` | Get audio metadata |
| `get_audio_by_youtube_id` | `youtube_id: str` | `Optional[Dict]` | Find audio by YouTube ID |
| `get_all_audios` | - | `list` | List all audios |
| `register_audio_for_download` | `url: str` | `str` | Register audio with pending status |
| `download_audio_with_status_async` | `audio_id, url, sse_manager` | `str` | Execute download with progress |
| `update_transcription_status` | `audio_id, status, path` | `bool` | Update transcription state |
| `delete_audio` | `audio_id: str` | `bool` | Delete audio and files |

**Download Process:**

```
1. register_audio_for_download(url)
   └── Creates DB entry with status="downloading"

2. download_audio_with_status_async(audio_id, url, sse_manager)
   ├── Creates download directory
   ├── Configures yt-dlp options
   ├── Starts download in executor
   ├── Broadcasts SSE progress events
   └── Updates DB with final status
```

**yt-dlp Configuration:**

```python
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': '{download_dir}/{youtube_id}/%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
        'preferredquality': '192',
    }],
    'socket_timeout': 30,
    'retries': 10,
    'fragment_retries': 10,
    'noplaylist': True,
}
```

---

### VideoDownloadManager

Manages video downloads with resolution selection.

```python
class VideoDownloadManager:
    RESOLUTION_MAP = {
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        "best": "bestvideo+bestaudio/best",
    }
```

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `extract_youtube_id` | `url: str` | `Optional[str]` | Extract YouTube ID from URL |
| `get_video_info` | `video_id: str` | `Optional[Dict]` | Get video metadata |
| `get_video_by_youtube_id` | `youtube_id: str` | `Optional[Dict]` | Find video by YouTube ID |
| `get_all_videos` | - | `list` | List all videos |
| `register_video_for_download` | `url, resolution` | `str` | Register video with pending status |
| `download_video_with_status_async` | `video_id, url, resolution, sse_manager` | `str` | Execute download with progress |
| `delete_video` | `video_id: str` | `bool` | Delete video and files |

---

## Download Queue (`download_queue.py`)

Async download queue with concurrency control, priority, and retry logic.

### DownloadStatus Enum

```python
class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
```

### DownloadTask

```python
@dataclass
class DownloadTask:
    id: str
    audio_id: str
    url: str
    high_quality: bool = True
    status: DownloadStatus = DownloadStatus.QUEUED
    priority: int = 0  # Higher = higher priority
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: int = 5  # seconds
```

**Methods:**

- `can_retry()` - Check if retry is possible
- `should_retry_now()` - Check if retry should happen now
- `schedule_retry()` - Schedule next retry with exponential backoff

### DownloadQueue

```python
class DownloadQueue:
    def __init__(self, max_concurrent_downloads: int = 2):
        self.max_concurrent_downloads = max_concurrent_downloads
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_downloads: Dict[str, asyncio.Task] = {}
```

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `add_download` | `audio_id, url, high_quality, priority` | `str` | Add task to queue |
| `cancel_download` | `task_id: str` | `bool` | Cancel a download |
| `get_queue_status` | - | `Dict` | Get queue statistics |
| `get_task_status` | `task_id: str` | `Optional[DownloadTask]` | Get task details |
| `get_tasks_by_audio_id` | `audio_id: str` | `List[DownloadTask]` | Find tasks by audio |
| `start_processing` | - | - | Start queue processor |
| `stop_processing` | - | - | Stop queue processor |
| `cleanup_old_tasks` | `max_age_hours: int` | - | Remove old completed tasks |

**Callbacks:**

```python
download_queue.on_download_started = async_callback
download_queue.on_download_progress = async_callback
download_queue.on_download_completed = async_callback
download_queue.on_download_failed = async_callback
download_queue.on_download_cancelled = async_callback
```

**Retry Strategy:**

```
Exponential backoff: delay = base_delay * 2^(retry_count - 1)

Attempt 1: Immediate
Attempt 2: 5 seconds
Attempt 3: 10 seconds
Max attempts: 3
```

**Usage:**

```python
from app.services.download_queue import download_queue

# Start processing
download_queue.start_processing()

# Add download
task_id = await download_queue.add_download(
    audio_id="abc123",
    url="https://youtube.com/watch?v=VIDEO_ID",
    priority=1
)

# Check status
status = await download_queue.get_queue_status()
# {"total": 5, "queued": 2, "downloading": 1, "completed": 2, ...}

# Cancel download
await download_queue.cancel_download(task_id)

# Cleanup old tasks
await download_queue.cleanup_old_tasks(max_age_hours=24)
```

---

## SSE Manager (`sse_manager.py`)

Server-Sent Events for real-time download progress updates.

### DownloadEvent

```python
@dataclass
class DownloadEvent:
    audio_id: str
    event_type: str  # download_started, download_progress, download_completed, download_error
    progress: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None
```

**SSE Format:**

```
event: download_progress
data: {"audio_id": "abc123", "event_type": "download_progress", "progress": 45, "message": "Downloading...", "timestamp": "2024-01-15T10:30:00"}
```

### SSEManager

```python
class SSEManager:
    def __init__(self):
        self._clients: Dict[str, asyncio.Queue] = {}
        self._download_status: Dict[str, Dict] = {}
```

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `connect` | `client_id: str` | `asyncio.Queue` | Connect new SSE client |
| `disconnect` | `client_id: str` | - | Disconnect client |
| `broadcast_event` | `event: DownloadEvent` | - | Send event to all clients |
| `download_started` | `audio_id, message` | - | Notify download started |
| `download_progress` | `audio_id, progress, message` | - | Notify progress update |
| `download_completed` | `audio_id, message` | - | Notify download completed |
| `download_error` | `audio_id, error` | - | Notify download error |
| `get_download_status` | `audio_id: str` | `Optional[Dict]` | Get current status |
| `get_all_downloads_status` | - | `Dict[str, Dict]` | Get all statuses |

**Usage:**

```python
from app.services.sse_manager import sse_manager

# In endpoint - connect client
queue = await sse_manager.connect(client_id)

async def event_generator():
    try:
        while True:
            event = await queue.get()
            yield event
    except asyncio.CancelledError:
        sse_manager.disconnect(client_id)

# In download service - send events
await sse_manager.download_started("abc123", "Iniciando download...")
await sse_manager.download_progress("abc123", 50, "50% concluído")
await sse_manager.download_completed("abc123", "Download finalizado!")
```

---

## Transcription Service (`transcription/`)

Audio-to-text conversion using multiple providers.

### TranscriptionProvider Enum

```python
class TranscriptionProvider(str, Enum):
    GROQ = "groq"
    OPENAI = "openai"
    FAST = "fast"
    LOCAL = "local"
```

### TranscriptionService

```python
class TranscriptionService:
    @staticmethod
    def normalize_id(file_id: str) -> str

    @staticmethod
    def calculate_similarity(s1: str, s2: str) -> float

    @staticmethod
    def get_audio_manager() -> AudioDownloadManager

    @staticmethod
    def find_audio_file(file_id: str) -> Path

    @staticmethod
    def transcribe_audio(
        file_path: str,
        provider: TranscriptionProvider,
        language: str = "pt",
        **kwargs
    ) -> List[Dict]

    @staticmethod
    def save_transcription(
        docs: List[Dict],
        output_path: Optional[str] = None
    ) -> str
```

**Providers:**

| Provider | Implementation | Requirements |
|----------|---------------|--------------|
| `groq` | Groq Whisper API | `GROQ_API_KEY` |
| `openai` | OpenAI Whisper API | `OPENAI_API_KEY` |
| `fast` | FasterWhisper | GPU recommended |
| `local` | Whisper local | CPU/GPU |

**Supported Languages:**

`pt`, `en`, `es`, `fr`, `de`, `it`, `ja`, `ko`, `zh`

**Usage:**

```python
from app.services.transcription.service import TranscriptionService
from app.services.transcription.parsers import TranscriptionProvider

# Find audio file
audio_path = TranscriptionService.find_audio_file("abc123")

# Transcribe
docs = TranscriptionService.transcribe_audio(
    file_path=str(audio_path),
    provider=TranscriptionProvider.GROQ,
    language="pt"
)

# Save transcription
output_path = TranscriptionService.save_transcription(
    docs,
    output_path=str(audio_path) + ".md"
)
```

### AudioLoader

Custom blob loader for audio files.

```python
class AudioLoader(BlobLoader):
    def __init__(self, file_path: str):
        self.file_path = file_path

    def yield_blobs(self) -> Iterable[Blob]:
        """Returns audio blobs for processing"""
```

---

## Configuration (`configs.py`)

Path configurations for the application.

```python
from pathlib import Path

# Base directories
DATA_DIR = Path("data")
DOWNLOADS_DIR = Path("downloads")
AUDIO_DIR = DOWNLOADS_DIR / "audio"
VIDEO_DIR = DOWNLOADS_DIR / "videos"

# Config files
AUDIO_CONFIG_PATH = DATA_DIR / "audios.json"  # Legacy

# In-memory mappings
audio_mapping: Dict[str, Path] = {}
video_mapping: Dict[str, Path] = {}
```

---

## Authentication (`securities.py`)

JWT-based authentication.

```python
from jose import jwt
from fastapi import Depends, HTTPException

SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

def create_access_token(data: dict) -> str:
    """Create JWT token"""

def verify_token(token: str = Depends(oauth2_scheme)) -> dict:
    """Verify and decode JWT token"""
```

**Usage in Endpoints:**

```python
@app.get("/protected")
async def protected_endpoint(token_data: dict = Depends(verify_token)):
    return {"user": token_data["sub"]}
```

---

## Global Instances

The following singleton instances are available:

```python
# SSE Manager
from app.services.sse_manager import sse_manager

# Download Queue
from app.services.download_queue import download_queue

# Start queue processing (typically in app startup)
download_queue.start_processing()
```

---

## Error Handling

All services use Loguru for structured logging:

```python
from loguru import logger

logger.info("Operation started")
logger.debug("Debug information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.exception("Exception with traceback")
logger.success("Operation completed successfully")
```

Errors are propagated as `HTTPException` for API endpoints:

```python
from fastapi import HTTPException

raise HTTPException(
    status_code=404,
    detail="Resource not found"
)
```
