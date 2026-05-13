"""S3 storage backend (opt-in).

Lifecycle decision: this implementation uses per-call `async with
session.client("s3", ...)` blocks. aioboto3 sessions are cheap; clients
are not, but for a service whose hot path is HTTP-bound (yt-dlp downloads
take seconds-to-minutes, S3 PUT takes seconds), per-call client creation
is well under the noise floor. Caching a long-lived client across the
asyncio event loop is a v2 optimization.

Credentials are resolved by aioboto3 via the standard AWS credential
chain. We never read AWS_SECRET_ACCESS_KEY directly here; we only pass
endpoint_url and region_name explicitly to support MinIO/LocalStack.
"""

from __future__ import annotations

import mimetypes
import tempfile
from pathlib import Path
from typing import Optional

import aioboto3
from botocore.exceptions import ClientError
from loguru import logger

from app.services.configs import (
    AWS_REGION,
    AWS_S3_BUCKET,
    AWS_S3_ENDPOINT_URL,
    AWS_S3_KEY_PREFIX,
    S3_PRESIGNED_URL_TTL,
)
from app.services.storage.base import Storage


def _full_key(key: str) -> str:
    """Apply the optional AWS_S3_KEY_PREFIX to a logical key."""
    if AWS_S3_KEY_PREFIX:
        # TODO(review): the .replace("//", "/") is redundant given strip("/") on
        # the prefix. Simplify to lstrip("/") on key. Not urgent. (code-reviewer,
        # 2026-05-13, Severity: Low)
        return f"{AWS_S3_KEY_PREFIX}/{key}".replace("//", "/")
    return key


class S3Storage(Storage):
    backend_name = "s3"

    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._client_kwargs = {"region_name": AWS_REGION}
        if AWS_S3_ENDPOINT_URL:
            # MinIO/LocalStack require path-style addressing.
            self._client_kwargs["endpoint_url"] = AWS_S3_ENDPOINT_URL

    def _client(self):
        return self._session.client("s3", **self._client_kwargs)

    async def put_file(
        self,
        local_path: Path,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        full_key = _full_key(key)
        if content_type is None:
            guessed, _ = mimetypes.guess_type(local_path.name)
            content_type = guessed or "application/octet-stream"

        async with self._client() as s3:
            with open(local_path, "rb") as fh:
                await s3.put_object(
                    Bucket=AWS_S3_BUCKET,
                    Key=full_key,
                    Body=fh,
                    ContentType=content_type,
                    ContentDisposition="inline",
                )
        logger.info(
            f"S3 PUT ok: s3://{AWS_S3_BUCKET}/{full_key} "
            f"({local_path.stat().st_size} bytes, {content_type})"
        )
        return full_key

    async def get_url(self, key: str, filename: Optional[str] = None) -> str:
        # Content-Disposition=inline ensures the browser plays the media
        # via the <audio>/<video> tag instead of downloading it.
        params = {"Bucket": AWS_S3_BUCKET, "Key": key}
        if filename:
            # RFC 5987 encoding for non-ASCII filenames.
            # FIXME(nitpick): this does not actually RFC 5987-encode the filename
            # (no filename*= variant, no percent-encoding). Non-ASCII filenames
            # may be mangled by some browsers. (code-reviewer, 2026-05-13, Cosmetic)
            params["ResponseContentDisposition"] = f'inline; filename="{filename}"'
        else:
            params["ResponseContentDisposition"] = "inline"

        async with self._client() as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=S3_PRESIGNED_URL_TTL,
            )
        return url

    async def delete(self, key: str) -> bool:
        try:
            async with self._client() as s3:
                await s3.delete_object(Bucket=AWS_S3_BUCKET, Key=key)
            logger.info(f"S3 DELETE ok: s3://{AWS_S3_BUCKET}/{key}")
            return True
        except ClientError as exc:
            logger.warning(f"S3 DELETE failed for {key}: {exc}")
            return False

    async def exists(self, key: str) -> bool:
        try:
            async with self._client() as s3:
                await s3.head_object(Bucket=AWS_S3_BUCKET, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    async def download_to_temp(self, key: str) -> Path:
        """Materialize an S3 object to a local tempfile and return its path.

        Caller owns the returned path and MUST `unlink(missing_ok=True)` it when
        done — see transcribe_audio() in app/uwtv/main.py for the canonical
        cleanup pattern (try/finally around the consumer). Returning a raw Path
        (rather than a context manager) is a pragmatic call: find_audio_file()
        has multiple return points and is consumed by background tasks whose
        lifetime extends beyond the request handler, so a `async with` API would
        force a deeper refactor of the transcription pipeline.
        """
        suffix = Path(key).suffix or ".bin"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        # M2 fix: stream chunks to disk to avoid loading the whole object into
        # memory. 8 MiB chunk is a balance between syscall overhead and RSS
        # footprint; for 1080p+ videos (>1 GB) this keeps peak memory bounded.
        try:
            async with self._client() as s3:
                response = await s3.get_object(Bucket=AWS_S3_BUCKET, Key=key)
                async with response["Body"] as stream:
                    with open(tmp_path, "wb") as f:
                        async for chunk in stream.iter_chunks(
                            chunk_size=8 * 1024 * 1024
                        ):
                            f.write(chunk)
        except Exception:
            # Don't leave a half-written tempfile on disk if streaming fails.
            tmp_path.unlink(missing_ok=True)
            raise

        logger.debug(f"S3 GET -> temp: s3://{AWS_S3_BUCKET}/{key} -> {tmp_path}")
        return tmp_path
