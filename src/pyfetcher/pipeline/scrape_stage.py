"""Scrape pipeline stage for :mod:`pyfetcher.pipeline`.

Purpose:
    Extract content, metadata, and media references from fetched pages.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pyfetcher.db.models.job import Job
from pyfetcher.db.models.page import Page
from pyfetcher.db.repo import create_job, notify
from pyfetcher.events.channels import Channels
from pyfetcher.pipeline.stage import PipelineStage


class ScrapeStage(PipelineStage):
    """Scrape stage: extract content and metadata from pages.

    Runs content extraction (trafilatura), markdown conversion,
    metadata extraction, and discovers media URLs for download.
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(job_type="scrape", **kwargs)  # type: ignore[arg-type]

    async def process(self, job: Job, session: AsyncSession) -> dict | None:
        """Extract content from a stored page and create download jobs."""
        page_id = uuid.UUID(job.payload["page_id"]) if job.payload else None
        if page_id is None:
            return {"error": "no page_id in payload"}

        result = await session.execute(select(Page).where(Page.id == page_id))
        page = result.scalar_one_or_none()
        if page is None or not page.html:
            return {"error": "page not found or empty"}

        # Content extraction (lazy imports for optional deps)
        try:
            from pyfetcher.extractors.content import extract_article_text

            page.extracted_text = extract_article_text(page.html, url=page.url)
        except ImportError:
            pass

        try:
            from pyfetcher.extractors.convert import html_to_markdown

            page.extracted_markdown = html_to_markdown(page.html)
        except ImportError:
            pass

        # Metadata extraction
        from pyfetcher.metadata.html import extract_basic_html_metadata
        from pyfetcher.metadata.opengraph import extract_open_graph_metadata

        meta = extract_basic_html_metadata(page.html, base_url=page.final_url or page.url)
        page.title = meta.title
        page.description = meta.description
        page.canonical_url = meta.canonical_url

        og = extract_open_graph_metadata(page.html)
        if og:
            page.og_metadata = og.model_dump()

        await session.flush()

        # Discover media URLs and create download jobs
        media_urls = self._find_media_urls(page.html, base_url=page.final_url or page.url)
        download_job_ids = []
        for media_url in media_urls:
            dl_job = await create_job(
                session,
                job_type="download",
                url=media_url,
                payload={"page_id": str(page.id)},
                parent_job_id=job.id,
            )
            await notify(session, Channels.DOWNLOAD_JOBS, str(dl_job.id))
            download_job_ids.append(str(dl_job.id))

        return {
            "page_id": str(page.id),
            "title": page.title,
            "media_urls_found": len(media_urls),
            "download_jobs": download_job_ids,
        }

    def _find_media_urls(self, html: str, *, base_url: str) -> list[str]:
        """Extract media URLs (images, videos, audio) from HTML."""
        from pyfetcher.scrape.selectors import extract_attrs

        media_urls = []
        for attrs in extract_attrs(html, "img[src]", attrs=["src"]):
            src = attrs.get("src")
            if src:
                from urllib.parse import urljoin

                media_urls.append(urljoin(base_url, src))

        for attrs in extract_attrs(html, "video source[src], audio source[src]", attrs=["src"]):
            src = attrs.get("src")
            if src:
                from urllib.parse import urljoin

                media_urls.append(urljoin(base_url, src))

        return media_urls
