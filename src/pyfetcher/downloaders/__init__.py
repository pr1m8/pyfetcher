"""Deep downloader integrations for :mod:`pyfetcher`.

Purpose:
    Provide Python API wrappers for yt-dlp and gallery-dl with progress
    tracking, metadata extraction, and MinIO upload support.
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from pyfetcher.downloaders.ytdlp import YtdlpDownloader  # noqa: F401
except Exception:  # pragma: no cover  # nosec B110
    pass
else:
    __all__.append("YtdlpDownloader")

try:
    from pyfetcher.downloaders.gallerydl import GalleryDlDownloader  # noqa: F401
except Exception:  # pragma: no cover  # nosec B110
    pass
else:
    __all__.append("GalleryDlDownloader")
