# Database Documentation

Complete database layer documentation for YouTube Downloader.

## Overview

The application uses SQLite with SQLAlchemy async ORM for data persistence. The database stores metadata about downloaded audio and video files.

## Database Configuration

### Location

```
data/youtube_downloader.db
```

### Connection

```python
# app/db/database.py
DATABASE_URL = "sqlite+aiosqlite:///data/youtube_downloader.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)
```

---

## Models

### Audio Model

Stores metadata for downloaded audio files.

**Table:** `audios`

```python
class Audio(Base):
    __tablename__ = "audios"
```

**Columns:**

| Column | Type | Description | Default |
|--------|------|-------------|---------|
| `id` | String(100) | Primary key | - |
| `title` | String(500) | Audio title | - |
| `name` | String(500) | Display name | - |
| `youtube_id` | String(100) | YouTube video ID | null |
| `url` | String(1000) | Source URL | null |
| `path` | String(1000) | File path | "" |
| `directory` | String(1000) | Directory path | "" |
| `format` | String(20) | Audio format | "m4a" |
| `filesize` | Integer | File size in bytes | 0 |
| `download_status` | String(50) | Download state | "pending" |
| `download_progress` | Integer | Progress percentage | 0 |
| `download_error` | Text | Error message | null |
| `transcription_status` | String(50) | Transcription state | "none" |
| `transcription_path` | String(1000) | Transcription file path | "" |
| `keywords` | Text | JSON serialized keywords | "" |
| `created_date` | DateTime | Creation timestamp | now() |
| `modified_date` | DateTime | Last modification | now() |

**Status Values:**

- `download_status`: `pending`, `downloading`, `ready`, `error`
- `transcription_status`: `none`, `started`, `ended`, `error`

**Methods:**

```python
def to_dict(self) -> dict:
    """Converts model to dictionary for JSON serialization"""
```

---

### Video Model

Stores metadata for downloaded video files.

**Table:** `videos`

```python
class Video(Base):
    __tablename__ = "videos"
```

**Columns:**

| Column | Type | Description | Default |
|--------|------|-------------|---------|
| `id` | String(100) | Primary key | - |
| `title` | String(500) | Video title | - |
| `name` | String(500) | Display name | - |
| `youtube_id` | String(100) | YouTube video ID | null |
| `url` | String(1000) | Source URL | null |
| `path` | String(1000) | File path | "" |
| `directory` | String(1000) | Directory path | "" |
| `format` | String(20) | Video format | "mp4" |
| `filesize` | Integer | File size in bytes | 0 |
| `duration` | Float | Duration in seconds | null |
| `resolution` | String(20) | Video resolution | "" |
| `download_status` | String(50) | Download state | "pending" |
| `download_progress` | Integer | Progress percentage | 0 |
| `download_error` | Text | Error message | null |
| `source` | String(50) | Video source | "youtube" |
| `created_date` | DateTime | Creation timestamp | now() |
| `modified_date` | DateTime | Last modification | now() |

**Status Values:**

- `download_status`: `pending`, `downloading`, `ready`, `error`

**Methods:**

```python
def to_dict(self) -> dict:
    """Converts model to dictionary for JSON serialization"""
```

---

## Repositories

Repository pattern implementation for database operations.

### AudioRepository

```python
class AudioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
```

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_by_id` | `audio_id: str` | `Optional[Audio]` | Find by primary key |
| `get_by_youtube_id` | `youtube_id: str` | `Optional[Audio]` | Find by YouTube ID |
| `get_all` | `order_by_date: bool = True` | `List[Audio]` | List all audios |
| `get_by_status` | `status: str` | `List[Audio]` | Filter by download status |
| `create` | `audio: Audio` | `Audio` | Create new audio |
| `update` | `audio_id: str, **kwargs` | `Optional[Audio]` | Update audio fields |
| `delete` | `audio_id: str` | `bool` | Delete audio |
| `update_download_status` | `audio_id, status, progress, error` | `Optional[Audio]` | Update download state |
| `update_transcription_status` | `audio_id, status, path` | `Optional[Audio]` | Update transcription state |
| `complete_download` | `audio_id, path, directory, filesize` | `Optional[Audio]` | Mark download complete |
| `search_by_keyword` | `keyword: str` | `List[Audio]` | Search by title/keywords |

**Usage Example:**

```python
from app.db.database import get_db_context
from app.db.repositories import AudioRepository

async with get_db_context() as session:
    repo = AudioRepository(session)

    # Get all audios
    audios = await repo.get_all()

    # Find by YouTube ID
    audio = await repo.get_by_youtube_id("dQw4w9WgXcQ")

    # Update download progress
    await repo.update_download_status(
        audio_id="abc123",
        status="downloading",
        progress=50
    )

    # Complete download
    await repo.complete_download(
        audio_id="abc123",
        path="audio/abc123/song.m4a",
        directory="audio/abc123",
        filesize=15000000
    )
```

---

### VideoRepository

```python
class VideoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
```

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_by_id` | `video_id: str` | `Optional[Video]` | Find by primary key |
| `get_by_youtube_id` | `youtube_id: str` | `Optional[Video]` | Find by YouTube ID |
| `get_all` | `order_by_date: bool = True` | `List[Video]` | List all videos |
| `get_by_status` | `status: str` | `List[Video]` | Filter by download status |
| `create` | `video: Video` | `Video` | Create new video |
| `update` | `video_id: str, **kwargs` | `Optional[Video]` | Update video fields |
| `delete` | `video_id: str` | `bool` | Delete video |
| `update_download_status` | `video_id, status, progress, error` | `Optional[Video]` | Update download state |
| `complete_download` | `video_id, path, directory, filesize, duration, resolution` | `Optional[Video]` | Mark download complete |

**Usage Example:**

```python
from app.db.database import get_db_context
from app.db.repositories import VideoRepository

async with get_db_context() as session:
    repo = VideoRepository(session)

    # Get all videos
    videos = await repo.get_all()

    # Find by YouTube ID
    video = await repo.get_by_youtube_id("dQw4w9WgXcQ")

    # Complete download with metadata
    await repo.complete_download(
        video_id="abc123",
        path="videos/abc123/video.mp4",
        directory="videos/abc123",
        filesize=500000000,
        duration=180.5,
        resolution="1080p"
    )
```

---

## Session Management

### Dependency Injection

For FastAPI endpoints:

```python
from app.db.database import get_db

@app.get("/audio/list")
async def list_audio(db: AsyncSession = Depends(get_db)):
    repo = AudioRepository(db)
    return await repo.get_all()
```

### Context Manager

For service layer:

```python
from app.db.database import get_db_context

async def process_audio():
    async with get_db_context() as session:
        repo = AudioRepository(session)
        # Operations auto-commit on success, rollback on error
```

---

## Initialization

### Database Creation

On application startup:

```python
# app/uwtv/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await migrate_json_to_sqlite()
    yield

app = FastAPI(lifespan=lifespan)
```

### Migration from JSON

The system can migrate legacy JSON data:

```python
async def migrate_json_to_sqlite():
    """
    Migrates data from data/audios.json to SQLite.
    Only executes if database is empty.
    """
```

**Migration Process:**

1. Check if database has existing records
2. Load `data/audios.json` if exists
3. Create Audio records from JSON data
4. Parse datetime fields
5. Commit transaction

---

## SQL Schema

### audios Table

```sql
CREATE TABLE audios (
    id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    name VARCHAR(500) NOT NULL,
    youtube_id VARCHAR(100),
    url VARCHAR(1000),
    path VARCHAR(1000) NOT NULL DEFAULT '',
    directory VARCHAR(1000) NOT NULL DEFAULT '',
    format VARCHAR(20) NOT NULL DEFAULT 'm4a',
    filesize INTEGER NOT NULL DEFAULT 0,
    download_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    download_progress INTEGER NOT NULL DEFAULT 0,
    download_error TEXT,
    transcription_status VARCHAR(50) NOT NULL DEFAULT 'none',
    transcription_path VARCHAR(1000) NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    created_date DATETIME NOT NULL,
    modified_date DATETIME NOT NULL
);

CREATE INDEX ix_audios_youtube_id ON audios (youtube_id);
```

### videos Table

```sql
CREATE TABLE videos (
    id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    name VARCHAR(500) NOT NULL,
    youtube_id VARCHAR(100),
    url VARCHAR(1000),
    path VARCHAR(1000) NOT NULL DEFAULT '',
    directory VARCHAR(1000) NOT NULL DEFAULT '',
    format VARCHAR(20) NOT NULL DEFAULT 'mp4',
    filesize INTEGER NOT NULL DEFAULT 0,
    duration FLOAT,
    resolution VARCHAR(20) NOT NULL DEFAULT '',
    download_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    download_progress INTEGER NOT NULL DEFAULT 0,
    download_error TEXT,
    source VARCHAR(50) NOT NULL DEFAULT 'youtube',
    created_date DATETIME NOT NULL,
    modified_date DATETIME NOT NULL
);

CREATE INDEX ix_videos_youtube_id ON videos (youtube_id);
```

---

## Query Examples

### List Ready Audios with Transcription

```python
from sqlalchemy import select

async with get_db_context() as session:
    result = await session.execute(
        select(Audio)
        .where(Audio.download_status == "ready")
        .where(Audio.transcription_status == "ended")
        .order_by(Audio.modified_date.desc())
    )
    audios = result.scalars().all()
```

### Search Audios by Title

```python
async with get_db_context() as session:
    result = await session.execute(
        select(Audio)
        .where(Audio.title.ilike(f"%{search_term}%"))
    )
    audios = result.scalars().all()
```

### Get Download Statistics

```python
from sqlalchemy import func

async with get_db_context() as session:
    result = await session.execute(
        select(
            Audio.download_status,
            func.count(Audio.id)
        ).group_by(Audio.download_status)
    )
    stats = {status: count for status, count in result}
```
