"""Base downloader protocol for :mod:`pyfetcher.downloaders`.

Purpose:
    Define the common interface for all downloader implementations.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import JsonValue

from pyfetcher.media.models import (
    ImageInfo,
    MediaKind,
    MediaMetadata,
    MediaProvenance,
    PixelDimensions,
    ThumbnailInfo,
    media_kind,
)


def _json(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json(item) for item in value]
    return str(value)


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
    kind: MediaKind | None = None
    width: int | None = None
    height: int | None = None
    thumbnails: tuple[ThumbnailInfo, ...] = ()
    provider: str | None = None
    extractor: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> MediaMetadata:
        """Normalize legacy downloader information into the canonical model."""
        dimensions = (
            PixelDimensions(width=self.width, height=self.height)
            if self.width and self.height
            else None
        )
        thumbnails = self.thumbnails
        if self.thumbnail_url and not thumbnails:
            thumbnails = (ThumbnailInfo(url=self.thumbnail_url),)
        resolved_kind = self.kind or media_kind(
            mime_type=self.mime_type,
            extension=self.ext,
        )
        image = (
            ImageInfo(dimensions=dimensions)
            if dimensions is not None and resolved_kind in {"image", "animation"}
            else None
        )
        return MediaMetadata(
            kind=resolved_kind,
            source_url=self.url,
            mime_type=self.mime_type,
            extension=(self.ext or "").lstrip(".") or None,
            file_size_bytes=self.file_size_bytes,
            title=self.title,
            description=self.description,
            duration_seconds=self.duration_seconds,
            uploader=self.uploader,
            upload_date=self.upload_date,
            image=image,
            thumbnails=thumbnails,
            provenance=MediaProvenance(
                provider=self.provider,
                extractor=self.extractor,
                source="provider",
            ),
            extra={str(key): _json(value) for key, value in self.extra.items()},
        )


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
    normalized_metadata: MediaMetadata | None = None
    media_metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> MediaMetadata:
        """Return canonical metadata enriched with local download information."""
        metadata = self.normalized_metadata or (
            self.media_info.to_metadata()
            if self.media_info is not None
            else MediaMetadata(
                kind=media_kind(
                    mime_type=self.mime_type,
                    extension=Path(self.filename or "").suffix,
                ),
                source_url=self.source_url,
            )
        )
        return metadata.model_copy(
            update={
                "path": self.local_path or metadata.path,
                "filename": self.filename or metadata.filename,
                "mime_type": self.mime_type or metadata.mime_type,
                "file_size_bytes": (
                    self.file_size_bytes
                    if self.file_size_bytes is not None
                    else metadata.file_size_bytes
                ),
                "checksum_sha256": self.checksum_sha256 or metadata.checksum_sha256,
                "extra": {
                    **metadata.extra,
                    **{str(key): _json(value) for key, value in self.media_metadata.items()},
                },
            }
        )

    def byte_stream(self):
        """Open the downloaded local file through the common byte adapter."""
        from pyfetcher.streams import ByteStream

        return ByteStream.from_download_result(self)


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


type DownloaderItems[ItemT] = Iterable[ItemT] | AsyncIterable[ItemT]
type DownloaderResult[ItemT] = DownloaderItems[ItemT] | Awaitable[DownloaderItems[ItemT]]
type ProgressCallback = Callable[[DownloadProgress], None]


class DownloaderProtocol(Protocol):
    """Minimal sync/async iterable protocol for downloader implementations."""

    def extract_info(self, url: str) -> DownloaderResult[MediaInfo]: ...

    def download(
        self,
        url: str,
        *,
        output_dir: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloaderResult[DownloadResult]: ...


class MetadataDownloaderProtocol(Protocol):
    """Optional capability for canonical provider metadata extraction."""

    async def extract_metadata(self, url: str) -> list[MediaMetadata]: ...


__all__ = [
    "DownloaderProtocol",
    "DownloaderItems",
    "DownloadProgress",
    "DownloadResult",
    "DownloaderResult",
    "MediaInfo",
    "MetadataDownloaderProtocol",
    "ProgressCallback",
]
