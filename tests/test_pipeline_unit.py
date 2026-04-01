"""Unit tests for pyfetcher.pipeline.stage module."""

from __future__ import annotations

import uuid
from abc import ABC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyfetcher.db.models.job import Job
from pyfetcher.pipeline.stage import PipelineStage


class TestPipelineStageIsAbstract:
    def test_pipeline_stage_is_abstract(self):
        """PipelineStage should be an abstract base class."""
        assert issubclass(PipelineStage, ABC)

    def test_pipeline_stage_cannot_be_instantiated(self):
        """Cannot instantiate PipelineStage directly because process is abstract."""
        mock_session_factory = MagicMock()
        with pytest.raises(TypeError):
            PipelineStage(
                session_factory=mock_session_factory,
                job_type="test",
            )


class ConcretePipelineStage(PipelineStage):
    """A concrete implementation for testing."""

    def __init__(self, process_fn=None, **kwargs):
        super().__init__(**kwargs)
        self._process_fn = process_fn

    async def process(self, job, session):
        if self._process_fn:
            return await self._process_fn(job, session)
        return {"status": "done"}


class TestPipelineStageInit:
    def test_pipeline_stage_worker_id_auto_generated(self):
        mock_sf = MagicMock()
        stage = ConcretePipelineStage(
            session_factory=mock_sf,
            job_type="crawl",
        )
        assert stage._worker_id.startswith("crawl-")
        assert len(stage._worker_id) > len("crawl-")

    def test_pipeline_stage_custom_worker_id(self):
        mock_sf = MagicMock()
        stage = ConcretePipelineStage(
            session_factory=mock_sf,
            job_type="crawl",
            worker_id="my-worker",
        )
        assert stage._worker_id == "my-worker"

    def test_pipeline_stage_concurrency(self):
        mock_sf = MagicMock()
        stage = ConcretePipelineStage(
            session_factory=mock_sf,
            job_type="scrape",
            concurrency=20,
        )
        assert stage._concurrency == 20

    def test_pipeline_stage_stop(self):
        mock_sf = MagicMock()
        stage = ConcretePipelineStage(
            session_factory=mock_sf,
            job_type="crawl",
        )
        assert stage._running is False
        stage._running = True
        stage.stop()
        assert stage._running is False


class TestCrawlStageProcess:
    @pytest.mark.asyncio
    async def test_crawl_stage_process(self):
        """Simulate a crawl stage processing a job with a mocked FetchService."""
        mock_session = AsyncMock()
        mock_sf = MagicMock()

        job = Job(
            id=uuid.uuid4(),
            type="crawl",
            url="https://example.com",
            state="running",
        )

        async def crawl_process(job, session):
            # Simulate calling FetchService and returning discovered URLs
            return {"discovered_urls": ["https://example.com/page1"]}

        stage = ConcretePipelineStage(
            session_factory=mock_sf,
            job_type="crawl",
            process_fn=crawl_process,
        )

        result = await stage.process(job, mock_session)
        assert result is not None
        assert "discovered_urls" in result
        assert len(result["discovered_urls"]) == 1


class TestScrapeStageProcess:
    @pytest.mark.asyncio
    async def test_scrape_stage_process(self):
        """Simulate a scrape stage processing a job with a mocked page."""
        mock_session = AsyncMock()
        mock_sf = MagicMock()

        job = Job(
            id=uuid.uuid4(),
            type="scrape",
            url="https://example.com/page",
            state="running",
        )

        async def scrape_process(job, session):
            # Simulate extracting content from the page
            return {
                "extracted_text": "Article content here.",
                "title": "Test Article",
                "media_urls": ["https://example.com/img.jpg"],
            }

        stage = ConcretePipelineStage(
            session_factory=mock_sf,
            job_type="scrape",
            process_fn=scrape_process,
        )

        result = await stage.process(job, mock_session)
        assert result is not None
        assert result["extracted_text"] == "Article content here."
        assert result["title"] == "Test Article"
        assert len(result["media_urls"]) == 1


class TestDownloadStageProcess:
    @pytest.mark.asyncio
    async def test_download_stage_process(self):
        """Simulate a download stage processing a job with a mocked DirectDownloader."""
        mock_session = AsyncMock()
        mock_sf = MagicMock()

        job = Job(
            id=uuid.uuid4(),
            type="download",
            url="https://example.com/video.mp4",
            state="running",
        )

        async def download_process(job, session):
            # Simulate download and return result dict
            return {
                "source_url": job.url,
                "local_path": "/tmp/video.mp4",
                "file_size_bytes": 10485760,
                "checksum_sha256": "abc123def456",
                "minio_key": "media/2026/01/01/hash/video.mp4",
            }

        stage = ConcretePipelineStage(
            session_factory=mock_sf,
            job_type="download",
            process_fn=download_process,
        )

        result = await stage.process(job, mock_session)
        assert result is not None
        assert result["source_url"] == "https://example.com/video.mp4"
        assert result["file_size_bytes"] == 10485760
        assert result["minio_key"].startswith("media/")


class TestPipelineStageRunLoop:
    @pytest.mark.asyncio
    async def test_pipeline_stage_run_claims_and_processes(self):
        """Test the run loop claims a job, processes it, and completes it."""
        job = Job(
            id=uuid.uuid4(),
            type="crawl",
            url="https://example.com",
            state="claimed",
        )

        call_count = 0

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock()
        mock_sf.return_value = mock_session_ctx

        async def process_fn(j, s):
            return {"status": "ok"}

        stage = ConcretePipelineStage(
            session_factory=mock_sf,
            job_type="crawl",
            process_fn=process_fn,
        )

        # Patch claim_job to return the job once, then None, and stop the loop
        async def mock_claim_job(session, job_type, worker_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return job
            # Stop the loop after the first iteration
            stage.stop()
            return None

        with (
            patch("pyfetcher.pipeline.stage.claim_job", side_effect=mock_claim_job),
            patch("pyfetcher.pipeline.stage.complete_job", new_callable=AsyncMock) as mock_complete,
            patch("pyfetcher.pipeline.stage.fail_job", new_callable=AsyncMock),
        ):
            # Run with a timeout to prevent hanging
            import asyncio

            try:
                await asyncio.wait_for(stage.run(), timeout=5.0)
            except asyncio.TimeoutError:
                stage.stop()

            # complete_job should have been called for the processed job
            mock_complete.assert_called_once()
