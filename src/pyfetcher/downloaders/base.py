"""Base downloader protocol for :mod:`pyfetcher.downloaders`.

Purpose:
    Define the common interface for all downloader implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """Extracted media metadata before download."""

    url: str
    title: str | None = None
    description: str | None = None
    duration_seconds: float | None = None
    thumbnail_url: str | None = None
    uploader: str | None = None
    upload_date: str | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
    ext: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Result of a completed download."""

    source_url: str
    local_path: str | None = None
    minio_key: str | None = None
    minio_bucket: str | None = None
    filename: str | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
    checksum_sha256: str | None = None
    media_info: MediaInfo | None = None
    media_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DownloadProgress:
    """Progress update during a download."""

    status: str  # 'downloading', 'finished', 'error', 'postprocessing'
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    speed_bytes_per_sec: float | None = None
    eta_seconds: float | None = None
    filename: str | None = None
    percent: float | None = None


class DownloaderProtocol(Protocol):
    """Protocol for downloader implementations."""

    async def extract_info(self, url: str) -> list[MediaInfo]: ...
    async def download(
        self,
        url: str,
        *,
        output_dir: str,
        progress_callback: Any | None = None,
    ) -> list[DownloadResult]: ...
