"""Pipeline runner for :mod:`pyfetcher.pipeline`.

Purpose:
    Start and manage all pipeline stages (crawl, scrape, download)
    with explicit worker and resource lifecycles.
"""

from __future__ import annotations

import asyncio
import logging

from pyfetcher.config import PyfetcherConfig
from pyfetcher.db.engine import build_async_engine, build_session_factory
from pyfetcher.pipeline.crawl_stage import CrawlStage
from pyfetcher.pipeline.download_stage import DownloadStage
from pyfetcher.pipeline.scrape_stage import ScrapeStage
from pyfetcher.pipeline.stage import PipelineStage

logger = logging.getLogger("pyfetcher.pipeline")


class PipelineRunner:
    """Runs the complete crawl -> scrape -> download pipeline.

    Starts all three polling workers. Stages emit Postgres notifications for
    external listeners, while workers claim durable rows directly with
    ``FOR UPDATE SKIP LOCKED``.

    Args:
        config: Application configuration.
    """

    def __init__(self, config: PyfetcherConfig | None = None) -> None:
        self._config = config or PyfetcherConfig()
        self._engine = build_async_engine(self._config)
        self._session_factory = build_session_factory(self._engine)
        self._stages: list[PipelineStage] = []
        self._tasks: list[asyncio.Task[None]] = []
        self._closed = False
        self._close_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start all pipeline stages and begin processing."""
        if self._tasks:
            raise RuntimeError("pipeline is already running")
        if self._closed:
            raise RuntimeError("pipeline runner is closed")
        logger.info("Starting pipeline...")

        crawl = CrawlStage(
            session_factory=self._session_factory,
            concurrency=self._config.crawl_concurrency,
        )
        scrape = ScrapeStage(
            session_factory=self._session_factory,
            concurrency=self._config.scrape_concurrency,
        )
        download = DownloadStage(
            session_factory=self._session_factory,
            concurrency=self._config.download_concurrency,
        )
        self._stages = [crawl, scrape, download]

        self._tasks = [
            asyncio.create_task(crawl.run(), name="pyfetcher:pipeline:crawl"),
            asyncio.create_task(scrape.run(), name="pyfetcher:pipeline:scrape"),
            asyncio.create_task(download.run(), name="pyfetcher:pipeline:download"),
        ]

        logger.info("Pipeline running with %d stages", len(self._tasks))
        try:
            await asyncio.gather(*self._tasks)
        finally:
            await self._close()

    async def stop(self) -> None:
        """Stop all stages gracefully."""
        for stage in self._stages:
            stage.stop()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._close()

    async def _close(self) -> None:
        """Close stage resources and the database engine once."""
        async with self._close_lock:
            if self._closed:
                return
            for stage in self._stages:
                stage.stop()
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            await asyncio.gather(*(stage.aclose() for stage in self._stages))
            await self._engine.dispose()
            self._closed = True
            logger.info("Pipeline stopped")

    async def __aenter__(self) -> PipelineRunner:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.stop()
