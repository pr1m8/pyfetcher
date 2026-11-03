"""Composable job application container.

Purpose:
    Assemble the registry, executor, control plane, worker, queue, store, and
    runtime-only services once, then let a CLI, FastAPI app, or process host own
    their lifecycle explicitly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Protocol

from pyfetcher.jobs.queue import InMemoryJobQueue, JobQueue
from pyfetcher.jobs.registry import JobContext, JobExecutionHook, JobExecutor, TemplateRegistry
from pyfetcher.jobs.service import JobService
from pyfetcher.jobs.store import InMemoryJobStore, JobStore
from pyfetcher.jobs.templates import register_builtin_templates
from pyfetcher.jobs.worker import JobWorker, WorkerConfig, WorkerEventSink


class AsyncCloseable(Protocol):
    """Minimal lifecycle surface for application-owned resources."""

    async def aclose(self) -> None: ...


class JobApplication:
    """Fully assembled durable-job application and lifecycle owner."""

    def __init__(
        self,
        *,
        registry: TemplateRegistry,
        executor: JobExecutor,
        queue: JobQueue,
        store: JobStore,
        service: JobService,
        worker: JobWorker,
        owns_queue: bool,
        owns_store: bool,
        owned_resources: tuple[AsyncCloseable, ...] = (),
    ) -> None:
        self.registry = registry
        self.executor = executor
        self.queue = queue
        self.store = store
        self.service = service
        self.worker = worker
        self._owns_queue = owns_queue
        self._owns_store = owns_store
        self._owned_resources = owned_resources
        self._closed = False
        self._close_lock = asyncio.Lock()

    @property
    def closed(self) -> bool:
        """Return whether application-owned resources have been closed."""
        return self._closed

    @classmethod
    def create(
        cls,
        *,
        context: JobContext | None = None,
        registry: TemplateRegistry | None = None,
        queue: JobQueue | None = None,
        store: JobStore | None = None,
        hooks: Iterable[JobExecutionHook] = (),
        worker_config: WorkerConfig | None = None,
        event_sinks: Iterable[WorkerEventSink] = (),
        owned_resources: Iterable[AsyncCloseable] = (),
    ) -> JobApplication:
        """Create an application with local defaults and injectable adapters."""
        resolved_registry = registry or TemplateRegistry()
        if registry is None:
            register_builtin_templates(resolved_registry)
        resolved_queue = queue or InMemoryJobQueue()
        resolved_store = store or InMemoryJobStore()
        executor = JobExecutor(
            resolved_registry,
            context=context,
            hooks=tuple(hooks),
        )
        service = JobService(resolved_queue, resolved_store, resolved_registry)
        worker = JobWorker(
            service,
            executor,
            config=worker_config,
            event_sinks=tuple(event_sinks),
        )
        return cls(
            registry=resolved_registry,
            executor=executor,
            queue=resolved_queue,
            store=resolved_store,
            service=service,
            worker=worker,
            owns_queue=queue is None,
            owns_store=store is None,
            owned_resources=tuple(owned_resources),
        )

    async def start(self) -> None:
        """Start the application worker."""
        if self._closed:
            raise RuntimeError("job application is closed")
        await self.worker.start()

    async def aclose(self) -> None:
        """Gracefully stop the worker and close owned dependencies once."""
        async with self._close_lock:
            if self._closed:
                return
            await self.worker.stop()
            if self._owns_queue:
                await self.queue.aclose()
            if self._owns_store:
                await self.store.aclose()
            for resource in reversed(self._owned_resources):
                await resource.aclose()
            self._closed = True

    async def __aenter__(self) -> JobApplication:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


__all__ = ["AsyncCloseable", "JobApplication"]
