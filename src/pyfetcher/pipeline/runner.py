"""Pipeline runner for :mod:`pyfetcher.pipeline`.

Purpose:
    Start and manage all pipeline stages (crawl, scrape, download)
    with event listeners for coordination.
"""

from __future__ import annotations

import asyncio
import logging

from pyfetcher.config import PyfetcherConfig
from pyfetcher.db.engine import build_async_engine, build_session_factory
from pyfetcher.events.listener import EventListener
from pyfetcher.pipeline.crawl_stage import CrawlStage
from pyfetcher.pipeline.download_stage import DownloadStage
from pyfetcher.pipeline.scrape_stage import ScrapeStage

logger = logging.getLogger("pyfetcher.pipeline")


class PipelineRunner:
    """Runs the complete crawl -> scrape -> download pipeline.

    Starts all three pipeline stages and an event listener for
    Postgres NOTIFY coordination.

    Args:
        config: Application configuration.
    """

    def __init__(self, config: PyfetcherConfig | None = None) -> None:
        self._config = config or PyfetcherConfig()
        self._engine = build_async_engine(self._config)
        self._session_factory = build_session_factory(self._engine)
        self._stages: list[object] = []
        self._listener: EventListener | None = None

    async def start(self) -> None:
        """Start all pipeline stages and begin processing."""
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

        tasks = [
            asyncio.create_task(crawl.run()),
            asyncio.create_task(scrape.run()),
            asyncio.create_task(download.run()),
        ]

        logger.info("Pipeline running with %d stages", len(tasks))
        await asyncio.gather(*tasks)

    async def stop(self) -> None:
        """Stop all stages gracefully."""
        for stage in self._stages:
            if hasattr(stage, "stop"):
                stage.stop()
        await self._engine.dispose()
        logger.info("Pipeline stopped")
