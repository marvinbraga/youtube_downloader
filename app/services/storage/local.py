"""Local filesystem storage backend (default).

Preserves the legacy behavior: files live under DOWNLOADS_DIR and are
served via FileResponse/StreamingResponse. `key` is a relative path
under DOWNLOADS_DIR (matches the `path` column populated by managers).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.services.configs import DOWNLOADS_DIR
from app.services.storage.base import Storage


class LocalStorage(Storage):
    backend_name = "local"

    async def put_file(
        self,
        local_path: Path,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        # File is already where it needs to be. Just return the key.
        return key

    async def get_url(self, key: str, filename: Optional[str] = None) -> str:
        raise NotImplementedError(
            "LocalStorage does not produce URLs; stream the file directly."
        )

    async def delete(self, key: str) -> bool:
        # missing_ok=True handles the TOCTOU window between exists() and unlink()
        # (concurrent delete or external cleanup). Matches S3Storage's
        # best-effort delete contract: a vanished object is a successful delete.
        path = DOWNLOADS_DIR / key
        path.unlink(missing_ok=True)
        return True

    async def exists(self, key: str) -> bool:
        return (DOWNLOADS_DIR / key).exists()

    async def download_to_temp(self, key: str) -> Path:
        # File is already local — return the canonical path.
        return DOWNLOADS_DIR / key
