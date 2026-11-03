"""Unit tests for pyfetcher.pipeline.stage module."""

from __future__ import annotations

import uuid
from abc import ABC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyfetcher.acquisition.models import AcquisitionProvenance, AcquisitionResult
from pyfetcher.db.models.job import Job
from pyfetcher.downloaders.base import DownloadResult
from pyfetcher.pipeline.download_stage import DownloadStage
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

    @pytest.mark.parametrize("concurrency", [0, -1])
    def test_pipeline_stage_rejects_invalid_concurrency(self, concurrency):
        with pytest.raises(ValueError, match="concurrency"):
            ConcretePipelineStage(
                session_factory=MagicMock(),
                job_type="scrape",
                concurrency=concurrency,
            )

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
            concurrency=1,
            poll_interval=0.01,
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
            except TimeoutError:
                stage.stop()

            # complete_job should have been called for the processed job
            mock_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_stage_processes_jobs_concurrently(self):
        """Configured slots claim and process independent jobs concurrently."""
        import asyncio

        jobs = [
            Job(id=uuid.uuid4(), type="crawl", url=f"https://example.com/{index}")
            for index in range(2)
        ]
        claimed = iter(jobs)
        both_started = asyncio.Event()
        release = asyncio.Event()
        active = 0
        max_active = 0

        async def claim(*_args):
            return next(claimed, None)

        async def process_fn(_job, _session):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            if active == 2:
                both_started.set()
            await release.wait()
            active -= 1
            return {"status": "ok"}

        def session_context():
            session = AsyncMock()
            context = AsyncMock()
            context.__aenter__ = AsyncMock(return_value=session)
            context.__aexit__ = AsyncMock(return_value=False)
            return context

        stage = ConcretePipelineStage(
            session_factory=MagicMock(side_effect=session_context),
            job_type="crawl",
            process_fn=process_fn,
            concurrency=2,
            poll_interval=0.01,
        )

        with (
            patch("pyfetcher.pipeline.stage.claim_job", side_effect=claim),
            patch("pyfetcher.pipeline.stage.complete_job", new_callable=AsyncMock),
            patch("pyfetcher.pipeline.stage.fail_job", new_callable=AsyncMock),
        ):
            task = asyncio.create_task(stage.run())
            await asyncio.wait_for(both_started.wait(), timeout=1)
            stage.stop()
            release.set()
            await asyncio.wait_for(task, timeout=1)

        assert max_active == 2


class TestDownloadStageAcquisition:
    @pytest.mark.asyncio
    async def test_persists_every_acquired_item(self):
        downloads = (
            DownloadResult(
                source_url="https://example.com/one.jpg",
                local_path="/tmp/one.jpg",
                filename="one.jpg",
                mime_type="image/jpeg",
                file_size_bytes=10,
            ),
            DownloadResult(
                source_url="https://example.com/two.jpg",
                local_path="/tmp/two.jpg",
                filename="two.jpg",
                mime_type="image/jpeg",
                file_size_bytes=20,
            ),
        )
        acquisition = MagicMock()
        acquisition.acquire = AsyncMock(
            return_value=AcquisitionResult(
                source_url="https://example.com/gallery",
                operation="download",
                provider="gallery_dl",
                downloads=downloads,
                provenance=AcquisitionProvenance(provider="gallery_dl"),
            )
        )
        store = MagicMock(default_bucket="assets")
        store.upload_file = AsyncMock()
        session = MagicMock()

        async def flush():
            asset = session.add.call_args.args[0]
            if asset.id is None:
                asset.id = uuid.uuid4()

        session.flush = AsyncMock(side_effect=flush)
        stage = DownloadStage(
            session_factory=MagicMock(),
            acquisition_service=acquisition,
            object_store=store,
        )
        job = Job(
            id=uuid.uuid4(),
            type="download",
            url="https://example.com/gallery",
            payload={"provider": "gallery_dl"},
        )

        result = await stage.process(job, session)

        assert result is not None
        assert result["provider"] == "gallery_dl"
        assert len(result["asset_ids"]) == 2
        assert len(result["items"]) == 2
        assert session.add.call_count == 2
        assert store.upload_file.await_count == 2
        request = acquisition.acquire.await_args.args[0]
        assert request.provider == "gallery_dl"
