"""Typed local media inspection for images, animations, video, and audio."""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from pyfetcher.media.models import (
    AudioStreamInfo,
    ImageInfo,
    MediaMetadata,
    MediaProvenance,
    PixelDimensions,
    VideoStreamInfo,
    media_kind,
)
from pyfetcher.streams import ByteStream


class MediaInspectionError(RuntimeError):
    """Raised when a recognized media type cannot be inspected."""


def _json(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json(item) for item in value]
    return str(value)


def _int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _duration_seconds(value: object) -> float | None:
    duration_ms = _float(value)
    return duration_ms / 1_000 if duration_ms is not None else None


def _dimensions(width: object, height: object) -> PixelDimensions | None:
    parsed_width = _int(width)
    parsed_height = _int(height)
    if not parsed_width or not parsed_height:
        return None
    return PixelDimensions(width=parsed_width, height=parsed_height)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _materialized(source: str | Path | ByteStream) -> Iterator[Path]:
    if isinstance(source, ByteStream):
        if source.path is not None:
            yield source.path
            return
        suffix = Path(source.info.name or "").suffix
        with tempfile.NamedTemporaryFile(
            prefix="fetchkit-media-", suffix=suffix, delete=False
        ) as temporary:
            path = Path(temporary.name)
            for chunk in source.iter_bytes():
                temporary.write(chunk)
        try:
            yield path
        finally:
            path.unlink(missing_ok=True)
        return
    yield Path(source)


def _inspect_image(
    path: Path,
    *,
    source_url: str | None,
    checksum: bool,
) -> MediaMetadata:
    try:
        from PIL import ExifTags, Image, ImageSequence
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise MediaInspectionError(
            "image, GIF, and WebP inspection requires `pip install 'fetchkit[media]'`"
        ) from exc

    try:
        with Image.open(path) as image:
            image_format = image.format
            mime_type = Image.MIME.get(image_format or "") or mimetypes.guess_type(path.name)[0]
            animated = bool(getattr(image, "is_animated", False))
            frame_count = int(getattr(image, "n_frames", 1) or 1)
            durations = tuple(
                max(0, int(frame.info.get("duration", image.info.get("duration", 0)) or 0))
                for frame in ImageSequence.Iterator(image)
            )
            exif: dict[str, JsonValue] = {}
            with suppress(AttributeError, TypeError, ValueError):
                exif = {
                    str(ExifTags.TAGS.get(tag, tag)): _json(value)
                    for tag, value in image.getexif().items()
                }
            image_metadata = {
                key: _json(value)
                for key, value in image.info.items()
                if key not in {"exif", "icc_profile"}
            }
            image_metadata["icc_profile_present"] = bool(image.info.get("icc_profile"))
            info = ImageInfo(
                format=image_format,
                dimensions=PixelDimensions(width=image.width, height=image.height),
                mode=image.mode,
                has_alpha="A" in image.getbands() or "transparency" in image.info,
                animated=animated,
                frame_count=frame_count,
                frame_durations_ms=durations if animated else (),
                total_duration_seconds=sum(durations) / 1_000 if animated else None,
                loop_count=_int(image.info.get("loop")) if animated else None,
                exif=exif,
                metadata=image_metadata,
            )
    except MediaInspectionError:
        raise
    except Exception as exc:
        raise MediaInspectionError(f"cannot inspect image {path}: {exc}") from exc

    extension = path.suffix.lower().lstrip(".") or None
    return MediaMetadata(
        kind=media_kind(mime_type=mime_type, extension=extension, animated=info.animated),
        source_url=source_url,
        path=str(path),
        filename=path.name,
        mime_type=mime_type,
        extension=extension,
        file_size_bytes=path.stat().st_size,
        checksum_sha256=_sha256(path) if checksum else None,
        duration_seconds=info.total_duration_seconds,
        image=info,
        provenance=MediaProvenance(extractor="pillow", source="file"),
    )


def _track_metadata(data: dict[str, Any], excluded: set[str]) -> dict[str, JsonValue]:
    return {
        str(key): _json(value)
        for key, value in data.items()
        if value is not None and key not in excluded
    }


def _inspect_av(
    path: Path,
    *,
    source_url: str | None,
    checksum: bool,
) -> MediaMetadata:
    try:
        from pymediainfo import MediaInfo as PyMediaInfo  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise MediaInspectionError(
            "video and audio inspection requires `pip install 'fetchkit[media]'`"
        ) from exc

    try:
        parsed = PyMediaInfo.parse(str(path))
    except Exception as exc:
        raise MediaInspectionError(f"cannot inspect audio/video {path}: {exc}") from exc

    general: dict[str, Any] = {}
    videos: list[VideoStreamInfo] = []
    audios: list[AudioStreamInfo] = []
    for position, track in enumerate(parsed.tracks):
        data = {key: value for key, value in track.to_data().items() if value is not None}
        kind = str(data.get("track_type", "")).lower()
        if kind == "general":
            general = data
        elif kind == "video":
            excluded = {
                "track_type",
                "track_id",
                "codec_id",
                "format",
                "format_profile",
                "width",
                "height",
                "frame_rate",
                "bit_rate",
                "bit_depth",
                "duration",
                "language",
                "color_space",
                "hdr_format",
            }
            videos.append(
                VideoStreamInfo(
                    index=_int(data.get("track_id")) or position,
                    codec=str(data.get("codec_id")) if data.get("codec_id") else None,
                    format=str(data.get("format")) if data.get("format") else None,
                    profile=(
                        str(data.get("format_profile")) if data.get("format_profile") else None
                    ),
                    dimensions=_dimensions(data.get("width"), data.get("height")),
                    frame_rate=_float(data.get("frame_rate")),
                    bit_rate=_int(data.get("bit_rate")),
                    bit_depth=_int(data.get("bit_depth")),
                    duration_seconds=_duration_seconds(data.get("duration")),
                    language=str(data.get("language")) if data.get("language") else None,
                    color_space=(str(data.get("color_space")) if data.get("color_space") else None),
                    hdr_format=str(data.get("hdr_format")) if data.get("hdr_format") else None,
                    metadata=_track_metadata(data, excluded),
                )
            )
        elif kind == "audio":
            excluded = {
                "track_type",
                "track_id",
                "codec_id",
                "format",
                "format_profile",
                "channel_s",
                "sampling_rate",
                "bit_rate",
                "bit_depth",
                "duration",
                "language",
            }
            audios.append(
                AudioStreamInfo(
                    index=_int(data.get("track_id")) or position,
                    codec=str(data.get("codec_id")) if data.get("codec_id") else None,
                    format=str(data.get("format")) if data.get("format") else None,
                    profile=(
                        str(data.get("format_profile")) if data.get("format_profile") else None
                    ),
                    channels=_int(data.get("channel_s")),
                    sample_rate_hz=_int(data.get("sampling_rate")),
                    bit_rate=_int(data.get("bit_rate")),
                    bit_depth=_int(data.get("bit_depth")),
                    duration_seconds=_duration_seconds(data.get("duration")),
                    language=str(data.get("language")) if data.get("language") else None,
                    metadata=_track_metadata(data, excluded),
                )
            )

    extension = path.suffix.lower().lstrip(".") or None
    mime_type = mimetypes.guess_type(path.name)[0]
    kind = (
        "video"
        if videos
        else "audio"
        if audios
        else media_kind(
            mime_type=mime_type,
            extension=extension,
        )
    )
    duration = _duration_seconds(general.get("duration"))
    if duration is None:
        duration = next(
            (
                value.duration_seconds
                for value in [*videos, *audios]
                if value.duration_seconds is not None
            ),
            None,
        )
    general_excluded = {
        "track_type",
        "format",
        "codec_id",
        "duration",
        "overall_bit_rate",
        "file_size",
        "file_name",
        "file_extension",
    }
    return MediaMetadata(
        kind=kind,
        source_url=source_url,
        path=str(path),
        filename=path.name,
        mime_type=mime_type,
        extension=extension,
        file_size_bytes=_int(general.get("file_size")) or path.stat().st_size,
        checksum_sha256=_sha256(path) if checksum else None,
        duration_seconds=duration,
        bit_rate=_int(general.get("overall_bit_rate")),
        container=str(general.get("format")) if general.get("format") else None,
        video_streams=tuple(videos),
        audio_streams=tuple(audios),
        provenance=MediaProvenance(extractor="pymediainfo", source="file"),
        extra=_track_metadata(general, general_excluded),
    )


def inspect_media(
    source: str | Path | ByteStream,
    *,
    mime_type: str | None = None,
    source_url: str | None = None,
    checksum: bool = False,
) -> MediaMetadata:
    """Inspect a path or synchronous byte stream into canonical metadata."""
    with _materialized(source) as path:
        if not path.is_file():
            raise FileNotFoundError(path)
        extension = path.suffix.lower().lstrip(".")
        resolved_mime = mime_type or mimetypes.guess_type(path.name)[0]
        kind = media_kind(mime_type=resolved_mime, extension=extension)
        if kind in {"image", "animation"}:
            return _inspect_image(path, source_url=source_url, checksum=checksum)
        if kind in {"video", "audio"}:
            return _inspect_av(path, source_url=source_url, checksum=checksum)
        return MediaMetadata.from_path_hints(
            path,
            mime_type=resolved_mime,
            source_url=source_url,
            checksum_sha256=_sha256(path) if checksum else None,
            provenance=MediaProvenance(extractor="file_hints", source="file"),
        )


async def ainspect_media(
    source: str | Path | ByteStream,
    *,
    mime_type: str | None = None,
    source_url: str | None = None,
    checksum: bool = False,
) -> MediaMetadata:
    """Inspect media off the event loop when the source is path/sync-backed."""
    if isinstance(source, ByteStream) and source.path is None and not source.supports_sync:
        suffix = Path(source.info.name or "").suffix
        with tempfile.NamedTemporaryFile(
            prefix="fetchkit-media-",
            suffix=suffix,
            delete=False,
        ) as temporary:
            path = Path(temporary.name)
            async for chunk in source.aiter_bytes():
                await asyncio.to_thread(temporary.write, chunk)
        try:
            return await asyncio.to_thread(
                inspect_media,
                path,
                mime_type=mime_type or source.info.media_type,
                source_url=source_url,
                checksum=checksum,
            )
        finally:
            path.unlink(missing_ok=True)
    return await asyncio.to_thread(
        inspect_media,
        source,
        mime_type=mime_type,
        source_url=source_url,
        checksum=checksum,
    )


__all__ = ["MediaInspectionError", "ainspect_media", "inspect_media"]
