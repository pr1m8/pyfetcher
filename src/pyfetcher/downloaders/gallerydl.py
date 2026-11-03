"""gallery-dl deep integration for :mod:`pyfetcher.downloaders`.

Purpose:
    Wrap gallery-dl's job/config API for programmatic downloading with
    metadata capture and file interception.
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyfetcher.downloaders.base import DownloadProgress, DownloadResult, MediaInfo
from pyfetcher.media import MediaMetadata, media_kind

_GALLERY_DL_CONFIG_LOCK = threading.Lock()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class GalleryDlDownloader:
    """Deep gallery-dl integration via its Python API.

    Uses gallery-dl's configuration system and job runner to download
    images and galleries, capturing per-file metadata.

    Args:
        extra_config: Additional gallery-dl configuration dict.
    """

    def __init__(self, *, extra_config: dict[str, Any] | None = None) -> None:
        self._extra_config = extra_config or {}

    def _apply_config(self, config_module: Any) -> None:
        """Apply provider-native top-level gallery-dl configuration."""
        config_module.clear()
        for key, value in self._extra_config.items():
            config_module.set((), key, value)

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

            items: list[dict] = []

            class CollectorJob(DataJob):
                def run(self):
                    for msg in self.extractor.items():
                        if msg[0] == 1:  # Message.Url
                            _, url_str, kwdict = msg
                            items.append({"url": url_str, **kwdict})

            with _GALLERY_DL_CONFIG_LOCK:
                self._apply_config(gdl_config)
                job = CollectorJob(url)
                job.run()
            return items

        raw_items = await asyncio.to_thread(_extract)
        results: list[MediaInfo] = []
        for item in raw_items:
            extension = item.get("extension")
            mime_type = mimetypes.guess_type(f"item.{extension}")[0] if extension else None
            results.append(
                MediaInfo(
                    url=item.get("url", ""),
                    title=item.get("description") or item.get("title"),
                    ext=extension,
                    file_size_bytes=item.get("filesize"),
                    mime_type=mime_type,
                    kind=media_kind(mime_type=mime_type, extension=extension),
                    width=item.get("width"),
                    height=item.get("height"),
                    provider="gallery_dl",
                    extractor=item.get("category") or item.get("subcategory"),
                    extra={
                        key: value
                        for key, value in item.items()
                        if key != "url" and value is not None
                    },
                )
            )
        return results

    async def extract_metadata(self, url: str) -> list[MediaMetadata]:
        """Extract canonical gallery item metadata without downloading."""
        return [item.to_metadata() for item in await self.extract_info(url)]

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

            with _GALLERY_DL_CONFIG_LOCK:
                self._apply_config(gdl_config)
                gdl_config.set((), "base-directory", output_dir)
                gdl_config.set((), "directory", [])

                gallery_dl.main([url])

                # Collect all downloaded files while the global configuration is stable.
                return [str(p) for p in Path(output_dir).rglob("*") if p.is_file()]

        downloaded_files = await asyncio.to_thread(_download)

        results = []
        for filepath in downloaded_files:
            fp = Path(filepath)
            file_size = fp.stat().st_size
            sha256 = _sha256(fp)
            mime_type = mimetypes.guess_type(fp.name)[0]
            metadata = (
                MediaInfo(
                    url=url,
                    file_size_bytes=file_size,
                    mime_type=mime_type,
                    ext=fp.suffix.lstrip(".") or None,
                    provider="gallery_dl",
                    extractor="download",
                )
                .to_metadata()
                .model_copy(
                    update={
                        "path": filepath,
                        "filename": fp.name,
                        "checksum_sha256": sha256,
                    }
                )
            )
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
                    mime_type=mime_type,
                    checksum_sha256=sha256,
                    normalized_metadata=metadata,
                )
            )
        return results
