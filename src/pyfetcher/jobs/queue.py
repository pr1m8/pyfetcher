"""Queue semantics shared by local, Redis, and other worker runtimes.

Purpose:
    Standardize enqueue, leasing, acknowledgement, retry, heartbeat, and queue
    inspection without claiming that every backend offers identical durability.

Design:
    Delivery is at-least-once. Templates must use idempotency keys or durable
    result stores for externally visible side effects. The in-memory backend is
    a reference implementation for tests and single-process flows only.
"""

from __future__ import annotations

import asyncio
import itertools
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from pyfetcher.jobs.models import JobRequest


class JobLease(BaseModel):
    """One queue delivery owned by a worker until ack, retry, or expiry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    message_id: str
    job: JobRequest
    consumer: str
    delivery_count: int = Field(default=1, ge=1)
    leased_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lease_expires_at: datetime | None = None


class QueueStats(BaseModel):
    """Portable queue health snapshot for CLI, API, and metrics surfaces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    queued: int = Field(ge=0)
    leased: int = Field(ge=0)
    completed: int = Field(ge=0)
    retried: int = Field(ge=0)
    dead: int = Field(ge=0)


class JobQueue(Protocol):
    """At-least-once job queue contract."""

    async def enqueue(self, job: JobRequest) -> bool: ...

    async def reserve(
        self,
        consumer: str,
        *,
        timeout_seconds: float | None = None,
        lease_seconds: float = 60.0,
    ) -> JobLease | None: ...

    async def acknowledge(self, lease: JobLease) -> None: ...

    async def retry(
        self,
        lease: JobLease,
        *,
        delay_seconds: float = 0,
    ) -> None: ...

    async def reject(self, lease: JobLease, *, reason: str) -> None: ...

    async def heartbeat(self, lease: JobLease, *, lease_seconds: float = 60.0) -> JobLease: ...

    async def stats(self) -> QueueStats: ...

    async def aclose(self) -> None: ...


class InMemoryJobQueue:
    """Priority queue with leasing and deduplication for local execution."""

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, int, JobRequest]] = asyncio.PriorityQueue()
        self._sequence = itertools.count()
        self._leases: dict[UUID, JobLease] = {}
        self._idempotency_keys: set[str] = set()
        self._delivery_counts: dict[UUID, int] = {}
        self._completed = 0
        self._retried = 0
        self._dead = 0
        self._scheduled: set[asyncio.Task[None]] = set()
        self._closed = False

    async def _put(self, job: JobRequest) -> None:
        await self._queue.put((-job.policy.priority, next(self._sequence), job))

    async def enqueue(self, job: JobRequest) -> bool:
        if self._closed:
            raise RuntimeError("job queue is closed")
        if job.idempotency_key is not None:
            if job.idempotency_key in self._idempotency_keys:
                return False
            self._idempotency_keys.add(job.idempotency_key)
        await self._put(job)
        return True

    async def reserve(
        self,
        consumer: str,
        *,
        timeout_seconds: float | None = None,
        lease_seconds: float = 60.0,
    ) -> JobLease | None:
        if self._closed:
            return None
        now = datetime.now(UTC)
        expired = [
            lease
            for lease in self._leases.values()
            if lease.lease_expires_at is not None and lease.lease_expires_at <= now
        ]
        for lease in expired:
            self._leases.pop(lease.id, None)
            self._queue.task_done()
            await self._put(lease.job)
        try:
            if timeout_seconds is None:
                _, _, job = await self._queue.get()
            else:
                _, _, job = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout_seconds,
                )
        except TimeoutError:
            return None
        deliveries = self._delivery_counts.get(job.id, 0) + 1
        self._delivery_counts[job.id] = deliveries
        now = datetime.now(UTC)
        lease = JobLease(
            message_id=str(job.id),
            job=job,
            consumer=consumer,
            delivery_count=deliveries,
            leased_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
        )
        self._leases[lease.id] = lease
        return lease

    def _take(self, lease: JobLease) -> JobLease:
        try:
            current = self._leases.pop(lease.id)
        except KeyError as exc:
            raise KeyError(f"unknown or completed job lease: {lease.id}") from exc
        self._queue.task_done()
        return current

    async def acknowledge(self, lease: JobLease) -> None:
        self._take(lease)
        self._completed += 1

    async def retry(
        self,
        lease: JobLease,
        *,
        delay_seconds: float = 0,
    ) -> None:
        current = self._take(lease)
        self._retried += 1
        job = current.job.next_attempt()

        async def requeue() -> None:
            if delay_seconds:
                await asyncio.sleep(delay_seconds)
            if not self._closed:
                await self._put(job)

        task = asyncio.create_task(requeue())
        self._scheduled.add(task)
        task.add_done_callback(self._scheduled.discard)

    async def reject(self, lease: JobLease, *, reason: str) -> None:
        self._take(lease)
        self._dead += 1

    async def heartbeat(self, lease: JobLease, *, lease_seconds: float = 60.0) -> JobLease:
        if lease.id not in self._leases:
            raise KeyError(f"unknown or completed job lease: {lease.id}")
        renewed = lease.model_copy(
            update={"lease_expires_at": datetime.now(UTC) + timedelta(seconds=lease_seconds)}
        )
        self._leases[lease.id] = renewed
        return renewed

    async def stats(self) -> QueueStats:
        return QueueStats(
            queued=self._queue.qsize(),
            leased=len(self._leases),
            completed=self._completed,
            retried=self._retried,
            dead=self._dead,
        )

    async def aclose(self) -> None:
        self._closed = True
        for task in tuple(self._scheduled):
            task.cancel()
        if self._scheduled:
            await asyncio.gather(*self._scheduled, return_exceptions=True)


__all__ = ["InMemoryJobQueue", "JobLease", "JobQueue", "QueueStats"]
