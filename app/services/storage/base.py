"""Storage strategy abstract base.

Two concrete implementations live alongside this module:
- LocalStorage (default; preserves legacy filesystem behavior)
- S3Storage   (opt-in via STORAGE_BACKEND=s3)

The Strategy abstracts only what differs across backends:
- where the canonical bytes live after download
- how a client retrieves them (direct file vs presigned URL)
- how to delete them
- how to make a seekable local copy for tools that need one (transcription)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class Storage(ABC):
    """Abstract storage backend."""

    backend_name: str = "abstract"

    @abstractmethod
    async def put_file(
        self,
        local_path: Path,
        key: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload (or register) the file. Returns a backend-specific key.

        For LocalStorage this is a no-op that returns the relative path.
        For S3Storage this PUTs the object and returns the S3 key.
        """

    @abstractmethod
    async def get_url(self, key: str, filename: Optional[str] = None) -> str:
        """Return a URL the client can fetch the bytes from.

        For LocalStorage this raises NotImplementedError (the endpoint
        serves bytes directly via FileResponse — no URL needed).
        For S3Storage this returns a short-lived presigned GET URL.
        """

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete the underlying object. Returns True on success."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if the key resolves to a real object."""

    @abstractmethod
    async def download_to_temp(self, key: str) -> Path:
        """Materialize the object as a local file and return its path.

        Required by transcription, which needs a seekable on-disk file.
        Caller is responsible for cleaning up the returned path.
        For LocalStorage this is a no-op that returns the existing path.
        """
