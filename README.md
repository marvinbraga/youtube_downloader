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

## Persistence Manual

The service exposes a single contract: every finished download lands at a stable, addressable location, and every row knows which backend stores its bytes. How that contract is fulfilled is a deployment decision. This section covers every supported mode.

### Quick decision matrix

| Your situation | Recommended mode |
|---|---|
| Local development, single user, small library | **Local filesystem** (default) |
| Home server / NAS, occasional access | **Local filesystem** on external mount |
| Production single-host with Docker | **Docker bind mount** to a dedicated host path |
| Production multi-host, shared access | **AWS S3** (or S3-compatible) |
| Self-hosted alternative to AWS | **MinIO** (S3 protocol, runs in Docker) |
| Cost-optimized cold archive | **Backblaze B2** / **Wasabi** / **Cloudflare R2** (S3-compatible) |
| Testing without real cloud | **LocalStack** or **MinIO** dev profile |
| Hybrid (local for hot, S3 for cold) | **Local + S3** with `S3_DELETE_LOCAL_AFTER_UPLOAD=false` |

The implementation distinguishes two backend families (`local` and `s3`), selected at startup via `STORAGE_BACKEND`. Each row stores its own `storage_backend` value, so legacy data downloaded under a previous mode keeps working when you switch.

### Behavior shared by every mode

- **yt-dlp always writes to local disk first.** ffmpeg muxing requires seekable files, so a transient local copy is unavoidable. With `STORAGE_BACKEND=s3`, the file is uploaded after download success.
- **Streaming endpoints branch per row.** Local rows serve bytes via `FileResponse` / `StreamingResponse`. S3 rows return a `302 Redirect` to a short-lived presigned GET URL.
- **Deletion order is local → DB → S3.** Local FS first, DB row next, S3 object best-effort last. An S3 orphan is recoverable via a sweeper; a DB row pointing at a missing S3 object is user-visible breakage.
- **Transcription is backend-agnostic.** S3-backed rows are materialized into a `tempfile` via `Storage.download_to_temp()` (streamed in 8 MB chunks to avoid OOM), transcribed, then cleaned up in `finally`. Transcript markdown is always written to disk regardless of media backend.

### Mode 1 — Local filesystem (default)

#### 1.1. Default project paths (no configuration)

```env
# .env — nothing storage-related needed
```

Files go to `./downloads/audio/{id}/` and `./downloads/videos/{id}/` relative to the project root. SQLite lives at `./data/youtube_downloader.db`. Use this for development and quick trials.

#### 1.2. Custom host path (run outside Docker)

The download paths are derived from `app/services/configs.py`. To redirect them without modifying code, set the working directory and let `./downloads` resolve there:

```bash
cd /mnt/midia/youtube-downloader
uv run uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
```

The `downloads/` and `data/` directories will be created next to where the process starts.

#### 1.3. Docker bind mount (default `docker-compose.yml`)

```yaml
services:
  app:
    volumes:
      - ./data:/app/data
      - ./downloads:/app/downloads
      - ./cookies:/app/cookies:ro
```

The host's `./data` and `./downloads` directories are mounted into the container. Files are visible from both sides — `ls ./downloads/audio/` on the host shows what's inside. `docker compose down` does not remove them; only `rm -rf ./downloads` does.

#### 1.4. Bind mount to an external location

Edit `docker-compose.yml` to point at a different host path — useful for HDs, NAS mounts, or larger partitions:

```yaml
volumes:
  - /mnt/hd-externo/youtube-downloader/data:/app/data
  - /mnt/hd-externo/youtube-downloader/downloads:/app/downloads
```

Or parameterize via env so the compose file stays generic:

```yaml
volumes:
  - ${DATA_DIR:-./data}:/app/data
  - ${DOWNLOADS_DIR:-./downloads}:/app/downloads
```

```env
# .env
DATA_DIR=/mnt/hd-externo/youtube-downloader/data
DOWNLOADS_DIR=/mnt/hd-externo/youtube-downloader/downloads
```

#### 1.5. Docker-managed named volumes

Use this when you don't want to think about host paths and don't need to inspect files directly:

```yaml
services:
  app:
    volumes:
      - app-data:/app/data
      - app-downloads:/app/downloads

volumes:
  app-data:
  app-downloads:
```

Files live under `/var/lib/docker/volumes/youtube_downloader_app-downloads/_data/`. Survive `docker compose down`; lost only with `docker compose down -v`.

#### 1.6. Network filesystem (NFS / SMB)

Mount the remote share on the host first, then bind-mount that path into the container:

```bash
# Host
sudo mount -t nfs nas.local:/exports/media /mnt/nas-media

# docker-compose.yml
volumes:
  - /mnt/nas-media/youtube-downloader/downloads:/app/downloads
```

Caveats: NFS locks can interact poorly with SQLite. Keep `data/` on local disk and only put `downloads/` on the share.

### Mode 2 — Object storage via S3 protocol

Set `STORAGE_BACKEND=s3` plus a bucket and a region. Credentials are resolved via the standard AWS chain (env, `~/.aws/credentials`, IAM role, IRSA, container metadata, SSO). Prefer instance/role identity over inline keys in production.

#### 2.1. AWS S3 (production)

```env
STORAGE_BACKEND=s3
AWS_S3_BUCKET=my-prod-bucket
AWS_REGION=us-east-1
# Credentials picked up from IAM role attached to the EC2/ECS/EKS workload.
S3_PRESIGNED_URL_TTL=21600          # 6h — covers long sessions
S3_DELETE_LOCAL_AFTER_UPLOAD=true   # default; switch to false for hybrid
```

Minimum IAM permissions on the bucket: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:HeadObject`.

#### 2.2. AWS S3 with explicit credentials (workstation / CI)

```env
STORAGE_BACKEND=s3
AWS_S3_BUCKET=my-personal-bucket
AWS_REGION=sa-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

Use this only when an IAM role isn't available. Never commit the populated `.env`.

#### 2.3. MinIO (self-hosted S3 protocol)

Two deployment paths:

**Dev / local MinIO via this repo's Docker profile:**

```bash
docker compose --profile s3-dev up -d
# Console: http://localhost:9001 (minioadmin / minioadmin)
# Bucket "youtube-downloader-dev" auto-created by the minio-init sidecar.
```

```env
STORAGE_BACKEND=s3
AWS_S3_BUCKET=youtube-downloader-dev
AWS_REGION=us-east-1
AWS_S3_ENDPOINT_URL=http://minio:9000     # inside compose network
# Or: http://localhost:9000 if running the app outside compose
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
```

Override the bucket name via `MINIO_DEV_BUCKET` in `.env` before bringing the profile up.

**Production MinIO (separate host or cluster):**

```env
STORAGE_BACKEND=s3
AWS_S3_BUCKET=media-archive
AWS_REGION=us-east-1                       # arbitrary; MinIO ignores
AWS_S3_ENDPOINT_URL=https://minio.internal.example.com
AWS_ACCESS_KEY_ID=<minio-access-key>
AWS_SECRET_ACCESS_KEY=<minio-secret-key>
```

#### 2.4. Other S3-compatible providers

The endpoint and region are the only knobs that change. Tested-equivalent endpoints:

| Provider | `AWS_S3_ENDPOINT_URL` | `AWS_REGION` |
|---|---|---|
| **DigitalOcean Spaces** | `https://nyc3.digitaloceanspaces.com` (substitute region) | `nyc3` / `sfo3` / `fra1` etc. |
| **Backblaze B2** | `https://s3.us-west-002.backblazeb2.com` (your region) | `us-west-002` |
| **Wasabi** | `https://s3.us-east-1.wasabisys.com` | `us-east-1` |
| **Cloudflare R2** | `https://<account-id>.r2.cloudflarestorage.com` | `auto` |
| **LocalStack** (test) | `http://localhost:4566` | `us-east-1` |

Pick the region documented by the provider and use their access-key/secret pair.

#### 2.5. Tuning knobs

| Variable | Default | Effect |
|---|---|---|
| `S3_PRESIGNED_URL_TTL` | `21600` (6h) | Validity window of stream redirect URLs. Max 7 days (AWS hard cap). |
| `S3_DELETE_LOCAL_AFTER_UPLOAD` | `true` | `false` keeps a redundant local copy after successful upload (hybrid mode). |
| `AWS_S3_KEY_PREFIX` | unset | Prepended to every key (e.g., `youtube-downloader/audio/abc.m4a`). Useful for sharing a bucket with other apps. |

### Mode 3 — Hybrid setups

#### 3.1. Local hot + S3 archive (`S3_DELETE_LOCAL_AFTER_UPLOAD=false`)

Both copies persist. Streaming still goes through the S3 path. Use when:

- You want a disaster-recovery copy on disk
- Re-uploads to a different bucket are anticipated
- Local FS is fast enough that you'd rather not pay S3 egress on every play

Trade-off: disk usage doubles.

#### 3.2. Mixed-vintage library

After switching `STORAGE_BACKEND` from `local` to `s3`, **existing rows are not migrated**. Each row keeps the `storage_backend` value it had when finished downloading. Streaming endpoints transparently serve local rows from disk and S3 rows from S3 — no UI distinction.

To force a row onto the new backend, delete and re-download it via the API (yt-dlp will re-fetch the source).

### Mode 4 — Testing without real cloud

LocalStack and the bundled MinIO dev profile both speak the S3 protocol. Point `AWS_S3_ENDPOINT_URL` at them and you can run the full upload/presigned-URL/download cycle offline. The repo's `docker compose --profile s3-dev` is the lowest-friction option.

### Cookies and downloads/ in Docker (orthogonal to storage backend)

```yaml
volumes:
  - ./cookies:/app/cookies:ro
```

```env
YT_COOKIES_FILE=/app/cookies/youtube.txt
INSTAGRAM_COOKIES_FILE=/app/cookies/instagram.txt
```

These paths are read-only inside the container and never persisted to S3; they belong to the yt-dlp authentication layer, not the storage layer.

### Migrating data between modes

There is no built-in migration tool. The recommended workflow is one of:

1. **Stop the service, copy bytes, swap config.**
   ```bash
   # Local → S3 (example with aws-cli)
   aws s3 sync ./downloads s3://my-bucket/youtube-downloader/

   # Update the DB to flip rows to s3 (manual SQL or a one-off script)
   sqlite3 ./data/youtube_downloader.db "UPDATE audios SET storage_backend='s3', s3_key='youtube-downloader/'||path WHERE storage_backend='local';"
   ```

2. **Delete + re-download.** Simplest when the library is small or the source URLs are still accessible.

3. **Side-by-side.** Run a second instance pointing at the new backend, copy individual rows, switch DNS / port.

### Known v1 limitations

- No retroactive migration of legacy local rows (see above for manual workflows).
- `app/services/files.py:scan_video_directory` only lists files on disk — S3-only rows are visible via the DB-backed `/video/list-downloads`, not via the legacy `/videos` filesystem scan.
- Transcription markdown files always live on disk regardless of media storage backend.
- Single uvicorn worker recommended. SQLite write contention degrades multi-worker throughput; move to Postgres before scaling out.

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
