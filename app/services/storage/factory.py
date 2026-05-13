"""Storage backend factory.

A single Storage instance is cached per process. The choice is made at
first call and never re-read — to switch backends, restart the process
(or call ``reset_storage_for_tests()`` in test code only).
This is intentional: live-switching invalidates every in-flight
post-download upload and every cached presigned URL.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from app.services.configs import STORAGE_BACKEND
from app.services.storage.base import Storage
from app.services.storage.local import LocalStorage

# TODO(review): lazy-import S3Storage inside the s3 branch so aioboto3
# isn't imported when STORAGE_BACKEND=local. Cosmetic — package is in
# pyproject either way. (code-reviewer, 2026-05-13, Severity: Low)
from app.services.storage.s3 import S3Storage

_storage_instance: Optional[Storage] = None


def get_storage() -> Storage:
    """Return the process-wide Storage instance.

    The lifespan startup hook in app/uwtv/main.py calls get_storage() before
    any request can reach the cache, so the bare if-check is sufficient in
    practice. If you remove that warm-up, wrap this lookup in a threading.Lock.
    """
    global _storage_instance
    if _storage_instance is None:
        if STORAGE_BACKEND == "s3":
            _storage_instance = S3Storage()
            logger.info("Storage backend: S3")
        else:
            _storage_instance = LocalStorage()
            logger.info("Storage backend: local")
    return _storage_instance


def reset_storage_for_tests() -> None:
    """Clear the cached instance. Tests only."""
    global _storage_instance
    _storage_instance = None
