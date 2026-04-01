"""yt-dlp deep integration for :mod:`pyfetcher.downloaders`.

Purpose:
    Wrap yt-dlp's YoutubeDL Python API with progress hooks, metadata
    extraction, and structured output for pipeline integration.
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyfetcher.downloaders.base import DownloadProgress, DownloadResult, MediaInfo


class YtdlpDownloader:
    """Deep yt-dlp integration via the YoutubeDL Python API.

    Hooks into progress_hooks for real-time download tracking and
    converts info_dict to structured MediaInfo/DownloadResult models.

    Args:
        format_spec: yt-dlp format selection string.
        extra_opts: Additional yt-dlp options dict.
    """

    def __init__(
        self,
        *,
        format_spec: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
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
                progress_callback(
                    DownloadProgress(
                        status=d.get("status", "unknown"),
                        downloaded_bytes=d.get("downloaded_bytes", 0),
                        total_bytes=d.get("total_bytes") or d.get("total_bytes_estimate"),
                        speed_bytes_per_sec=d.get("speed"),
                        eta_seconds=d.get("eta"),
                        filename=d.get("filename"),
                        percent=d.get("_percent_str"),
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

            with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": False}) as ydl:
                return ydl.extract_info(url, download=False) or {}

        info = await asyncio.to_thread(_extract)
        return self._info_to_media_list(info)

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
                    ext=entry.get("ext"),
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
        Path(output_dir)
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
                sha256 = hashlib.sha256(fp.read_bytes()).hexdigest() if fp.exists() else None
            else:
                file_size = None
                sha256 = None
            media_info_list = self._info_to_media_list({"entries": [entry]})
            results.append(
                DownloadResult(
                    source_url=entry.get("webpage_url") or entry.get("url", ""),
                    local_path=filepath,
                    filename=Path(filepath).name if filepath else None,
                    file_size_bytes=file_size,
                    checksum_sha256=sha256,
                    media_info=media_info_list[0] if media_info_list else None,
                )
            )
        return results
