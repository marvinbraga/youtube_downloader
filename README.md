# YouTube Downloader

FastAPI service for downloading and streaming video/audio from YouTube and Instagram, with built-in transcription support.

<!-- Languages & Runtime -->
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-DE5FE9.svg?style=for-the-badge&logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Docker](https://img.shields.io/badge/Docker-2496ED.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

<!-- Backend Frameworks & Libraries -->
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Uvicorn](https://img.shields.io/badge/Uvicorn-499848.svg?style=for-the-badge&logo=gunicorn&logoColor=white)](https://www.uvicorn.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063.svg?style=for-the-badge&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00.svg?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57.svg?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![JWT](https://img.shields.io/badge/JWT-000000.svg?style=for-the-badge&logo=jsonwebtokens&logoColor=white)](https://jwt.io/)

<!-- Media & Sources -->
[![yt-dlp](https://img.shields.io/badge/yt--dlp-FF0000.svg?style=for-the-badge&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![YouTube](https://img.shields.io/badge/YouTube-FF0000.svg?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/)
[![Instagram](https://img.shields.io/badge/Instagram-E4405F.svg?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-007808.svg?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

<!-- Storage -->
[![AWS S3](https://img.shields.io/badge/AWS_S3-569A31.svg?style=for-the-badge&logo=amazons3&logoColor=white)](https://aws.amazon.com/s3/)
[![MinIO](https://img.shields.io/badge/MinIO-C72E49.svg?style=for-the-badge&logo=minio&logoColor=white)](https://min.io/)
[![aioboto3](https://img.shields.io/badge/aioboto3-FF9900.svg?style=for-the-badge&logo=amazonaws&logoColor=white)](https://github.com/terricain/aioboto3)

<!-- Transcription Providers -->
[![Groq](https://img.shields.io/badge/Groq-F55036.svg?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991.svg?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)

<!-- Frontend -->
[![Bootstrap](https://img.shields.io/badge/Bootstrap_5-7952B3.svg?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![jQuery](https://img.shields.io/badge/jQuery-0769AD.svg?style=for-the-badge&logo=jquery&logoColor=white)](https://jquery.com/)

<!-- Project Status -->
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code_style-ruff-D7FF64.svg?style=for-the-badge&logo=ruff&logoColor=black)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-FAB040.svg?style=for-the-badge&logo=precommit&logoColor=white)](https://pre-commit.com/)

## Features

- Video and audio downloads from YouTube and Instagram via yt-dlp
- Real-time video/audio streaming
- Asynchronous download queue with priority and retry logic
- Live progress updates via Server-Sent Events (SSE)
- Audio transcription (Groq / OpenAI)
- JWT authentication
- SQLite persistence
- Web interface for management and playback
- Strategy pattern for adding new source platforms
- Per-source cookie support for authenticated downloads

## Requirements

- Python 3.10 – 3.12
- [uv](https://docs.astral.sh/uv/) (package manager)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd youtube_downloader

# Install dependencies
uv sync

# Install with development dependencies
uv sync --extra dev
```

## Configuration

Create a `.env` file at the project root:

```env
JWT_SECRET=your_secret_key
GROQ_API_KEY=your_groq_key       # optional, for transcription
OPENAI_API_KEY=your_openai_key   # optional, for transcription

# Optional per-source cookies (Netscape format or browser name)
YT_COOKIES_FROM_BROWSER=chrome           # or firefox, brave, edge, ...
YT_COOKIES_FILE=/path/to/youtube.txt     # alternative: file-based cookies
INSTAGRAM_COOKIES_FROM_BROWSER=chrome    # for private Instagram content
INSTAGRAM_COOKIES_FILE=/path/to/ig.txt
```

## Running

```bash
# Start the server
uv run uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`.

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
- Transcription pulls S3-backed media to a tempfile via `Storage.download_to_temp()`; the tempfile is removed in a `finally` block after the transcript is produced.

### Local development with MinIO

```bash
docker compose --profile s3-dev up -d
# Open http://localhost:9001 (minioadmin / minioadmin).
# The minio-init sidecar auto-creates the bucket "youtube-downloader-dev"
# (override via MINIO_DEV_BUCKET in your .env).
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

## Main Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/token` | Authentication (returns JWT) |
| POST | `/audio/download` | Start audio download |
| GET | `/audio/download-status/{id}` | Download status |
| GET | `/audio/stream/{id}` | Audio stream |
| GET | `/audio/list` | List downloaded audios |
| DELETE | `/audio/{id}` | Delete audio |
| POST | `/video/download` | Start video download |
| GET | `/video/stream/{id}` | Video stream |
| GET | `/video/list-downloads` | List downloaded videos |
| DELETE | `/video/{id}` | Delete video |
| POST | `/transcription/transcribe` | Transcribe audio |
| GET | `/downloads/events` | SSE feed for download progress |

## Architecture

```
app/
├── core/                       # Logging and shared configuration
├── db/                         # Database layer (SQLite + SQLAlchemy)
│   ├── database.py             # Engine, sessions, schema migrations
│   ├── models.py               # Audio / Video models
│   └── repositories.py         # Repository pattern
├── models/                     # Pydantic request/response models
├── services/                   # Business logic
│   ├── managers.py             # Stream and download managers
│   ├── download_queue.py       # Async download queue
│   ├── sse_manager.py          # Server-Sent Events
│   ├── downloaders/            # Per-platform Strategy implementations
│   │   ├── base.py             # Abstract Downloader
│   │   ├── factory.py          # URL-to-strategy routing
│   │   ├── youtube.py          # YouTube strategy
│   │   └── instagram.py        # Instagram strategy
│   └── transcription/          # Transcription service
└── uwtv/
    └── main.py                 # FastAPI app and endpoints
```

## Data Layout

```
data/
└── youtube_downloader.db       # SQLite database (audios, videos, folders)

downloads/
├── audio/{external_id}/        # Downloaded audio files
└── videos/{external_id}/       # Downloaded video files
```

Each row carries both `source` (`youtube` | `instagram`) and `external_id`, with `youtube_id` kept as a legacy alias for backward compatibility.

## Web Client

The `web_client/` directory contains a single-page web interface (vanilla jQuery + Bootstrap 5, no build step) for managing downloads, playing back media, and triggering transcriptions.

## Adding a New Source Platform

Source support follows the Strategy pattern:

1. Implement a new class extending `Downloader` in `app/services/downloaders/`.
2. Register the platform hosts in `app/services/downloaders/factory.py`.
3. Add the new value to the `Source` enums in `app/models/audio.py` and `app/models/video.py`.
4. Update the frontend URL validator in `web_client/js/app.js`.

See `instagram.py` for a reference implementation.

## Technologies

- **FastAPI** + **Uvicorn** — Web framework and ASGI server
- **yt-dlp** — Multi-platform video extractor
- **SQLAlchemy** (async) + **aiosqlite** — ORM and SQLite driver
- **Pydantic** — Request/response validation
- **SSE-Starlette** — Server-Sent Events
- **Groq** / **OpenAI** — Audio transcription providers
- **PyJWT** — Authentication
- **Bootstrap 5** + **jQuery** — Web client UI

## License

GNU Affero General Public License v3.0 (AGPL-3.0) — see [LICENSE](LICENSE) for the full text.

Summary of obligations for anyone redistributing this software or running it as a network service:

- Make the source code available (including modifications) under the same license
- Preserve copyright notices and references to the AGPL
- State the significant changes made to the code
- If the software is offered to users over a network (SaaS), the operator must give those users access to the corresponding source code

Users running the software locally, without distributing it or exposing it as a network service to third parties, have no additional obligations.
