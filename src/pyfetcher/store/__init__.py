"""Object storage (MinIO/S3) for :mod:`pyfetcher`.

Purpose:
    Provide async object storage operations for uploading, downloading,
    and managing binary assets in MinIO or S3-compatible stores.
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from pyfetcher.store.client import ObjectStoreClient  # noqa: F401
except Exception:  # pragma: no cover  # nosec B110
    pass
else:
    __all__.append("ObjectStoreClient")
