"""Tests for startup queue recovery of orphaned transcriptions.

Covers the core invariants of the recovery feature:

  (a) ``enqueue_transcription(force=False)`` treats a "queued"/"started" row as
      already in progress and does NOT submit (endpoint semantics preserved);
  (b) ``enqueue_transcription(force=True)`` BYPASSES the in-progress guard and
      DOES submit — this is the trap that would otherwise make recovery a silent
      no-op (every orphan is "queued"/"started");
  (c) ``recover_pending_transcriptions`` resets "started" -> "queued", re-submits
      both audio and video orphans, and reports the count;
  (d) idempotency: a finished ("ended") row whose .md exists is never re-submitted
      even with force=True.

These exercise the reusable core directly (asyncio.run) and do NOT use the
``client`` fixture, so they don't depend on the app lifespan / cookie env.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import app.uwtv.main as main
from app.uwtv.main import EnqueueOutcome


def _audio_row(status: str):
    return {
        "id": "audio-1",
        "path": "audio/recovery-unique-audio.mp3",
        "transcription_status": status,
        "storage_backend": "s3",
        "s3_key": "audio/recovery-unique-audio.mp3",
    }


# ---------------------------------------------------------------------------
# (a) force=False -> queued row is IN_PROGRESS, no submit
# ---------------------------------------------------------------------------


def test_enqueue_queued_without_force_is_in_progress():
    submit = MagicMock()
    storage_mock = AsyncMock()
    storage_mock.download_to_temp = AsyncMock(return_value="/tmp/mat.mp3")

    with (
        patch(
            "app.uwtv.main.audio_manager.get_audio_info",
            new=AsyncMock(return_value=_audio_row("queued")),
        ),
        patch("app.uwtv.main.get_storage", return_value=storage_mock),
        patch.object(main._transcription_executor, "submit", submit),
    ):
        result = asyncio.run(
            main.enqueue_transcription("audio-1", provider="groq", language="pt")
        )

    assert result.outcome is EnqueueOutcome.IN_PROGRESS
    submit.assert_not_called()


# ---------------------------------------------------------------------------
# (b) force=True -> queued row IS submitted (the trap is closed)
# ---------------------------------------------------------------------------


def test_enqueue_queued_with_force_submits():
    submit = MagicMock()
    update_status = AsyncMock()
    storage_mock = AsyncMock()
    storage_mock.download_to_temp = AsyncMock(return_value="/tmp/mat.mp3")

    with (
        patch(
            "app.uwtv.main.audio_manager.get_audio_info",
            new=AsyncMock(return_value=_audio_row("queued")),
        ),
        patch(
            "app.uwtv.main.audio_manager.update_transcription_status",
            new=update_status,
        ),
        patch("app.uwtv.main.get_storage", return_value=storage_mock),
        patch.object(main._transcription_executor, "submit", submit),
    ):
        result = asyncio.run(
            main.enqueue_transcription(
                "audio-1", provider="groq", language="pt", force=True
            )
        )

    assert result.outcome is EnqueueOutcome.SUBMITTED
    submit.assert_called_once()
    # Item re-marked "queued" before submit.
    update_status.assert_awaited_with("audio-1", "queued")


# ---------------------------------------------------------------------------
# (c) recover_pending_transcriptions: started->queued, submits audio+video
# ---------------------------------------------------------------------------


def test_recover_resets_started_and_resubmits_audio_and_video():
    # One audio orphan in "started", one video orphan in "queued".
    audio_obj = MagicMock(id="audio-1", transcription_status="started")
    video_obj = MagicMock(id="video-1", transcription_status="queued")

    audio_repo = MagicMock()
    audio_repo.get_by_transcription_status = AsyncMock(return_value=[audio_obj])
    video_repo = MagicMock()
    video_repo.get_by_transcription_status = AsyncMock(return_value=[video_obj])

    # get_db_context() is an async context manager returning a session.
    class _Ctx:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *a):
            return False

    audio_update = AsyncMock()
    video_update = AsyncMock()

    calls = []

    async def fake_enqueue(file_id, *, provider, language, is_video, force):
        calls.append((file_id, is_video, force))
        return main.EnqueueResult(EnqueueOutcome.SUBMITTED)

    def _repo_factory(repo):
        return lambda _session: repo

    with (
        patch("app.uwtv.main.get_db_context", return_value=_Ctx()),
        patch("app.uwtv.main.AudioRepository", new=_repo_factory(audio_repo)),
        patch("app.uwtv.main.VideoRepository", new=_repo_factory(video_repo)),
        patch(
            "app.uwtv.main.audio_manager.update_transcription_status",
            new=audio_update,
        ),
        patch(
            "app.uwtv.main.video_manager.update_transcription_status",
            new=video_update,
        ),
        patch("app.uwtv.main.enqueue_transcription", side_effect=fake_enqueue),
    ):
        recovered = asyncio.run(main.recover_pending_transcriptions())

    assert recovered == 2
    # The "started" audio was reset to "queued".
    audio_update.assert_awaited_once_with("audio-1", "queued")
    # The already-"queued" video was NOT reset.
    video_update.assert_not_awaited()
    # Both were re-enqueued with force=True.
    assert ("audio-1", False, True) in calls
    assert ("video-1", True, True) in calls


# ---------------------------------------------------------------------------
# (c') per-item error isolation: one failure does not abort the rest
# ---------------------------------------------------------------------------


def test_recover_isolates_per_item_failure():
    a1 = MagicMock(id="audio-1", transcription_status="queued")
    a2 = MagicMock(id="audio-2", transcription_status="queued")

    audio_repo = MagicMock()
    audio_repo.get_by_transcription_status = AsyncMock(return_value=[a1, a2])
    video_repo = MagicMock()
    video_repo.get_by_transcription_status = AsyncMock(return_value=[])

    class _Ctx:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *a):
            return False

    async def fake_enqueue(file_id, *, provider, language, is_video, force):
        if file_id == "audio-1":
            raise RuntimeError("boom")
        return main.EnqueueResult(EnqueueOutcome.SUBMITTED)

    with (
        patch("app.uwtv.main.get_db_context", return_value=_Ctx()),
        patch("app.uwtv.main.AudioRepository", new=lambda _s: audio_repo),
        patch("app.uwtv.main.VideoRepository", new=lambda _s: video_repo),
        patch(
            "app.uwtv.main.audio_manager.update_transcription_status",
            new=AsyncMock(),
        ),
        patch("app.uwtv.main.enqueue_transcription", side_effect=fake_enqueue),
    ):
        recovered = asyncio.run(main.recover_pending_transcriptions())

    # audio-1 failed; audio-2 still recovered.
    assert recovered == 1


# ---------------------------------------------------------------------------
# (d) idempotency: ended row with existing .md is never re-submitted
# ---------------------------------------------------------------------------


def test_enqueue_ended_is_idempotent_even_with_force(tmp_path):
    submit = MagicMock()
    md = tmp_path / "done.md"
    md.write_text("x")

    # S3-backed so media resolution succeeds via mocked storage; the ended-check
    # (which fires after resolution) is what we're asserting wins.
    ended_row = {
        "id": "audio-1",
        "path": "audio/whatever.mp3",
        "transcription_status": "ended",
        "transcription_path": md.name,
        "storage_backend": "s3",
        "s3_key": "audio/whatever.mp3",
    }

    storage_mock = AsyncMock()
    storage_mock.download_to_temp = AsyncMock(return_value="/tmp/mat-ended.mp3")

    with (
        patch("app.uwtv.main.DOWNLOADS_DIR", tmp_path),
        patch(
            "app.uwtv.main.audio_manager.get_audio_info",
            new=AsyncMock(return_value=ended_row),
        ),
        patch("app.uwtv.main.get_storage", return_value=storage_mock),
        patch.object(main._transcription_executor, "submit", submit),
    ):
        result = asyncio.run(
            main.enqueue_transcription(
                "audio-1", provider="groq", language="pt", force=True
            )
        )

    assert result.outcome is EnqueueOutcome.ALREADY_ENDED
    submit.assert_not_called()
