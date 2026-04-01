"""Direct HTTP download with MinIO upload for :mod:`pyfetcher.downloaders`.

Purpose:
    Provide direct HTTP file downloads using pyfetcher's existing fetch
    infrastructure, with optional streaming to MinIO.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.downloaders.base import DownloadResult, MediaInfo
from pyfetcher.fetch.service import FetchService


class DirectDownloader:
    """Direct HTTP downloader using pyfetcher's FetchService.

    Streams files to disk using the existing streaming infrastructure,
    then optionally uploads to MinIO.

    Args:
        fetch_service: Optional FetchService instance.
    """

    def __init__(self, *, fetch_service: FetchService | None = None) -> None:
        self._service = fetch_service or FetchService()

    async def extract_info(self, url: str) -> list[MediaInfo]:
        """Extract info via HEAD request.

        Args:
            url: File URL.

        Returns:
            A list with one :class:`MediaInfo`.
        """
        request = FetchRequest(url=url, method="HEAD")
        response = await self._service.afetch(request)
        filename = url.rsplit("/", 1)[-1] if "/" in url else None
        return [
            MediaInfo(
                url=url,
                mime_type=response.content_type,
                file_size_bytes=int(response.headers.get("content-length", 0)) or None,
                ext=Path(filename).suffix if filename else None,
            )
        ]

    async def download(
        self,
        url: str,
        *,
        output_dir: str | None = None,
        progress_callback: object | None = None,
    ) -> list[DownloadResult]:
        """Download a file via HTTP streaming.

        Args:
            url: File URL.
            output_dir: Output directory. Uses temp dir if not provided.
            progress_callback: Not used for direct downloads.

        Returns:
            A list with one :class:`DownloadResult`.
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="pyfetcher-direct-")

        filename = url.rsplit("/", 1)[-1] if "/" in url else "download"
        dest = Path(output_dir) / filename
        dest.parent.mkdir(parents=True, exist_ok=True)

        request = FetchRequest(url=url)
        hasher = hashlib.sha256()
        total_bytes = 0

        with dest.open("wb") as f:
            async for chunk in self._service.astream(request):
                f.write(chunk.data)
                hasher.update(chunk.data)
                total_bytes += len(chunk.data)

        return [
            DownloadResult(
                source_url=url,
                local_path=str(dest),
                filename=filename,
                file_size_bytes=total_bytes,
                checksum_sha256=hasher.hexdigest(),
            )
        ]
