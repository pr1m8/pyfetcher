"""URL frontier (priority queue) for :mod:`pyfetcher.crawler`.

Purpose:
    Manage the URL crawl queue backed by Postgres. Implements the
    dual-queue pattern: priority-based selection with per-host
    politeness enforcement.
"""

from __future__ import annotations

import uuid

from pyfetcher.crawler.dedup import URLDeduplicator


class Frontier:
    """Postgres-backed URL frontier with dedup and priority.

    Combines job creation, dedup checking, and priority management
    into a single interface for the crawl stage.

    Args:
        deduplicator: URL dedup checker.
    """

    def __init__(self, deduplicator: URLDeduplicator | None = None) -> None:
        self._dedup = deduplicator or URLDeduplicator()

    async def add_url(
        self,
        session: object,
        url: str,
        *,
        priority: int = 0,
        parent_job_id: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        """Add a URL to the frontier if not already seen.

        Args:
            session: Async database session.
            url: The URL to add.
            priority: Crawl priority (higher = more urgent).
            parent_job_id: Optional parent job for traceability.

        Returns:
            The new job UUID, or ``None`` if the URL was already seen.
        """
        if await self._dedup.is_seen(session, url):
            return None

        await self._dedup.mark_seen(session, url)

        from pyfetcher.db.repo import create_job

        job = await create_job(
            session,  # type: ignore[arg-type]
            job_type="crawl",
            url=url,
            priority=priority,
            parent_job_id=parent_job_id,
        )
        return job.id

    async def add_urls(
        self,
        session: object,
        urls: list[str],
        *,
        priority: int = 0,
        parent_job_id: uuid.UUID | None = None,
    ) -> list[uuid.UUID]:
        """Add multiple URLs, skipping duplicates.

        Args:
            session: Async database session.
            urls: URLs to add.
            priority: Crawl priority.
            parent_job_id: Optional parent job.

        Returns:
            List of created job UUIDs (excludes dupes).
        """
        created = []
        for url in urls:
            job_id = await self.add_url(
                session, url, priority=priority, parent_job_id=parent_job_id
            )
            if job_id is not None:
                created.append(job_id)
        return created
