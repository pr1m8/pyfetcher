"""yt-dlp deep integration for :mod:`pyfetcher.downloaders`.

Purpose:
    Wrap yt-dlp's YoutubeDL Python API with progress hooks, metadata
    extraction, and structured output for pipeline integration.
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyfetcher.downloaders.base import DownloadProgress, DownloadResult, MediaInfo
from pyfetcher.media import MediaMetadata, ThumbnailInfo, media_kind


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _thumbnail_info(value: dict[str, Any]) -> ThumbnailInfo | None:
    url = value.get("url")
    if not url:
        return None
    width = value.get("width")
    height = value.get("height")
    dimensions = None
    if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
        from pyfetcher.media import PixelDimensions

        dimensions = PixelDimensions(width=width, height=height)
    return ThumbnailInfo(
        id=str(value.get("id")) if value.get("id") is not None else None,
        url=str(url),
        dimensions=dimensions,
        extension=value.get("ext"),
        file_size_bytes=value.get("filesize") or value.get("filesize_approx"),
        preference=value.get("preference"),
    )


class YtdlpDownloader:
    """Deep yt-dlp integration via the YoutubeDL Python API.

    Hooks into progress_hooks for real-time download tracking and
    converts info_dict to structured MediaInfo/DownloadResult models.

    Args:
        format_spec: yt-dlp format selection string.
        extra_opts: Additional yt-dlp options dict.
    """

    DEFAULT_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    def __init__(
        self,
        *,
        format_spec: str = DEFAULT_FORMAT,
        extra_opts: dict[str, Any] | None = None,
    ) -> None:
        self._format = format_spec
        self._extra_opts = extra_opts or {}

    def _build_opts(
        self,
        output_dir: str,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> dict[str, Any]:
        """Build the yt-dlp options dict."""
        hooks = []
        if progress_callback:

            def _hook(d: dict) -> None:
                percent_value = d.get("_percent_str")
                if isinstance(percent_value, str):
                    try:
                        percent_value = float(percent_value.strip().rstrip("%"))
                    except ValueError:
                        percent_value = None
                progress_callback(
                    DownloadProgress(
                        status=d.get("status", "unknown"),
                        downloaded_bytes=d.get("downloaded_bytes", 0),
                        total_bytes=d.get("total_bytes") or d.get("total_bytes_estimate"),
                        speed_bytes_per_sec=d.get("speed"),
                        eta_seconds=d.get("eta"),
                        filename=d.get("filename"),
                        percent=percent_value,
                    )
                )

            hooks.append(_hook)

        opts: dict[str, Any] = {
            "format": self._format,
            "outtmpl": f"{output_dir}/%(title)s-%(id)s.%(ext)s",
            "progress_hooks": hooks,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "writethumbnail": False,
            **self._extra_opts,
        }
        return opts

    async def extract_info(self, url: str) -> list[MediaInfo]:
        """Extract metadata without downloading.

        Args:
            url: The URL to extract info from.

        Returns:
            A list of :class:`MediaInfo` objects (one per video/track).
        """

        def _extract() -> dict:
            from yt_dlp import YoutubeDL  # type: ignore[import-untyped]

            opts = self._build_opts(".")
            opts.update({"skip_download": True, "simulate": True})
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False) or {}

        info = await asyncio.to_thread(_extract)
        return self._info_to_media_list(info)

    async def extract_metadata(self, url: str) -> list[MediaMetadata]:
        """Extract canonical media and thumbnail metadata without downloading."""
        return [item.to_metadata() for item in await self.extract_info(url)]

    async def download(
        self,
        url: str,
        *,
        output_dir: str | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> list[DownloadResult]:
        """Download media via yt-dlp.

        Args:
            url: The URL to download from.
            output_dir: Directory for downloaded files. Uses temp dir if not provided.
            progress_callback: Optional callback for progress updates.

        Returns:
            A list of :class:`DownloadResult` objects.
        """
        tmp = None
        if output_dir is None:
            tmp = tempfile.mkdtemp(prefix="pyfetcher-ytdlp-")
            output_dir = tmp

        opts = self._build_opts(output_dir, progress_callback)

        def _download() -> dict:
            from yt_dlp import YoutubeDL  # type: ignore[import-untyped]

            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True) or {}

        info = await asyncio.to_thread(_download)
        return self._info_to_results(info, output_dir)

    def _info_to_media_list(self, info: dict) -> list[MediaInfo]:
        """Convert yt-dlp info_dict to MediaInfo list."""
        entries = info.get("entries", [info]) if "entries" in info else [info]
        results = []
        for entry in entries:
            if not entry:
                continue
            thumbnails = tuple(
                thumbnail
                for value in entry.get("thumbnails") or ()
                if isinstance(value, dict) and (thumbnail := _thumbnail_info(value)) is not None
            )
            if not thumbnails and entry.get("thumbnail"):
                thumbnails = (ThumbnailInfo(url=str(entry["thumbnail"])),)
            extension = entry.get("ext")
            mime_type = mimetypes.guess_type(f"item.{extension}")[0] if extension else None
            if entry.get("vcodec") == "none" and entry.get("acodec") != "none":
                kind = "audio"
            elif entry.get("vcodec") not in {None, "none"}:
                kind = "video"
            else:
                kind = media_kind(mime_type=mime_type, extension=extension)
            results.append(
                MediaInfo(
                    url=entry.get("webpage_url") or entry.get("url", ""),
                    title=entry.get("title"),
                    description=entry.get("description"),
                    duration_seconds=entry.get("duration"),
                    thumbnail_url=entry.get("thumbnail"),
                    uploader=entry.get("uploader"),
                    upload_date=entry.get("upload_date"),
                    file_size_bytes=entry.get("filesize") or entry.get("filesize_approx"),
                    mime_type=mime_type,
                    ext=entry.get("ext"),
                    kind=kind,
                    width=entry.get("width"),
                    height=entry.get("height"),
                    thumbnails=thumbnails,
                    provider="yt_dlp",
                    extractor=entry.get("extractor_key") or entry.get("extractor"),
                    extra={
                        k: v
                        for k, v in entry.items()
                        if k
                        in (
                            "id",
                            "view_count",
                            "like_count",
                            "categories",
                            "tags",
                            "format",
                            "format_id",
                            "extractor",
                            "extractor_key",
                            "webpage_url_domain",
                        )
                        and v is not None
                    },
                )
            )
        return results

    def _info_to_results(self, info: dict, output_dir: str) -> list[DownloadResult]:
        """Convert yt-dlp info_dict to DownloadResult list after download."""
        entries = info.get("entries", [info]) if "entries" in info else [info]
        results = []
        for entry in entries:
            if not entry:
                continue
            requested = entry.get("requested_downloads", [{}])
            filepath = None
            if requested:
                filepath = requested[0].get("filepath") or requested[0].get("filename")
            if filepath:
                fp = Path(filepath)
                file_size = fp.stat().st_size if fp.exists() else None
                sha256 = _sha256(fp) if fp.exists() else None
            else:
                file_size = None
                sha256 = None
            media_info_list = self._info_to_media_list({"entries": [entry]})
            normalized = media_info_list[0].to_metadata() if media_info_list else None
            if normalized is not None:
                normalized = normalized.model_copy(
                    update={
                        "path": filepath,
                        "filename": Path(filepath).name if filepath else None,
                        "file_size_bytes": file_size,
                        "checksum_sha256": sha256,
                    }
                )
            results.append(
                DownloadResult(
                    source_url=entry.get("webpage_url") or entry.get("url", ""),
                    local_path=filepath,
                    filename=Path(filepath).name if filepath else None,
                    file_size_bytes=file_size,
                    mime_type=(media_info_list[0].mime_type if media_info_list else None),
                    checksum_sha256=sha256,
                    media_info=media_info_list[0] if media_info_list else None,
                    normalized_metadata=normalized,
                )
            )
        return results
