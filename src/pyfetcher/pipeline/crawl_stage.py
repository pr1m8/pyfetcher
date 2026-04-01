"""Crawl pipeline stage for :mod:`pyfetcher.pipeline`.

Purpose:
    Fetch pages, discover new URLs, and create downstream scrape jobs.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.crawler.dedup import normalize_url
from pyfetcher.crawler.frontier import Frontier
from pyfetcher.db.models.job import Job
from pyfetcher.db.models.page import Page
from pyfetcher.db.repo import create_job, notify
from pyfetcher.events.channels import Channels
from pyfetcher.fetch.service import FetchService
from pyfetcher.pipeline.stage import PipelineStage
from pyfetcher.scrape.links import extract_links


class CrawlStage(PipelineStage):
    """Crawl stage: fetch pages and discover URLs.

    Fetches each URL, stores the page in the DB, discovers links,
    adds unseen URLs to the frontier, and creates a scrape job.

    Args:
        fetch_service: FetchService for HTTP requests.
        frontier: URL frontier for dedup + queueing.
    """

    def __init__(
        self,
        *,
        fetch_service: FetchService | None = None,
        frontier: Frontier | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(job_type="crawl", **kwargs)  # type: ignore[arg-type]
        self._fetch = fetch_service or FetchService()
        self._frontier = frontier or Frontier()

    async def process(self, job: Job, session: AsyncSession) -> dict | None:
        """Fetch a URL, store the page, discover links, create scrape job."""
        response = await self._fetch.afetch(FetchRequest(url=job.url))

        page = Page(
            url=job.url,
            final_url=response.final_url,
            hostname=normalize_url(job.url).split("/")[2] if "/" in job.url else "",
            status_code=response.status_code,
            content_type=response.content_type,
            html=response.text,
            response_headers=response.headers,
            fetched_at=job.claimed_at,
            elapsed_ms=response.elapsed_ms,
        )
        session.add(page)
        await session.flush()

        # Discover and enqueue new URLs
        if response.text:
            links = extract_links(response.text, base_url=response.final_url, same_domain_only=True)
            urls = [link.url for link in links]
            await self._frontier.add_urls(session, urls, parent_job_id=job.id)

        # Create scrape job for this page
        scrape_job = await create_job(
            session,
            job_type="scrape",
            url=job.url,
            payload={"page_id": str(page.id)},
            parent_job_id=job.id,
        )
        await notify(session, Channels.SCRAPE_JOBS, str(scrape_job.id))

        return {"page_id": str(page.id), "status_code": response.status_code}
