"""Media-file metadata extraction with typed and legacy result surfaces.

``inspect_media`` and ``ainspect_media`` return canonical Pydantic metadata.
``extract_media_metadata`` preserves the original dictionary API and optional
provider-specific dispatch behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyfetcher.media import ainspect_media, inspect_media


def extract_media_metadata(file_path: str | Path) -> dict[str, Any]:
    """Extract legacy dictionary metadata based on the file extension."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in {".mp3", ".flac", ".ogg", ".m4a", ".wma", ".wav", ".aac"}:
        return _extract_audio(path)
    if ext in {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}:
        return _extract_video(path)
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".tiff", ".bmp", ".webp"}:
        return _extract_image(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    return {"type": "unknown", "extension": ext}


def _extract_audio(path: Path) -> dict[str, Any]:
    """Extract legacy audio metadata with mutagen."""
    try:
        import mutagen  # type: ignore[import-untyped]

        audio = mutagen.File(str(path))
        if audio is None:
            return {"type": "audio", "error": "unrecognized format"}
        info: dict[str, Any] = {"type": "audio"}
        if hasattr(audio, "info"):
            info["length_seconds"] = getattr(audio.info, "length", None)
            info["bitrate"] = getattr(audio.info, "bitrate", None)
            info["sample_rate"] = getattr(audio.info, "sample_rate", None)
            info["channels"] = getattr(audio.info, "channels", None)
        if hasattr(audio, "tags") and audio.tags:
            info["tags"] = {str(key): str(value) for key, value in audio.tags.items()}
        return info
    except Exception as exc:
        return {"type": "audio", "error": str(exc)}


def _extract_video(path: Path) -> dict[str, Any]:
    """Extract legacy video metadata with pymediainfo."""
    try:
        from pymediainfo import MediaInfo  # type: ignore[import-untyped]

        media = MediaInfo.parse(str(path))
        return {
            "type": "video",
            "tracks": [
                {key: value for key, value in track.to_data().items() if value is not None}
                for track in media.tracks
            ],
        }
    except Exception as exc:
        return {"type": "video", "error": str(exc)}


def _extract_image(path: Path) -> dict[str, Any]:
    """Extract legacy image EXIF metadata with exifread."""
    try:
        import exifread  # type: ignore[import-untyped]

        with path.open("rb") as handle:
            tags = exifread.process_file(handle, details=False)
        return {
            "type": "image",
            "exif": {str(key): str(value) for key, value in tags.items()},
        }
    except Exception as exc:
        return {"type": "image", "error": str(exc)}


def _extract_pdf(path: Path) -> dict[str, Any]:
    """Extract legacy PDF metadata with pypdf."""
    try:
        from pypdf import PdfReader  # type: ignore[import-untyped]

        reader = PdfReader(str(path))
        metadata = reader.metadata
        info: dict[str, Any] = {"type": "pdf", "pages": len(reader.pages)}
        if metadata:
            info["title"] = metadata.get("/Title")
            info["author"] = metadata.get("/Author")
            info["subject"] = metadata.get("/Subject")
            info["creator"] = metadata.get("/Creator")
        return info
    except Exception as exc:
        return {"type": "pdf", "error": str(exc)}


__all__ = ["ainspect_media", "extract_media_metadata", "inspect_media"]
