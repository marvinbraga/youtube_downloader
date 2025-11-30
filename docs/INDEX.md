# YouTube Downloader - Documentation Index

## Overview

YouTube Downloader is a FastAPI-based service for downloading and streaming YouTube videos/audio with transcription support.

## Documentation Structure

### Core Documentation

| Document | Description |
|----------|-------------|
| [Architecture](./ARCHITECTURE.md) | System architecture and component overview |
| [API Reference](./API.md) | Complete API endpoint documentation |
| [Database](./DATABASE.md) | Database models and repositories |
| [Services](./SERVICES.md) | Service layer documentation |

### Quick Links

- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints-summary)
- [Configuration](#configuration)

---

## Getting Started

### Requirements

- Python 3.10 - 3.12
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --extra dev
```

### Configuration

Create `.env` file:

```env
JWT_SECRET=your_secret_key
GROQ_API_KEY=your_groq_key      # optional
OPENAI_API_KEY=your_openai_key  # optional
```

### Running

```bash
uv run uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Project Structure

```
youtube_downloader/
├── app/
│   ├── core/                    # Core utilities
│   │   └── logging.py           # Loguru configuration
│   ├── db/                      # Database layer
│   │   ├── database.py          # SQLAlchemy engine & sessions
│   │   ├── models.py            # ORM models (Audio, Video)
│   │   └── repositories.py      # Repository pattern
│   ├── models/                  # Pydantic models
│   │   ├── audio.py             # Audio request/response models
│   │   └── video.py             # Video request/response models
│   ├── services/                # Business logic
│   │   ├── configs.py           # Path configurations
│   │   ├── download_queue.py    # Async download queue
│   │   ├── files.py             # File streaming utilities
│   │   ├── locks.py             # Concurrency locks
│   │   ├── managers.py          # Download managers
│   │   ├── securities.py        # JWT authentication
│   │   ├── sse_manager.py       # Server-Sent Events
│   │   └── transcription/       # Transcription service
│   │       ├── parsers.py       # Whisper parsers
│   │       └── service.py       # Transcription logic
│   └── uwtv/
│       └── main.py              # FastAPI application
├── data/
│   └── youtube_downloader.db    # SQLite database
├── downloads/
│   ├── audio/{id}/              # Audio files
│   └── videos/{id}/             # Video files
└── web_client/                  # Frontend application
    ├── css/styles.css
    ├── js/app.js
    └── index.html
```

---

## API Endpoints Summary

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/token` | Get JWT access token |

### Audio

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/audio/list` | List all audio files |
| POST | `/audio/download` | Start audio download |
| GET | `/audio/download-status/{id}` | Get download progress |
| GET | `/audio/stream/{id}` | Stream audio file |
| GET | `/audio/check_exists` | Check if audio exists |
| DELETE | `/audio/{id}` | Delete audio file |

### Video

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/videos` | List available videos |
| GET | `/video/list-downloads` | List downloaded videos |
| POST | `/video/download` | Start video download |
| GET | `/video/download-status/{id}` | Get download progress |
| GET | `/video/stream/{id}` | Stream video file |
| DELETE | `/video/{id}` | Delete video file |

### Transcription

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/audio/transcribe` | Start transcription |
| GET | `/audio/transcription/{id}` | Get transcription file |
| GET | `/audio/transcription_status/{id}` | Get transcription status |
| DELETE | `/audio/transcription/{id}` | Delete transcription |

### Download Queue

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/downloads/queue/status` | Queue status |
| GET | `/downloads/queue/tasks` | List tasks |
| POST | `/downloads/queue/cancel/{id}` | Cancel task |
| POST | `/downloads/queue/retry/{id}` | Retry failed task |
| DELETE | `/downloads/queue/cleanup` | Clean completed tasks |

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/audio/download-events` | SSE for download progress |

---

## Key Components

### Classes

| Class | Location | Description |
|-------|----------|-------------|
| `AudioDownloadManager` | `services/managers.py` | Audio download management |
| `VideoDownloadManager` | `services/managers.py` | Video download management |
| `VideoStreamManager` | `services/managers.py` | YouTube video streaming |
| `DownloadQueue` | `services/download_queue.py` | Async download queue |
| `SSEManager` | `services/sse_manager.py` | Server-Sent Events |
| `TranscriptionService` | `services/transcription/service.py` | Audio transcription |
| `AudioRepository` | `db/repositories.py` | Audio database operations |
| `VideoRepository` | `db/repositories.py` | Video database operations |

### Database Models

| Model | Table | Description |
|-------|-------|-------------|
| `Audio` | `audios` | Audio file metadata |
| `Video` | `videos` | Video file metadata |

### Transcription Providers

| Provider | Description |
|----------|-------------|
| `groq` | Groq Whisper API (fast) |
| `openai` | OpenAI Whisper API |
| `fast` | FasterWhisper (local) |
| `local` | Local Whisper model |

---

## Technologies

- **FastAPI** - Web framework
- **yt-dlp** - YouTube download
- **SQLAlchemy** + **aiosqlite** - Database ORM
- **SSE-Starlette** - Server-Sent Events
- **Groq/OpenAI** - Transcription APIs
- **PyJWT** - JWT authentication
- **Loguru** - Logging
- **Pydantic** - Data validation

---

## License

MIT
