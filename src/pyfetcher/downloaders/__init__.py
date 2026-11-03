"""Deep downloader integrations for :mod:`pyfetcher`.

Purpose:
    Provide Python API wrappers for yt-dlp and gallery-dl with progress
    tracking, metadata extraction, and MinIO upload support.
"""

from __future__ import annotations

from pyfetcher.downloaders.base import (
    DownloaderItems,
    DownloaderProtocol,
    DownloaderResult,
    DownloadProgress,
    DownloadResult,
    MediaInfo,
    MetadataDownloaderProtocol,
    ProgressCallback,
)
from pyfetcher.downloaders.direct import DirectDownloader
from pyfetcher.downloaders.gallerydl import GalleryDlDownloader
from pyfetcher.downloaders.ytdlp import YtdlpDownloader

__all__ = [
    "DirectDownloader",
    "DownloadProgress",
    "DownloadResult",
    "DownloaderProtocol",
    "DownloaderItems",
    "DownloaderResult",
    "GalleryDlDownloader",
    "MediaInfo",
    "MetadataDownloaderProtocol",
    "ProgressCallback",
    "YtdlpDownloader",
]
