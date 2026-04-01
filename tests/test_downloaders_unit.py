"""Unit tests for pyfetcher.downloaders.base and pyfetcher.downloaders.direct."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyfetcher.downloaders.base import (
    DownloadProgress,
    DownloadResult,
    MediaInfo,
)


# ---------------------------------------------------------------------------
# base.py dataclass tests
# ---------------------------------------------------------------------------
class TestMediaInfoDataclass:
    def test_media_info_defaults(self):
        info = MediaInfo(url="https://example.com/video.mp4")
        assert info.url == "https://example.com/video.mp4"
        assert info.title is None
        assert info.description is None
        assert info.duration_seconds is None
        assert info.thumbnail_url is None
        assert info.uploader is None
        assert info.upload_date is None
        assert info.file_size_bytes is None
        assert info.mime_type is None
        assert info.ext is None
        assert info.extra == {}

    def test_media_info_frozen(self):
        info = MediaInfo(url="https://example.com/video.mp4")
        with pytest.raises(AttributeError):
            info.url = "changed"

    def test_media_info_with_all_fields(self):
        info = MediaInfo(
            url="https://example.com/video.mp4",
            title="Test Video",
            description="A test",
            duration_seconds=120.0,
            thumbnail_url="https://example.com/thumb.jpg",
            uploader="user1",
            upload_date="2026-01-01",
            file_size_bytes=1024,
            mime_type="video/mp4",
            ext=".mp4",
            extra={"format": "720p"},
        )
        assert info.title == "Test Video"
        assert info.duration_seconds == 120.0
        assert info.extra["format"] == "720p"


class TestDownloadResultDataclass:
    def test_download_result_defaults(self):
        result = DownloadResult(source_url="https://example.com/file.zip")
        assert result.source_url == "https://example.com/file.zip"
        assert result.local_path is None
        assert result.minio_key is None
        assert result.minio_bucket is None
        assert result.filename is None
        assert result.file_size_bytes is None
        assert result.mime_type is None
        assert result.checksum_sha256 is None
        assert result.media_info is None
        assert result.media_metadata == {}

    def test_download_result_frozen(self):
        result = DownloadResult(source_url="https://example.com/file.zip")
        with pytest.raises(AttributeError):
            result.source_url = "changed"

    def test_download_result_with_media_info(self):
        info = MediaInfo(url="https://example.com/vid.mp4", mime_type="video/mp4")
        result = DownloadResult(
            source_url="https://example.com/vid.mp4",
            local_path="/tmp/vid.mp4",
            filename="vid.mp4",
            file_size_bytes=2048,
            checksum_sha256="abc123",
            media_info=info,
        )
        assert result.media_info is not None
        assert result.media_info.mime_type == "video/mp4"


class TestDownloadProgressDataclass:
    def test_download_progress_defaults(self):
        progress = DownloadProgress(status="downloading")
        assert progress.status == "downloading"
        assert progress.downloaded_bytes == 0
        assert progress.total_bytes is None
        assert progress.speed_bytes_per_sec is None
        assert progress.eta_seconds is None
        assert progress.filename is None
        assert progress.percent is None

    def test_download_progress_mutable(self):
        progress = DownloadProgress(status="downloading", downloaded_bytes=100)
        progress.downloaded_bytes = 200
        assert progress.downloaded_bytes == 200

    def test_download_progress_all_statuses(self):
        for status in ("downloading", "finished", "error", "postprocessing"):
            p = DownloadProgress(status=status)
            assert p.status == status


# ---------------------------------------------------------------------------
# direct.py tests
# ---------------------------------------------------------------------------
from pyfetcher.downloaders.direct import DirectDownloader


class TestDirectDownloaderExtractInfo:
    @pytest.mark.asyncio
    async def test_direct_downloader_extract_info(self):
        mock_response = MagicMock()
        mock_response.content_type = "application/pdf"
        mock_response.headers = {"content-length": "4096"}

        mock_service = AsyncMock()
        mock_service.afetch = AsyncMock(return_value=mock_response)

        downloader = DirectDownloader(fetch_service=mock_service)
        results = await downloader.extract_info("https://example.com/doc.pdf")

        assert len(results) == 1
        assert results[0].url == "https://example.com/doc.pdf"
        assert results[0].mime_type == "application/pdf"
        assert results[0].file_size_bytes == 4096
        assert results[0].ext == ".pdf"

    @pytest.mark.asyncio
    async def test_direct_downloader_extract_info_no_content_length(self):
        mock_response = MagicMock()
        mock_response.content_type = "image/png"
        mock_response.headers = {"content-length": "0"}

        mock_service = AsyncMock()
        mock_service.afetch = AsyncMock(return_value=mock_response)

        downloader = DirectDownloader(fetch_service=mock_service)
        results = await downloader.extract_info("https://example.com/img.png")

        assert len(results) == 1
        assert results[0].file_size_bytes is None  # 0 converts to None via `or None`


class TestDirectDownloaderDownload:
    @pytest.mark.asyncio
    async def test_direct_downloader_download(self, tmp_path):
        """Test direct download with mocked streaming."""
        chunk1 = MagicMock()
        chunk1.data = b"Hello "
        chunk2 = MagicMock()
        chunk2.data = b"World"

        async def mock_astream(request):
            yield chunk1
            yield chunk2

        mock_service = MagicMock()
        mock_service.astream = mock_astream

        downloader = DirectDownloader(fetch_service=mock_service)
        results = await downloader.download(
            "https://example.com/hello.txt",
            output_dir=str(tmp_path),
        )

        assert len(results) == 1
        result = results[0]
        assert result.source_url == "https://example.com/hello.txt"
        assert result.filename == "hello.txt"
        assert result.file_size_bytes == 11
        assert result.checksum_sha256 is not None
        assert result.local_path is not None

        # Verify the file was actually written
        import pathlib

        written = pathlib.Path(result.local_path)
        assert written.exists()
        assert written.read_bytes() == b"Hello World"

    @pytest.mark.asyncio
    async def test_direct_downloader_download_uses_temp_dir_when_no_output_dir(self):
        """When no output_dir is given, a temp directory should be used."""
        chunk = MagicMock()
        chunk.data = b"data"

        async def mock_astream(request):
            yield chunk

        mock_service = MagicMock()
        mock_service.astream = mock_astream

        downloader = DirectDownloader(fetch_service=mock_service)
        results = await downloader.download("https://example.com/file.bin")

        assert len(results) == 1
        assert "pyfetcher-direct-" in results[0].local_path
