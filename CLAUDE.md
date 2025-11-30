# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube Downloader is a FastAPI-based service for downloading and streaming YouTube videos/audio with transcription support. It uses yt-dlp for downloads, SSE for real-time progress updates, SQLite for data persistence, and integrates with Groq/OpenAI for audio transcription.

## Commands

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --extra dev

# Run the server
uv run uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
```

## Architecture

### Core Components

- **`app/uwtv/main.py`** - FastAPI application with all endpoints (auth, video/audio streaming, download queue, transcription)
- **`app/services/managers.py`** - `VideoStreamManager` (YouTube streaming) and `AudioDownloadManager` (download + metadata management)
- **`app/services/download_queue.py`** - Async download queue with priority, retry logic, and SSE callbacks
- **`app/services/sse_manager.py`** - Server-Sent Events for real-time download progress
- **`app/services/transcription/service.py`** - Audio transcription using Groq/OpenAI providers

### Database Layer (SQLite)

- **`app/db/database.py`** - SQLAlchemy async engine, session factory, and migration from JSON
- **`app/db/models.py`** - SQLAlchemy models (`Audio`, `Video`) with `to_dict()` methods
- **`app/db/repositories.py`** - Repository pattern for database operations (`AudioRepository`, `VideoRepository`)

The database is initialized on application startup via `lifespan` context manager. If `data/audios.json` exists and the database is empty, data is automatically migrated.

### Data Flow

1. Audio downloads are registered first (status: "downloading"), then processed via background queue
2. Download progress is broadcast via SSE to connected clients
3. Metadata is persisted to SQLite (`data/youtube_downloader.db`)
4. Audio files are stored in `downloads/audio/{youtube_id}/`

### Key Patterns

- JWT authentication for all endpoints (see `app/services/securities.py`)
- Pydantic models for request/response validation (`app/models/`)
- Async processing with `BackgroundTasks` and custom download queue
- yt-dlp runs in executor to avoid blocking event loop
- Repository pattern for database operations

### Configuration

- `app/services/configs.py` - Directory paths (DATA_DIR, DOWNLOADS_DIR, AUDIO_DIR)
- Environment variables for secrets (JWT_SECRET, API keys for transcription)
- Database: `data/youtube_downloader.db` (SQLite)
