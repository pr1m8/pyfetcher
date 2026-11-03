"""Base pipeline stage for :mod:`pyfetcher.pipeline`.

Purpose:
    Provide the base class for pipeline workers that claim jobs,
    process them, and emit events to trigger downstream stages.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pyfetcher.db.models.job import Job
from pyfetcher.db.repo import claim_job, complete_job, fail_job

logger = logging.getLogger("pyfetcher.pipeline")


class PipelineStage(ABC):
    """Base class for pipeline stage workers.

    Subclasses implement :meth:`process` to handle claimed jobs.
    The base class handles job claiming, completion, failure, retry,
    and event publishing.

    Args:
        session_factory: Async session factory for DB access.
        job_type: The job type this stage processes ('crawl', 'scrape', 'download').
        worker_id: Unique worker identifier.
        concurrency: Maximum concurrent jobs.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        job_type: str,
        worker_id: str | None = None,
        concurrency: int = 5,
        poll_interval: float = 0.5,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than 0")
        self._session_factory = session_factory
        self._job_type = job_type
        self._worker_id = worker_id or f"{job_type}-{uuid.uuid4().hex[:8]}"
        self._concurrency = concurrency
        self._poll_interval = poll_interval
        self._running = False

    @abstractmethod
    async def process(self, job: Job, session: AsyncSession) -> dict | None:
        """Process a claimed job.

        Args:
            job: The claimed job to process.
            session: Active database session.

        Returns:
            Optional result dict to store on the job.
        """
        ...

    async def run(self) -> None:
        """Run the stage worker loop.

        Claims and processes jobs until :meth:`stop` is called.
        Starts one independent claim loop per configured concurrency slot.
        """
        if self._running:
            raise RuntimeError(f"{self._job_type} stage is already running")
        self._running = True
        logger.info(
            "Stage %s started (worker=%s, concurrency=%d)",
            self._job_type,
            self._worker_id,
            self._concurrency,
        )

        workers = [
            asyncio.create_task(
                self._run_worker(slot),
                name=f"pyfetcher:{self._job_type}:{slot}",
            )
            for slot in range(self._concurrency)
        ]
        try:
            await asyncio.gather(*workers)
        finally:
            self._running = False
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    async def _run_worker(self, slot: int) -> None:
        """Claim and process jobs for one concurrency slot."""
        worker_id = f"{self._worker_id}:{slot + 1}"
        while self._running:
            async with self._session_factory() as session:
                job = await claim_job(session, self._job_type, worker_id)
                if job is not None:
                    job.state = "running"
                    job.started_at = job.claimed_at
                    await session.commit()

            if job is None:
                await asyncio.sleep(self._poll_interval)
                continue

            try:
                async with self._session_factory() as session:
                    result = await self.process(job, session)
                    await complete_job(session, job.id, result=result)
                    await session.commit()
                    logger.info("Job %s completed", job.id)
            except Exception as exc:
                async with self._session_factory() as session:
                    await fail_job(session, job.id, error=str(exc))
                    await session.commit()
                logger.warning("Job %s failed: %s", job.id, exc)

    def stop(self) -> None:
        """Signal the worker to stop after current jobs complete."""
        self._running = False

    async def aclose(self) -> None:
        """Close resources owned by the stage."""
        return None

    async def __aenter__(self) -> PipelineStage:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.stop()
        await self.aclose()
