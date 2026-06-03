"""Tests for the dedicated transcription concurrency executor.

Covers:
  (a) the default concurrency limit is 2;
  (b) enqueuing a transcription sets the status to "queued" (not "started").
"""

from unittest.mock import AsyncMock, patch

import app.uwtv.main as main


# ---------------------------------------------------------------------------
# (a) default concurrency limit
# ---------------------------------------------------------------------------


def test_default_transcription_concurrency_is_2():
    """The dedicated executor caps simultaneous transcriptions at 2 by default."""
    from app.services.configs import TRANSCRIPTION_CONCURRENCY

    assert TRANSCRIPTION_CONCURRENCY == 2
    # The module-level executor must honor that limit.
    assert main._transcription_executor._max_workers == 2


# ---------------------------------------------------------------------------
# (b) enqueue -> status "queued"
# ---------------------------------------------------------------------------


def test_enqueue_sets_status_queued(client):
    """POST /audio/transcribe enqueues and marks the row 'queued' before submit.

    The executor's ``submit`` is patched to a no-op so the worker never flips
    queued -> started; this isolates the enqueue-time status write.

    An S3-backed row is used so the media file is materialized from (mocked)
    storage instead of requiring a real local file, and a unique relative path
    guarantees the ``.md`` transcript does not pre-exist (which would otherwise
    short-circuit the handler to "ended").
    """
    audio_info = {
        "id": "audio-uuid-123",
        "path": "audio/transcribe-concurrency-test-unique.mp3",
        "transcription_status": "none",
        "storage_backend": "s3",
        "s3_key": "audio/transcribe-concurrency-test-unique.mp3",
    }

    update_status = AsyncMock()

    storage_mock = AsyncMock()
    storage_mock.download_to_temp = AsyncMock(return_value="/tmp/materialized.mp3")

    with (
        patch(
            "app.uwtv.main.audio_manager.get_audio_info",
            new=AsyncMock(return_value=audio_info),
        ),
        patch(
            "app.uwtv.main.audio_manager.update_transcription_status",
            new=update_status,
        ),
        patch("app.uwtv.main.get_storage", return_value=storage_mock),
        # No-op submit: the handler awaits the "queued" write BEFORE submit, so
        # status is observable without the worker racing it to "started".
        patch.object(main._transcription_executor, "submit", lambda fn: None),
    ):
        response = client.post(
            "/audio/transcribe",
            json={
                "file_id": "audio-uuid-123",
                "provider": "groq",
                "language": "pt",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "processing"

    # The row must have been marked "queued" at enqueue time (not "started").
    update_status.assert_awaited_once_with("audio-uuid-123", "queued")
