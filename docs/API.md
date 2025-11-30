# API Reference

Complete API documentation for YouTube Downloader.

## Base URL

```
http://localhost:8000
```

## Authentication

All endpoints (except `/auth/token`) require JWT authentication.

### Headers

```
Authorization: Bearer <token>
```

---

## Endpoints

### Authentication

#### POST /auth/token

Get JWT access token.

**Request Body:**
```json
{
  "client_id": "your_client_id",
  "client_secret": "your_client_secret"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

---

### Audio

#### GET /audio/list

List all downloaded audio files.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sort_by` | string | `modified_date` | Sort field |
| `sort_order` | string | `desc` | Sort order (asc/desc) |

**Response:**
```json
{
  "audio_files": [
    {
      "id": "abc123",
      "name": "Song Title",
      "title": "Song Title",
      "path": "audio/abc123/Song Title.m4a",
      "format": "m4a",
      "filesize": 15000000,
      "duration": 240.5,
      "created_date": "2024-01-15T10:30:00",
      "modified_date": "2024-01-15T10:35:00",
      "download_status": "ready",
      "download_progress": 100,
      "transcription_status": "ended",
      "transcription_path": "audio/abc123/Song Title.md"
    }
  ],
  "total": 1
}
```

#### POST /audio/download

Start audio download from YouTube.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "high_quality": true
}
```

**Response:**
```json
{
  "status": "processando",
  "audio_id": "VIDEO_ID",
  "title": "Video Title",
  "message": "Download iniciado"
}
```

#### GET /audio/download-status/{audio_id}

Get download progress.

**Response:**
```json
{
  "id": "VIDEO_ID",
  "title": "Video Title",
  "download_status": "downloading",
  "download_progress": 45,
  "filesize": 15000000
}
```

#### GET /audio/stream/{audio_id}

Stream audio file.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | string | JWT token (alternative to header) |

**Response:** Audio stream with `Content-Type: audio/mp4`

#### GET /audio/check_exists

Check if audio already exists.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | string | YouTube URL |

**Response:**
```json
{
  "exists": true,
  "audio_id": "VIDEO_ID",
  "audio_info": { ... }
}
```

#### DELETE /audio/{audio_id}

Delete audio file and metadata.

**Response:**
```json
{
  "status": "success",
  "message": "Áudio excluído com sucesso"
}
```

---

### Video

#### GET /videos

List available videos for streaming.

**Response:**
```json
{
  "videos": [
    {
      "id": "video_id",
      "name": "Video Name",
      "path": "/path/to/video.mp4"
    }
  ]
}
```

#### GET /video/list-downloads

List downloaded videos.

**Response:**
```json
{
  "videos": [
    {
      "id": "VIDEO_ID",
      "youtube_id": "VIDEO_ID",
      "title": "Video Title",
      "resolution": "1080p",
      "filesize": 500000000,
      "duration": 600.0,
      "download_status": "ready",
      "download_progress": 100,
      "created_date": "2024-01-15T10:30:00",
      "modified_date": "2024-01-15T10:45:00"
    }
  ],
  "total": 1
}
```

#### POST /video/download

Start video download from YouTube.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "resolution": "1080p"
}
```

**Resolution Options:** `360p`, `480p`, `720p`, `1080p`, `1440p`, `2160p`, `best`

**Response:**
```json
{
  "status": "processando",
  "video_id": "VIDEO_ID",
  "title": "Video Title",
  "message": "Download iniciado"
}
```

#### GET /video/download-status/{video_id}

Get video download progress.

**Response:**
```json
{
  "id": "VIDEO_ID",
  "title": "Video Title",
  "download_status": "downloading",
  "download_progress": 60,
  "resolution": "1080p"
}
```

#### GET /video/stream/{video_id}

Stream video file.

**Response:** Video stream with `Content-Type: video/mp4`

#### DELETE /video/{video_id}

Delete video file and metadata.

**Response:**
```json
{
  "status": "success",
  "message": "Vídeo excluído com sucesso"
}
```

---

### Transcription

#### POST /audio/transcribe

Start audio transcription.

**Request Body:**
```json
{
  "file_id": "AUDIO_ID",
  "provider": "groq",
  "language": "pt"
}
```

**Providers:** `groq`, `openai`, `fast`, `local`

**Languages:** `pt`, `en`, `es`, `fr`, `de`, `it`, `ja`, `ko`, `zh`

**Response:**
```json
{
  "file_id": "AUDIO_ID",
  "transcription_path": "audio/AUDIO_ID/file.md",
  "status": "processing",
  "message": "A transcrição foi iniciada em segundo plano"
}
```

#### GET /audio/transcription/{file_id}

Get transcription file content.

**Response:** Markdown file with `Content-Type: text/markdown`

#### GET /audio/transcription_status/{file_id}

Get transcription status.

**Response:**
```json
{
  "file_id": "AUDIO_ID",
  "status": "ended",
  "transcription_path": "audio/AUDIO_ID/file.md"
}
```

**Status Values:** `none`, `started`, `ended`, `error`

#### DELETE /audio/transcription/{file_id}

Delete transcription file.

**Response:**
```json
{
  "status": "success",
  "message": "Transcrição excluída com sucesso",
  "file_id": "AUDIO_ID"
}
```

---

### Download Queue

#### GET /downloads/queue/status

Get queue status.

**Response:**
```json
{
  "total_tasks": 5,
  "pending": 2,
  "in_progress": 1,
  "completed": 2,
  "failed": 0,
  "cancelled": 0,
  "processing": true
}
```

#### GET /downloads/queue/tasks

List queue tasks.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status |
| `limit` | int | Max results (default: 50) |

**Response:**
```json
{
  "tasks": [
    {
      "id": "task-uuid",
      "audio_id": "VIDEO_ID",
      "url": "https://youtube.com/...",
      "status": "in_progress",
      "progress": 45,
      "priority": 0,
      "created_at": "2024-01-15T10:30:00",
      "started_at": "2024-01-15T10:30:05",
      "completed_at": null,
      "error": null,
      "retry_count": 0
    }
  ],
  "total": 1
}
```

#### POST /downloads/queue/cancel/{task_id}

Cancel a download task.

**Response:**
```json
{
  "status": "success",
  "message": "Download cancelado"
}
```

#### POST /downloads/queue/retry/{task_id}

Retry a failed download.

**Response:**
```json
{
  "status": "success",
  "message": "Download reagendado"
}
```

#### DELETE /downloads/queue/cleanup

Remove completed/cancelled tasks from queue.

**Response:**
```json
{
  "status": "success",
  "removed": 5,
  "message": "5 tarefas removidas"
}
```

---

### Server-Sent Events

#### GET /audio/download-events

SSE stream for real-time download updates.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | string | JWT token |

**Event Types:**
- `download_started` - Download began
- `download_progress` - Progress update
- `download_completed` - Download finished
- `download_error` - Error occurred

**Event Format:**
```
event: download_progress
data: {"audio_id": "VIDEO_ID", "progress": 45, "message": "Downloading..."}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message description"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Rate Limiting

No rate limiting is implemented. For production use, consider adding rate limiting middleware.

## CORS

CORS is enabled for all origins (`*`). Restrict in production.
