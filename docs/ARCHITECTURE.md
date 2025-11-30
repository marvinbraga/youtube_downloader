# Architecture

System architecture and component overview for YouTube Downloader.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Client                                │
│                    (HTML/CSS/JavaScript)                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/SSE
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│                       (app/uwtv/main.py)                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Auth Handler │  │ REST Handler │  │   SSE Handler        │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                        Service Layer                             │
├──────────────┬──────────────┬──────────────┬───────────────────┤
│ Download     │ Stream       │ Transcription│ SSE               │
│ Queue        │ Managers     │ Service      │ Manager           │
└──────────────┴──────────────┴──────────────┴───────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                        Data Layer                                │
├──────────────────────────────┬──────────────────────────────────┤
│        SQLite Database       │         File System              │
│    (youtube_downloader.db)   │     (downloads/audio|video)      │
└──────────────────────────────┴──────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                      External Services                           │
├──────────────────────────────┬──────────────────────────────────┤
│          YouTube             │     Groq / OpenAI APIs           │
│         (yt-dlp)             │       (Transcription)            │
└──────────────────────────────┴──────────────────────────────────┘
```

## Component Details

### Application Layer

#### FastAPI Application (`app/uwtv/main.py`)

The main entry point that:
- Configures CORS middleware
- Initializes database on startup
- Registers all API endpoints
- Manages application lifecycle

**Key Features:**
- Async request handling
- Background task processing
- Static file serving for web client

### Service Layer

#### Download Queue (`app/services/download_queue.py`)

Manages concurrent downloads with priority and retry logic.

```python
class DownloadQueue:
    """
    Async download queue with:
    - Priority-based ordering
    - Configurable concurrent downloads (default: 2)
    - Automatic retry on failure (max: 3 attempts)
    - Callback hooks for progress updates
    """
```

**Flow:**
```
Add Download → Queue → Process → yt-dlp → Complete/Retry
                         │
                         ▼
                   SSE Callbacks
```

#### Stream Managers (`app/services/managers.py`)

Three manager classes:

| Manager | Purpose |
|---------|---------|
| `VideoStreamManager` | Direct YouTube streaming via yt-dlp |
| `AudioDownloadManager` | Audio download, metadata, transcription status |
| `VideoDownloadManager` | Video download, metadata management |

**AudioDownloadManager Methods:**
- `register_audio_for_download()` - Create entry before download
- `download_audio_with_status_async()` - Execute download with progress
- `get_audio_info()` - Retrieve metadata
- `update_transcription_status()` - Track transcription state
- `delete_audio()` - Remove file and database entry

#### SSE Manager (`app/services/sse_manager.py`)

Server-Sent Events for real-time updates.

```python
class SSEManager:
    """
    Manages SSE connections and broadcasts:
    - download_started
    - download_progress
    - download_completed
    - download_error
    """
```

**Event Format:**
```json
{
  "audio_id": "VIDEO_ID",
  "progress": 45,
  "message": "Downloading...",
  "timestamp": "2024-01-15T10:30:00"
}
```

#### Transcription Service (`app/services/transcription/`)

Audio-to-text conversion using multiple providers.

**Components:**
- `TranscriptionService` - Main service class
- `TranscriptionFactory` - Provider factory
- `GroqWhisperParser` - Groq Whisper implementation
- `AudioLoader` - File loading for langchain

**Providers:**
| Provider | Implementation | Notes |
|----------|---------------|-------|
| groq | Groq API | Fast, requires API key |
| openai | OpenAI API | Accurate, requires API key |
| fast | FasterWhisper | Local, requires GPU |
| local | Whisper local | Local, CPU-based |

**Process:**
```
Audio File → Chunk (20min) → Transcribe → Merge → Save .md
```

### Data Layer

#### Database (`app/db/`)

SQLite with SQLAlchemy async.

**Models:**
- `Audio` - Audio file metadata
- `Video` - Video file metadata

**Repositories:**
- `AudioRepository` - CRUD for audios
- `VideoRepository` - CRUD for videos

**Schema:**
```sql
-- audios table
CREATE TABLE audios (
    id VARCHAR PRIMARY KEY,
    youtube_id VARCHAR UNIQUE,
    title VARCHAR,
    path VARCHAR,
    format VARCHAR DEFAULT 'm4a',
    filesize INTEGER,
    duration FLOAT,
    download_status VARCHAR DEFAULT 'pending',
    download_progress INTEGER DEFAULT 0,
    transcription_status VARCHAR DEFAULT 'none',
    transcription_path VARCHAR,
    created_date DATETIME,
    modified_date DATETIME
);

-- videos table
CREATE TABLE videos (
    id VARCHAR PRIMARY KEY,
    youtube_id VARCHAR UNIQUE,
    title VARCHAR,
    path VARCHAR,
    resolution VARCHAR,
    format VARCHAR DEFAULT 'mp4',
    filesize INTEGER,
    duration FLOAT,
    download_status VARCHAR DEFAULT 'pending',
    download_progress INTEGER DEFAULT 0,
    created_date DATETIME,
    modified_date DATETIME
);
```

#### File System

```
downloads/
├── audio/
│   └── {youtube_id}/
│       ├── {title}.m4a         # Audio file
│       └── {title}.md          # Transcription
└── videos/
    └── {youtube_id}/
        └── {title}.mp4         # Video file
```

### Authentication

JWT-based authentication (`app/services/securities.py`).

**Flow:**
```
Client → POST /auth/token → JWT Token → Bearer Header → Protected Endpoints
```

**Token Structure:**
```json
{
  "sub": "client_id",
  "exp": 1704067200
}
```

## Data Flow

### Download Flow

```
1. Client POST /audio/download {url}
2. Register audio in DB (status: pending)
3. Add to download queue
4. Queue processes download with yt-dlp
5. SSE broadcasts progress updates
6. Update DB (status: ready)
7. Client receives completion event
```

### Transcription Flow

```
1. Client POST /audio/transcribe {file_id, provider}
2. Update DB (transcription_status: started)
3. Background task:
   a. Load audio file
   b. Split into 20-min chunks
   c. Send to transcription provider
   d. Merge results
   e. Save .md file
4. Update DB (transcription_status: ended)
5. Client polls status or receives notification
```

### Streaming Flow

```
1. Client GET /audio/stream/{id}
2. Verify JWT token
3. Lookup file path in DB
4. Stream file with range support
5. Client receives audio/video data
```

## Error Handling

### Retry Strategy

Download queue implements exponential backoff:
- Attempt 1: Immediate
- Attempt 2: 5 seconds delay
- Attempt 3: 15 seconds delay
- Max attempts: 3

### Error Propagation

```
Service Error → HTTPException → JSON Response → Client
```

All errors include:
- HTTP status code
- Detail message
- Logged with traceback

## Concurrency

### Async Operations

- All database operations are async (aiosqlite)
- Downloads run in thread executor (blocking yt-dlp)
- SSE connections are async generators

### Locks

File-level locking for concurrent access:
- Prevents duplicate downloads
- Thread-safe status updates

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `JWT_SECRET` | JWT signing key | Yes |
| `GROQ_API_KEY` | Groq API key | No |
| `OPENAI_API_KEY` | OpenAI API key | No |

### Path Configuration (`app/services/configs.py`)

```python
DATA_DIR = Path("data")
DOWNLOADS_DIR = Path("downloads")
AUDIO_DIR = DOWNLOADS_DIR / "audio"
VIDEO_DIR = DOWNLOADS_DIR / "videos"
```
