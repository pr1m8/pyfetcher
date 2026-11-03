"""Pillow-backed image, GIF, WebP, and thumbnail processing."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pyfetcher.media.inspect import MediaInspectionError, inspect_media
from pyfetcher.media.models import (
    ImageProcessingSpec,
    MediaProcessingResult,
    PixelDimensions,
    ThumbnailInfo,
)
from pyfetcher.streams import ByteStream


@contextmanager
def _source_path(source: str | Path | ByteStream):
    if isinstance(source, ByteStream):
        if source.path is not None:
            yield source.path
            return
        suffix = Path(source.info.name or "").suffix
        with tempfile.NamedTemporaryFile(
            prefix="fetchkit-image-",
            suffix=suffix,
            delete=False,
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


def _target_size(width: int, height: int, spec: ImageProcessingSpec) -> tuple[int, int]:
    if spec.width is None and spec.height is None:
        return width, height
    if spec.width is None:
        assert spec.height is not None
        return max(1, round(width * spec.height / height)), spec.height
    if spec.height is None:
        return spec.width, max(1, round(height * spec.width / width))
    return spec.width, spec.height


def _resize(frame: Any, spec: ImageProcessingSpec, image_ops: Any, resampling: Any):
    target = _target_size(frame.width, frame.height, spec)
    if target == frame.size:
        return frame.copy()
    if spec.fit == "cover" and spec.width is not None and spec.height is not None:
        return image_ops.fit(frame, target, method=resampling.LANCZOS)
    if spec.fit == "stretch":
        return frame.resize(target, resampling.LANCZOS)
    return image_ops.contain(frame, target, method=resampling.LANCZOS)


def _format(destination: Path, requested: str | None, source_format: str | None) -> str:
    value = requested or destination.suffix.lstrip(".") or source_format
    if not value:
        raise ValueError("output_format or destination extension is required")
    normalized = value.upper()
    return "JPEG" if normalized in {"JPG", "JPE"} else normalized


def process_image(
    source: str | Path | ByteStream,
    destination: str | Path,
    spec: ImageProcessingSpec | None = None,
) -> MediaProcessingResult:
    """Resize or convert an image atomically, preserving animation on request."""
    resolved_spec = spec or ImageProcessingSpec()
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageOps, ImageSequence
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise MediaInspectionError(
            "image processing requires `pip install 'fetchkit[media]'`"
        ) from exc

    partial: Path | None = None
    with _source_path(source) as input_path:
        try:
            with (
                Image.open(input_path) as image,
                tempfile.NamedTemporaryFile(
                    dir=output.parent,
                    prefix=f".{output.name}.",
                    suffix=".part",
                    delete=False,
                ) as temporary,
            ):
                partial = Path(temporary.name)
                output_format = _format(output, resolved_spec.output_format, image.format)
                animated = bool(getattr(image, "is_animated", False))
                keep_animation = (
                    animated
                    and resolved_spec.preserve_animation
                    and output_format in {"GIF", "WEBP"}
                )
                frames = [
                    _resize(frame.convert("RGBA"), resolved_spec, ImageOps, Image.Resampling)
                    for frame in ImageSequence.Iterator(image)
                    if keep_animation
                ]
                if not frames:
                    image.seek(0)
                    frames = [
                        _resize(image.convert("RGBA"), resolved_spec, ImageOps, Image.Resampling)
                    ]
                if output_format == "JPEG":
                    frames = [frame.convert("RGB") for frame in frames]

                save_options: dict[str, object] = {}
                if output_format in {"JPEG", "WEBP"}:
                    save_options["quality"] = resolved_spec.quality
                    save_options["optimize"] = True
                if not resolved_spec.strip_metadata:
                    for key in ("exif", "icc_profile"):
                        if image.info.get(key):
                            save_options[key] = image.info[key]
                if keep_animation:
                    durations = [
                        int(frame.info.get("duration", image.info.get("duration", 0)) or 0)
                        for frame in ImageSequence.Iterator(image)
                    ]
                    save_options.update(
                        {
                            "save_all": True,
                            "append_images": frames[1:],
                            "duration": durations,
                            "loop": int(image.info.get("loop", 0) or 0),
                        }
                    )
                frames[0].save(temporary, format=output_format, **save_options)
            partial.replace(output)
            partial = None
        except BaseException:
            if partial is not None:
                partial.unlink(missing_ok=True)
            raise

    metadata = inspect_media(output, checksum=True)
    return MediaProcessingResult(
        operation="image.process",
        source_path=(
            str(source.path or source.info.name or "<stream>")
            if isinstance(source, ByteStream)
            else str(source)
        ),
        output_path=str(output),
        metadata=metadata,
    )


def generate_thumbnail(
    source: str | Path | ByteStream,
    destination: str | Path,
    *,
    width: int,
    height: int,
    fit: Literal["contain", "cover", "stretch"] = "cover",
    output_format: str | None = None,
    quality: int = 85,
    preserve_animation: bool = False,
) -> MediaProcessingResult:
    """Generate a bounded thumbnail and attach standardized thumbnail metadata."""
    result = process_image(
        source,
        destination,
        ImageProcessingSpec(
            width=width,
            height=height,
            fit=fit,
            output_format=output_format,
            quality=quality,
            preserve_animation=preserve_animation,
        ),
    )
    dimensions = result.metadata.dimensions or PixelDimensions(width=width, height=height)
    thumbnail = ThumbnailInfo(
        path=result.output_path,
        dimensions=dimensions,
        mime_type=result.metadata.mime_type,
        extension=result.metadata.extension,
        file_size_bytes=result.metadata.file_size_bytes,
        generated=True,
    )
    return result.model_copy(update={"operation": "image.thumbnail", "thumbnail": thumbnail})


__all__ = ["generate_thumbnail", "process_image"]
