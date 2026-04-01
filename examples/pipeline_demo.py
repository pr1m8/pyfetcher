"""Pipeline demo for pyfetcher.

Demonstrates seeding URLs and running the crawl-scrape-download pipeline.
Requires: pip install 'pyfetcher[pipeline]'
Requires: make infra-up && make migrate
"""

from __future__ import annotations

import asyncio

from pyfetcher.config import PyfetcherConfig
from pyfetcher.crawler.frontier import Frontier
from pyfetcher.db.engine import build_async_engine, build_session_factory


async def seed_urls() -> None:
    """Seed the frontier with starting URLs."""
    print("=== Seeding URLs ===")
    config = PyfetcherConfig()
    engine = build_async_engine(config)
    session_factory = build_session_factory(engine)

    frontier = Frontier()
    async with session_factory() as session:
        created = await frontier.add_urls(
            session,
            [
                "https://httpbin.org/html",
                "https://httpbin.org/links/5",
            ],
            priority=10,
        )
        await session.commit()
        print(f"  Seeded {len(created)} URLs")

    await engine.dispose()


async def run_pipeline() -> None:
    """Run the full pipeline."""
    print("\n=== Starting Pipeline ===")
    print("  (Ctrl+C to stop)")

    from pyfetcher.pipeline.runner import PipelineRunner

    config = PyfetcherConfig(
        crawl_concurrency=2,
        scrape_concurrency=4,
        download_concurrency=2,
    )
    runner = PipelineRunner(config)

    try:
        await runner.start()
    except KeyboardInterrupt:
        await runner.stop()
        print("\n  Pipeline stopped")


if __name__ == "__main__":
    asyncio.run(seed_urls())
    asyncio.run(run_pipeline())
