"""Serializable, provider-neutral media metadata contracts."""

from __future__ import annotations

import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, computed_field

type MediaKind = Literal[
    "image",
    "animation",
    "video",
    "audio",
    "document",
    "archive",
    "binary",
    "unknown",
]

_IMAGE_EXTENSIONS = {"avif", "bmp", "heic", "heif", "ico", "jpeg", "jpg", "png", "tif", "tiff"}
_ANIMATION_EXTENSIONS = {"apng", "gif", "webp"}
_VIDEO_EXTENSIONS = {"avi", "flv", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "webm"}
_AUDIO_EXTENSIONS = {"aac", "flac", "m4a", "mp3", "oga", "ogg", "opus", "wav", "wma"}
_DOCUMENT_EXTENSIONS = {"doc", "docx", "epub", "html", "md", "pdf", "txt"}
_ARCHIVE_EXTENSIONS = {"7z", "bz2", "gz", "rar", "tar", "xz", "zip"}


def media_kind(
    *,
    mime_type: str | None = None,
    extension: str | None = None,
    animated: bool | None = None,
) -> MediaKind:
    """Infer a coarse media kind from normalized MIME and extension hints."""
    mime = (mime_type or "").partition(";")[0].strip().lower()
    ext = (extension or "").lower().lstrip(".")
    if animated is True:
        return "animation"
    if mime.startswith("image/") or ext in _IMAGE_EXTENSIONS | _ANIMATION_EXTENSIONS:
        return "image"
    if mime.startswith("video/") or ext in _VIDEO_EXTENSIONS:
        return "video"
    if mime.startswith("audio/") or ext in _AUDIO_EXTENSIONS:
        return "audio"
    if mime.startswith("text/") or mime == "application/pdf" or ext in _DOCUMENT_EXTENSIONS:
        return "document"
    if ext in _ARCHIVE_EXTENSIONS:
        return "archive"
    if mime:
        return "binary"
    return "unknown"


class PixelDimensions(BaseModel):
    """Validated pixel size shared by images, videos, and thumbnails."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @computed_field
    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height


class ThumbnailInfo(BaseModel):
    """One provider or locally generated thumbnail candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str | None = None
    url: str | None = None
    path: str | None = None
    dimensions: PixelDimensions | None = None
    mime_type: str | None = None
    extension: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    preference: float | None = None
    generated: bool = False
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ImageInfo(BaseModel):
    """Raster image, animated GIF, or animated WebP details."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format: str | None = None
    dimensions: PixelDimensions
    mode: str | None = None
    has_alpha: bool = False
    animated: bool = False
    frame_count: int = Field(default=1, ge=1)
    frame_durations_ms: tuple[int, ...] = ()
    total_duration_seconds: float | None = Field(default=None, ge=0)
    loop_count: int | None = Field(default=None, ge=0)
    exif: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class VideoStreamInfo(BaseModel):
    """Normalized metadata for one video track."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int | None = Field(default=None, ge=0)
    codec: str | None = None
    format: str | None = None
    profile: str | None = None
    dimensions: PixelDimensions | None = None
    frame_rate: float | None = Field(default=None, gt=0)
    bit_rate: int | None = Field(default=None, ge=0)
    bit_depth: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    language: str | None = None
    color_space: str | None = None
    hdr_format: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class AudioStreamInfo(BaseModel):
    """Normalized metadata for one audio track."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int | None = Field(default=None, ge=0)
    codec: str | None = None
    format: str | None = None
    profile: str | None = None
    channels: int | None = Field(default=None, ge=1)
    sample_rate_hz: int | None = Field(default=None, gt=0)
    bit_rate: int | None = Field(default=None, ge=0)
    bit_depth: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    language: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class MediaProvenance(BaseModel):
    """Record where normalized media information originated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str | None = None
    extractor: str | None = None
    source: str = "unknown"
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MediaMetadata(BaseModel):
    """Canonical metadata shared by files and external media providers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: MediaKind = "unknown"
    source_url: str | None = None
    path: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    extension: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = None
    title: str | None = None
    description: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    bit_rate: int | None = Field(default=None, ge=0)
    container: str | None = None
    uploader: str | None = None
    upload_date: str | None = None
    image: ImageInfo | None = None
    video_streams: tuple[VideoStreamInfo, ...] = ()
    audio_streams: tuple[AudioStreamInfo, ...] = ()
    thumbnails: tuple[ThumbnailInfo, ...] = ()
    tags: tuple[str, ...] = ()
    provenance: MediaProvenance = Field(default_factory=MediaProvenance)
    extra: dict[str, JsonValue] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @computed_field
    @property
    def dimensions(self) -> PixelDimensions | None:
        if self.image is not None:
            return self.image.dimensions
        return next(
            (stream.dimensions for stream in self.video_streams if stream.dimensions),
            None,
        )

    @computed_field
    @property
    def primary_thumbnail(self) -> ThumbnailInfo | None:
        if not self.thumbnails:
            return None
        return max(
            self.thumbnails,
            key=lambda item: (
                item.preference if item.preference is not None else float("-inf"),
                (
                    item.dimensions.width * item.dimensions.height
                    if item.dimensions is not None
                    else 0
                ),
            ),
        )

    @classmethod
    def from_path_hints(
        cls,
        path: str | Path,
        *,
        mime_type: str | None = None,
        **values: object,
    ) -> MediaMetadata:
        """Build basic metadata without opening the file."""
        source = Path(path)
        resolved_mime = mime_type or mimetypes.guess_type(source.name)[0]
        extension = source.suffix.lower().lstrip(".") or None
        return cls(
            kind=media_kind(mime_type=resolved_mime, extension=extension),
            path=str(source),
            filename=source.name,
            mime_type=resolved_mime,
            extension=extension,
            file_size_bytes=source.stat().st_size if source.is_file() else None,
            **values,
        )


class ImageProcessingSpec(BaseModel):
    """Portable resize/convert policy for Pillow-backed image processing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    fit: Literal["contain", "cover", "stretch"] = "contain"
    output_format: str | None = None
    quality: int = Field(default=85, ge=1, le=100)
    preserve_animation: bool = True
    strip_metadata: bool = False


class MediaProcessingResult(BaseModel):
    """Typed result of a media processor or thumbnail generator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str
    source_path: str
    output_path: str
    metadata: MediaMetadata
    thumbnail: ThumbnailInfo | None = None


__all__ = [
    "AudioStreamInfo",
    "ImageInfo",
    "ImageProcessingSpec",
    "MediaKind",
    "MediaMetadata",
    "MediaProcessingResult",
    "MediaProvenance",
    "PixelDimensions",
    "ThumbnailInfo",
    "VideoStreamInfo",
    "media_kind",
]
