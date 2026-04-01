"""Repository helpers for :mod:`pyfetcher.db`.

Purpose:
    Provide common async database operations: job claiming with
    SELECT FOR UPDATE SKIP LOCKED, bulk URL dedup checks, and
    job state transitions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from pyfetcher.db.models.job import Job
from pyfetcher.db.models.url import SeenURL


async def claim_job(
    session: AsyncSession,
    job_type: str,
    worker_id: str,
) -> Job | None:
    """Claim the next available job of the given type.

    Uses SELECT FOR UPDATE SKIP LOCKED to safely claim jobs across
    concurrent workers without contention.

    Args:
        session: Active async database session.
        job_type: Job type to claim ('crawl', 'scrape', 'download').
        worker_id: Identifier for the claiming worker.

    Returns:
        The claimed :class:`Job`, or ``None`` if no jobs are available.
    """
    now = datetime.now(UTC)
    stmt = (
        select(Job)
        .where(
            Job.type == job_type,
            Job.state.in_(["pending", "failed"]),
            (Job.next_retry_at.is_(None)) | (Job.next_retry_at <= now),
        )
        .order_by(Job.priority.desc(), Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.state = "claimed"
    job.claimed_by = worker_id
    job.claimed_at = now
    await session.flush()
    return job


async def complete_job(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    result: dict | None = None,
) -> None:
    """Mark a job as successfully completed.

    Args:
        session: Active async database session.
        job_id: The job ID to complete.
        result: Optional result payload to store.
    """
    now = datetime.now(UTC)
    stmt = (
        update(Job)
        .where(Job.id == job_id)
        .values(state="success", result=result, completed_at=now, updated_at=now)
    )
    await session.execute(stmt)


async def fail_job(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    error: str,
    retry: bool = True,
) -> None:
    """Mark a job as failed, optionally scheduling a retry.

    Args:
        session: Active async database session.
        job_id: The job ID that failed.
        error: Error description.
        retry: Whether to schedule a retry (respects max_retries).
    """
    now = datetime.now(UTC)
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one()

    job.error = error
    job.updated_at = now

    if retry and job.retry_count < job.max_retries:
        job.state = "failed"
        job.retry_count += 1
        backoff = min(2**job.retry_count, 300)
        job.next_retry_at = datetime.fromtimestamp(now.timestamp() + backoff, tz=UTC)
    else:
        job.state = "dead"
        job.completed_at = now

    await session.flush()


async def create_job(
    session: AsyncSession,
    *,
    job_type: str,
    url: str,
    priority: int = 0,
    payload: dict | None = None,
    max_retries: int = 3,
    parent_job_id: uuid.UUID | None = None,
) -> Job:
    """Create a new pending job.

    Args:
        session: Active async database session.
        job_type: Job type ('crawl', 'scrape', 'download').
        url: Target URL.
        priority: Job priority (higher = more urgent).
        payload: Type-specific configuration.
        max_retries: Maximum retry attempts.
        parent_job_id: Optional parent job for chaining.

    Returns:
        The created :class:`Job` instance.
    """
    job = Job(
        type=job_type,
        url=url,
        priority=priority,
        payload=payload,
        max_retries=max_retries,
        parent_job_id=parent_job_id,
    )
    session.add(job)
    await session.flush()
    return job


async def check_url_seen(session: AsyncSession, url_hash: int) -> bool:
    """Check if a URL hash has been seen before.

    Args:
        session: Active async database session.
        url_hash: The xxhash64 of the normalized URL.

    Returns:
        ``True`` if the URL has been seen, ``False`` otherwise.
    """
    stmt = select(SeenURL.url_hash).where(SeenURL.url_hash == url_hash)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def mark_url_seen(
    session: AsyncSession,
    *,
    url_hash: int,
    url: str,
) -> None:
    """Mark a URL as seen (upsert).

    Args:
        session: Active async database session.
        url_hash: The xxhash64 of the normalized URL.
        url: The original URL string.
    """
    now = datetime.now(UTC)
    stmt = pg_insert(SeenURL).values(
        url_hash=url_hash,
        url=url,
        first_seen_at=now,
        last_seen_at=now,
        fetch_count=1,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[SeenURL.url_hash],
        set_={"last_seen_at": now, "fetch_count": SeenURL.fetch_count + 1},
    )
    await session.execute(stmt)


async def notify(session: AsyncSession, channel: str, payload: str) -> None:
    """Send a Postgres NOTIFY on the given channel.

    Args:
        session: Active async database session.
        channel: The notification channel name.
        payload: The notification payload (typically a job UUID).
    """
    await session.execute(text(f"NOTIFY {channel}, :payload"), {"payload": payload})
