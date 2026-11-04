"""Bounded in-process fan-out for job worker event adapters."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from pyfetcher.jobs.worker import WorkerEvent


class WorkerEventBroker:
    """Fan worker events out to HTTP, gRPC, or application subscribers.

    The broker is intentionally process-local and lossy for slow subscribers.
    Durable audit or event processing should use a dedicated event sink.
    """

    def __init__(self, *, subscriber_buffer: int = 100) -> None:
        if subscriber_buffer < 1:
            raise ValueError("subscriber_buffer must be at least 1")
        self._subscriber_buffer = subscriber_buffer
        self._subscribers: set[asyncio.Queue[WorkerEvent]] = set()

    async def publish(self, event: WorkerEvent) -> None:
        """Publish an event without blocking a worker on slow subscribers."""
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    async def subscribe(self, *, job_id: UUID | None = None) -> AsyncIterator[WorkerEvent]:
        """Yield future events, optionally filtering by logical job ID."""
        queue: asyncio.Queue[WorkerEvent] = asyncio.Queue(self._subscriber_buffer)
        self._subscribers.add(queue)
        try:
            while True:
                event = await queue.get()
                if job_id is None or event.job_id == job_id:
                    yield event
        finally:
            self._subscribers.discard(queue)


__all__ = ["WorkerEventBroker"]
