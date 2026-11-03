"""Direct HTTP download with MinIO upload for :mod:`pyfetcher.downloaders`.

Purpose:
    Provide direct HTTP file downloads using pyfetcher's existing fetch
    infrastructure, with optional streaming to MinIO.
"""

from __future__ import annotations

import hashlib
import mimetypes
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.downloaders.base import DownloadProgress, DownloadResult, MediaInfo
from pyfetcher.fetch.service import FetchService
from pyfetcher.media import MediaMetadata


class DirectDownloader:
    """Direct HTTP downloader using pyfetcher's FetchService.

    Streams files to disk using the existing streaming infrastructure,
    then optionally uploads to MinIO.

    Args:
        fetch_service: Optional FetchService instance.
        headers: Headers shared by metadata and download requests.
        cookies: Cookies encoded into the shared Cookie header.
        proxy: Optional HTTP(S) proxy URL.
        backend: FetchService transport name.
        request_options: Additional FetchRequest policy fields.
    """

    def __init__(
        self,
        *,
        fetch_service: FetchService | None = None,
        headers: Mapping[str, str] | None = None,
        cookies: Mapping[str, str] | None = None,
        proxy: str | None = None,
        backend: str = "httpx",
        request_options: Mapping[str, Any] | None = None,
    ) -> None:
        self._service = fetch_service or FetchService()
        self._owns_service = fetch_service is None
        self._headers = dict(headers or {})
        if cookies:
            cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
            self._headers.setdefault("cookie", cookie_header)
        self._proxy = proxy
        self._backend = backend
        self._request_options = dict(request_options or {})

    def _request(self, url: str, *, method: str = "GET") -> FetchRequest:
        return FetchRequest(
            url=url,
            method=method,
            headers=self._headers,
            proxy=self._proxy,
            backend=self._backend,
            **self._request_options,
        )

    async def extract_info(self, url: str) -> list[MediaInfo]:
        """Extract info via HEAD request.

        Args:
            url: File URL.

        Returns:
            A list with one :class:`MediaInfo`.
        """
        request = self._request(url, method="HEAD")
        response = await self._service.afetch(request)
        filename = unquote(Path(urlsplit(url).path).name) or None
        mime_type = response.content_type or mimetypes.guess_type(filename or url)[0]
        return [
            MediaInfo(
                url=url,
                mime_type=mime_type,
                file_size_bytes=int(response.headers.get("content-length", 0)) or None,
                ext=Path(filename).suffix if filename else None,
                provider="direct",
                extractor="http_head",
            )
        ]

    async def extract_metadata(self, url: str) -> list[MediaMetadata]:
        """Extract canonical direct-download metadata without downloading."""
        return [item.to_metadata() for item in await self.extract_info(url)]

    async def download(
        self,
        url: str,
        *,
        output_dir: str | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        filename: str | None = None,
        overwrite: bool = True,
    ) -> list[DownloadResult]:
        """Download a file via HTTP streaming.

        Args:
            url: File URL.
            output_dir: Output directory. Uses temp dir if not provided.
            progress_callback: Optional callback invoked for chunks and completion.
            filename: Optional safe path relative to ``output_dir``.
            overwrite: Whether an existing destination may be atomically replaced.

        Returns:
            A list with one :class:`DownloadResult`.
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="pyfetcher-direct-")

        filename = filename or unquote(Path(urlsplit(url).path).name) or "download"
        relative_path = Path(filename)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("filename must be a relative path without parent traversal")
        dest = Path(output_dir) / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not overwrite:
            raise FileExistsError(f"download destination already exists: {dest}")

        request = self._request(url)
        hasher = hashlib.sha256()
        total_bytes = 0

        partial_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=dest.parent,
                prefix=f".{dest.name}.",
                suffix=".part",
                delete=False,
            ) as partial:
                partial_path = Path(partial.name)
                async for chunk in self._service.astream(request):
                    partial.write(chunk.data)
                    hasher.update(chunk.data)
                    total_bytes += len(chunk.data)
                    if progress_callback:
                        progress_callback(
                            DownloadProgress(
                                status="downloading",
                                downloaded_bytes=total_bytes,
                                filename=dest.name,
                            )
                        )
            if dest.exists() and not overwrite:
                raise FileExistsError(f"download destination already exists: {dest}")
            partial_path.replace(dest)
        except BaseException:
            if partial_path is not None:
                partial_path.unlink(missing_ok=True)
            raise

        if progress_callback:
            progress_callback(
                DownloadProgress(
                    status="finished",
                    downloaded_bytes=total_bytes,
                    total_bytes=total_bytes,
                    filename=dest.name,
                    percent=100.0,
                )
            )

        mime_type = mimetypes.guess_type(dest.name)[0]
        metadata = (
            MediaInfo(
                url=url,
                file_size_bytes=total_bytes,
                mime_type=mime_type,
                ext=dest.suffix.lstrip(".") or None,
                provider="direct",
                extractor="http_stream",
            )
            .to_metadata()
            .model_copy(
                update={
                    "path": str(dest),
                    "filename": dest.name,
                    "checksum_sha256": hasher.hexdigest(),
                }
            )
        )
        return [
            DownloadResult(
                source_url=url,
                local_path=str(dest),
                filename=dest.name,
                file_size_bytes=total_bytes,
                mime_type=mime_type,
                checksum_sha256=hasher.hexdigest(),
                normalized_metadata=metadata,
            )
        ]

    async def aclose(self) -> None:
        """Close an internally owned fetch service."""
        if self._owns_service:
            await self._service.aclose()
