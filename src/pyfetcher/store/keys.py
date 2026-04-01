"""Object key generation for :mod:`pyfetcher.store`.

Purpose:
    Generate deterministic, organized object keys for MinIO/S3 storage
    based on content type, source, and identifiers.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import PurePosixPath

from slugify import slugify  # type: ignore[import-untyped]


def generate_media_key(
    *,
    source_url: str,
    filename: str | None = None,
    mime_type: str | None = None,
    prefix: str = "media",
) -> str:
    """Generate an organized object key for a media asset.

    Keys follow the pattern: {prefix}/{date}/{url_hash}/{filename}

    Args:
        source_url: The source URL of the media.
        filename: Original filename (derived from URL if not provided).
        mime_type: MIME type for extension fallback.
        prefix: Top-level prefix in the bucket.

    Returns:
        A string key suitable for MinIO/S3.
    """
    url_hash = hashlib.sha256(source_url.encode()).hexdigest()[:12]
    date_part = datetime.now(UTC).strftime("%Y/%m/%d")

    if filename:
        safe_name = slugify(PurePosixPath(filename).stem, max_length=80)
        ext = PurePosixPath(filename).suffix or _ext_from_mime(mime_type)
        name = f"{safe_name}{ext}"
    else:
        ext = _ext_from_mime(mime_type)
        name = f"{url_hash}{ext}"

    return f"{prefix}/{date_part}/{url_hash}/{name}"


def _ext_from_mime(mime_type: str | None) -> str:
    """Derive a file extension from a MIME type."""
    if not mime_type:
        return ""
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "audio/mpeg": ".mp3",
        "audio/ogg": ".ogg",
        "application/pdf": ".pdf",
    }
    return mapping.get(mime_type.split(";")[0].strip(), "")
