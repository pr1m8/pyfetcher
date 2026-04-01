"""gallery-dl deep integration for :mod:`pyfetcher.downloaders`.

Purpose:
    Wrap gallery-dl's job/config API for programmatic downloading with
    metadata capture and file interception.
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyfetcher.downloaders.base import DownloadProgress, DownloadResult, MediaInfo


class GalleryDlDownloader:
    """Deep gallery-dl integration via its Python API.

    Uses gallery-dl's configuration system and job runner to download
    images and galleries, capturing per-file metadata.

    Args:
        extra_config: Additional gallery-dl configuration dict.
    """

    def __init__(self, *, extra_config: dict[str, Any] | None = None) -> None:
        self._extra_config = extra_config or {}

    async def extract_info(self, url: str) -> list[MediaInfo]:
        """Extract metadata for all downloadable items without downloading.

        Args:
            url: Gallery or image URL.

        Returns:
            A list of :class:`MediaInfo` objects.
        """

        def _extract() -> list[dict]:
            from gallery_dl import config as gdl_config  # type: ignore[import-untyped]
            from gallery_dl.job import DataJob  # type: ignore[import-untyped]

            gdl_config.clear()
            gdl_config.set((), "extractor", self._extra_config.get("extractor", {}))

            items: list[dict] = []

            class CollectorJob(DataJob):
                def run(self):
                    for msg in self.extractor.items():
                        if msg[0] == 1:  # Message.Url
                            _, url_str, kwdict = msg
                            items.append({"url": url_str, **kwdict})

            try:
                job = CollectorJob(url)
                job.run()
            except Exception:
                pass
            return items

        raw_items = await asyncio.to_thread(_extract)
        return [
            MediaInfo(
                url=item.get("url", ""),
                title=item.get("description") or item.get("title"),
                ext=item.get("extension"),
                file_size_bytes=item.get("filesize"),
                extra={k: v for k, v in item.items() if k not in ("url",) and v is not None},
            )
            for item in raw_items
        ]

    async def download(
        self,
        url: str,
        *,
        output_dir: str | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> list[DownloadResult]:
        """Download all items from a URL.

        Args:
            url: Gallery or image URL.
            output_dir: Directory for downloaded files. Uses temp dir if not provided.
            progress_callback: Optional callback for progress updates.

        Returns:
            A list of :class:`DownloadResult` objects.
        """
        tmp = None
        if output_dir is None:
            tmp = tempfile.mkdtemp(prefix="pyfetcher-gallerydl-")
            output_dir = tmp

        def _download() -> list[str]:
            import gallery_dl  # type: ignore[import-untyped]
            from gallery_dl import config as gdl_config  # type: ignore[import-untyped]

            gdl_config.clear()
            gdl_config.set((), "base-directory", output_dir)
            gdl_config.set((), "directory", [])
            if self._extra_config:
                for key, val in self._extra_config.items():
                    gdl_config.set((), key, val)

            gallery_dl.main([url])

            # Collect all downloaded files
            return [str(p) for p in Path(output_dir).rglob("*") if p.is_file()]

        downloaded_files = await asyncio.to_thread(_download)

        results = []
        for filepath in downloaded_files:
            fp = Path(filepath)
            file_size = fp.stat().st_size
            sha256 = hashlib.sha256(fp.read_bytes()).hexdigest()
            if progress_callback:
                progress_callback(
                    DownloadProgress(
                        status="finished",
                        downloaded_bytes=file_size,
                        total_bytes=file_size,
                        filename=fp.name,
                    )
                )
            results.append(
                DownloadResult(
                    source_url=url,
                    local_path=filepath,
                    filename=fp.name,
                    file_size_bytes=file_size,
                    checksum_sha256=sha256,
                )
            )
        return results
