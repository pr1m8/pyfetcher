"""Download service for :mod:`pyfetcher`.

Purpose:
    Provide file-oriented download helpers that reuse the shared fetch service
    and streaming models.

Design:
    - Downloads are async-first using streamed chunks.
    - Files are written incrementally to avoid holding entire responses in memory.
    - Parent directories are created automatically.

Examples:
    ::

        >>> service = DownloadService()
        >>> hasattr(service, "adownload_to_path")
        True
"""

from __future__ import annotations

from pathlib import Path

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.fetch.service import FetchService


class DownloadService:
    """Async download service built on streamed fetches.

    Wraps a :class:`~pyfetcher.fetch.service.FetchService` to provide
    file-oriented download capabilities. Files are streamed incrementally
    to disk to minimize memory usage for large downloads.

    Args:
        fetch_service: Optional fetch service instance. A default is created
            if not provided.

    Examples:
        ::

            >>> service = DownloadService()
            >>> hasattr(service, "adownload_to_path")
            True
    """

    def __init__(self, *, fetch_service: FetchService | None = None) -> None:
        self.fetch_service = fetch_service or FetchService()

    async def adownload_to_path(self, request: FetchRequest, destination: str | Path) -> Path:
        """Download a resource to a destination file path.

        Streams the response body in chunks and writes each chunk to disk
        as it arrives. Parent directories are created automatically.

        Args:
            request: The fetch request for the resource to download.
            destination: Target file path (string or ``Path``).

        Returns:
            The resolved :class:`Path` where the file was written.

        Raises:
            Exception: Any streaming or file I/O failure.

        Examples:
            ::

                >>> service = DownloadService()
                >>> hasattr(service, "adownload_to_path")
                True
        """
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with destination_path.open("wb") as handle:
            async for chunk in self.fetch_service.astream(request):
                handle.write(chunk.data)

        return destination_path
