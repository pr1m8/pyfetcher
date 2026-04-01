"""Media file metadata extraction for :mod:`pyfetcher.extractors`.

Purpose:
    Extract metadata from media files: audio (mutagen), video (pymediainfo),
    images (exifread), and PDFs (pypdf). Returns a unified dict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_media_metadata(file_path: str | Path) -> dict[str, Any]:
    """Extract metadata from a media file based on its type.

    Dispatches to the appropriate library based on file extension.

    Args:
        file_path: Path to the media file.

    Returns:
        A dictionary of extracted metadata.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in {".mp3", ".flac", ".ogg", ".m4a", ".wma", ".wav", ".aac"}:
        return _extract_audio(path)
    elif ext in {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}:
        return _extract_video(path)
    elif ext in {".jpg", ".jpeg", ".png", ".gif", ".tiff", ".bmp", ".webp"}:
        return _extract_image(path)
    elif ext == ".pdf":
        return _extract_pdf(path)
    return {"type": "unknown", "extension": ext}


def _extract_audio(path: Path) -> dict[str, Any]:
    """Extract audio metadata with mutagen."""
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
            info["tags"] = {str(k): str(v) for k, v in audio.tags.items()}
        return info
    except Exception as e:
        return {"type": "audio", "error": str(e)}


def _extract_video(path: Path) -> dict[str, Any]:
    """Extract video metadata with pymediainfo."""
    try:
        from pymediainfo import MediaInfo  # type: ignore[import-untyped]

        mi = MediaInfo.parse(str(path))
        info: dict[str, Any] = {"type": "video", "tracks": []}
        for track in mi.tracks:
            info["tracks"].append({k: v for k, v in track.to_data().items() if v is not None})
        return info
    except Exception as e:
        return {"type": "video", "error": str(e)}


def _extract_image(path: Path) -> dict[str, Any]:
    """Extract image EXIF metadata with exifread."""
    try:
        import exifread  # type: ignore[import-untyped]

        with path.open("rb") as f:
            tags = exifread.process_file(f, details=False)
        return {"type": "image", "exif": {str(k): str(v) for k, v in tags.items()}}
    except Exception as e:
        return {"type": "image", "error": str(e)}


def _extract_pdf(path: Path) -> dict[str, Any]:
    """Extract PDF metadata with pypdf."""
    try:
        from pypdf import PdfReader  # type: ignore[import-untyped]

        reader = PdfReader(str(path))
        meta = reader.metadata
        info: dict[str, Any] = {
            "type": "pdf",
            "pages": len(reader.pages),
        }
        if meta:
            info["title"] = meta.get("/Title")
            info["author"] = meta.get("/Author")
            info["subject"] = meta.get("/Subject")
            info["creator"] = meta.get("/Creator")
        return info
    except Exception as e:
        return {"type": "pdf", "error": str(e)}
