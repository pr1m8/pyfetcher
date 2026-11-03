"""Long-running worker host for portable job queues.

Purpose:
    Execute queued jobs with bounded concurrency, lease heartbeats,
    cooperative cancellation, retries, child submission, structured events,
    and terminal-result deduplication.

Design:
    The worker depends only on the portable queue, store, executor, and service
    contracts. Redis, HTTP APIs, gRPC, and deployment frameworks remain
    adapters around this host.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from pyfetcher.jobs.models import JobRequest, JobResult
from pyfetcher.jobs.queue import JobLease, JobQueue
from pyfetcher.jobs.registry import JobExecutor
from pyfetcher.jobs.service import JobService
from pyfetcher.jobs.store import JobStore

logger = logging.getLogger("pyfetcher.jobs.worker")

type WorkerEventKind = Literal[
    "worker_started",
    "worker_stopped",
    "reserved",
    "started",
    "heartbeat",
    "succeeded",
    "failed",
    "retried",
    "cancelled",
    "duplicate",
    "error",
]
type WorkerEventSink = Callable[["WorkerEvent"], None | Awaitable[None]]


class WorkerConfig(BaseModel):
    """Serializable worker runtime configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = "fetchkit-worker"
    concurrency: int = Field(default=4, ge=1)
    reserve_timeout_seconds: float = Field(default=1.0, gt=0)
    lease_seconds: float = Field(default=60.0, gt=0)
    heartbeat_seconds: float = Field(default=15.0, gt=0)
    error_backoff_seconds: float = Field(default=1.0, ge=0)
    shutdown_grace_seconds: float | None = Field(default=30.0, gt=0)

    @model_validator(mode="after")
    def _heartbeat_fits_lease(self) -> WorkerConfig:
        if self.heartbeat_seconds >= self.lease_seconds:
            raise ValueError("heartbeat_seconds must be less than lease_seconds")
        return self


class WorkerEvent(BaseModel):
    """One portable worker lifecycle event for logs, metrics, or streaming."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: WorkerEventKind
    worker_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    job_id: UUID | None = None
    run_id: UUID | None = None
    template: str | None = None
    attempt: int | None = None
    message: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class WorkerSnapshot(BaseModel):
    """Current worker state for health endpoints and CLI inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: Literal["idle", "running", "stopping", "stopped"]
    concurrency: int = Field(ge=1)
    active_jobs: tuple[UUID, ...] = ()
    completed_jobs: int = Field(default=0, ge=0)
    failed_jobs: int = Field(default=0, ge=0)
    retried_jobs: int = Field(default=0, ge=0)


class JobWorker:
    """Run queued jobs through a shared executor and control plane."""

    def __init__(
        self,
        service: JobService,
        executor: JobExecutor,
        *,
        config: WorkerConfig | None = None,
        event_sinks: tuple[WorkerEventSink, ...] = (),
    ) -> None:
        self._service = service
        self._queue: JobQueue = service.queue
        self._store: JobStore = service.store
        self._executor = executor
        self._config = config or WorkerConfig()
        self._event_sinks = event_sinks
        self._stop_event = asyncio.Event()
        self._run_task: asyncio.Task[None] | None = None
        self._slot_tasks: list[asyncio.Task[None]] = []
        self._status: Literal["idle", "running", "stopping", "stopped"] = "idle"
        self._active: set[UUID] = set()
        self._completed = 0
        self._failed = 0
        self._retried = 0

    @property
    def config(self) -> WorkerConfig:
        return self._config

    def snapshot(self) -> WorkerSnapshot:
        """Return a serializable point-in-time worker snapshot."""
        return WorkerSnapshot(
            name=self._config.name,
            status=self._status,
            concurrency=self._config.concurrency,
            active_jobs=tuple(sorted(self._active, key=str)),
            completed_jobs=self._completed,
            failed_jobs=self._failed,
            retried_jobs=self._retried,
        )

    def add_event_sink(self, sink: WorkerEventSink) -> None:
        """Attach an application-owned event sink before or during execution."""
        self._event_sinks = (*self._event_sinks, sink)

    async def _emit(
        self,
        kind: WorkerEventKind,
        *,
        job: JobRequest | None = None,
        message: str | None = None,
        metadata: dict[str, JsonValue] | None = None,
    ) -> None:
        event = WorkerEvent(
            kind=kind,
            worker_id=self._config.name,
            job_id=job.id if job is not None else None,
            run_id=job.run_id if job is not None else None,
            template=job.template.key if job is not None else None,
            attempt=job.attempt if job is not None else None,
            message=message,
            metadata=metadata or {},
        )
        level = (
            logging.ERROR
            if kind == "error"
            else logging.WARNING
            if kind == "failed"
            else logging.INFO
        )
        logger.log(
            level,
            message or kind.replace("_", " "),
            extra={
                "worker_id": event.worker_id,
                "job_id": str(event.job_id) if event.job_id else "",
                "run_id": str(event.run_id) if event.run_id else "",
                "job_template": event.template or "",
                "job_attempt": event.attempt or 0,
                "worker_event": event.kind,
            },
        )
        for sink in self._event_sinks:
            try:
                emitted = sink(event)
                if inspect.isawaitable(emitted):
                    await emitted
            except Exception:
                logger.exception(
                    "worker event sink failed",
                    extra={"worker_id": event.worker_id, "worker_event": event.kind},
                )

    async def start(self) -> asyncio.Task[None]:
        """Start the worker in the current event loop and return its task."""
        if self._run_task is not None and not self._run_task.done():
            raise RuntimeError("job worker is already running")
        self._run_task = asyncio.create_task(
            self.run(),
            name=f"pyfetcher:worker:{self._config.name}",
        )
        await asyncio.sleep(0)
        return self._run_task

    async def run(self) -> None:
        """Run until :meth:`stop` is called, finishing active jobs gracefully."""
        if self._status == "running":
            raise RuntimeError("job worker is already running")
        if self._run_task is None or self._run_task.done():
            self._run_task = asyncio.current_task()
        self._stop_event.clear()
        self._status = "running"
        await self._emit("worker_started")
        self._slot_tasks = [
            asyncio.create_task(
                self._run_slot(index),
                name=f"pyfetcher:worker:{self._config.name}:{index + 1}",
            )
            for index in range(self._config.concurrency)
        ]
        try:
            await asyncio.gather(*self._slot_tasks)
        finally:
            self._status = "stopped"
            await self._emit("worker_stopped")
            self._slot_tasks.clear()

    async def stop(self) -> None:
        """Stop reserving work and wait for active jobs to finish."""
        if self._status not in {"running", "stopping"}:
            self._status = "stopped"
            return
        self._status = "stopping"
        self._stop_event.set()
        current = asyncio.current_task()
        if self._run_task is not None and self._run_task is not current:
            if self._config.shutdown_grace_seconds is None:
                await self._run_task
                return
            try:
                async with asyncio.timeout(self._config.shutdown_grace_seconds):
                    await asyncio.shield(self._run_task)
            except TimeoutError:
                for task in self._slot_tasks:
                    task.cancel()
                await asyncio.gather(self._run_task, return_exceptions=True)

    async def _run_slot(self, index: int) -> None:
        consumer = f"{self._config.name}-{index + 1}"
        while not self._stop_event.is_set():
            try:
                lease = await self._queue.reserve(
                    consumer,
                    timeout_seconds=self._config.reserve_timeout_seconds,
                    lease_seconds=self._config.lease_seconds,
                )
                if lease is None:
                    continue
                self._active.add(lease.job.id)
                try:
                    await self._process(lease)
                finally:
                    self._active.discard(lease.job.id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._emit("error", message=str(exc))
                if self._config.error_backoff_seconds:
                    await asyncio.sleep(self._config.error_backoff_seconds)

    async def _heartbeat(
        self,
        lease_holder: list[JobLease],
        execution: asyncio.Task[JobResult],
    ) -> None:
        while not execution.done():
            await asyncio.sleep(self._config.heartbeat_seconds)
            if execution.done():
                return
            lease = lease_holder[0]
            if await self._store.cancel_requested(lease.job.id):
                execution.cancel()
                return
            renewed = await self._queue.heartbeat(
                lease,
                lease_seconds=self._config.lease_seconds,
            )
            lease_holder[0] = renewed
            await self._emit("heartbeat", job=lease.job)

    async def _cancelled_result(self, job: JobRequest) -> JobResult:
        return JobResult(
            job_id=job.id,
            status="cancelled",
            error="cancellation requested",
        )

    async def _process(self, lease: JobLease) -> None:
        job = lease.job
        record, _ = await self._store.create(job)
        if record.terminal:
            await self._queue.acknowledge(lease)
            await self._emit("duplicate", job=job, message="terminal job redelivered")
            return
        if record.cancel_requested:
            result = await self._cancelled_result(job)
            await self._store.save_result(result)
            await self._queue.reject(lease, reason=result.error or "cancelled")
            self._failed += 1
            await self._emit("cancelled", job=job, message=result.error)
            return

        await self._store.mark_running(
            job,
            worker_id=lease.consumer,
            delivery_count=lease.delivery_count,
        )
        await self._emit("reserved", job=job, metadata={"consumer": lease.consumer})
        await self._emit("started", job=job)

        execution = asyncio.create_task(
            self._executor.execute(job),
            name=f"pyfetcher:job:{job.id}",
        )
        lease_holder = [lease]
        heartbeat = asyncio.create_task(
            self._heartbeat(lease_holder, execution),
            name=f"pyfetcher:heartbeat:{job.id}",
        )
        try:
            done, _ = await asyncio.wait(
                {execution, heartbeat},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if heartbeat in done:
                heartbeat_error = heartbeat.exception()
                if heartbeat_error is not None:
                    execution.cancel()
                    await asyncio.gather(execution, return_exceptions=True)
                    raise heartbeat_error
            try:
                result = await execution
            except asyncio.CancelledError:
                if await self._store.cancel_requested(job.id):
                    result = await self._cancelled_result(job)
                else:
                    raise
        except asyncio.CancelledError:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            raise
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

        should_retry = result.status in {"failed", "retry"} and (
            job.attempt < job.policy.max_attempts
        )
        if should_retry:
            delay = (
                result.retry_after_seconds
                if result.retry_after_seconds is not None
                else job.policy.retry_backoff_seconds * (2 ** (job.attempt - 1))
            )
            next_job = job.next_attempt()
            await self._store.mark_retry(next_job, result)
            await self._queue.retry(lease_holder[0], delay_seconds=delay)
            self._retried += 1
            await self._emit(
                "retried",
                job=next_job,
                message=result.error,
                metadata={"delay_seconds": delay},
            )
            return

        if result.status == "succeeded" and result.spawned_jobs:
            children = tuple(
                child.model_copy(
                    update={
                        "run_id": job.run_id,
                        "parent_job_id": child.parent_job_id or job.id,
                        "idempotency_key": child.idempotency_key or f"spawn:{job.id}:{index}",
                    }
                )
                for index, child in enumerate(result.spawned_jobs)
            )
            for child in children:
                await self._service.submit(child)
            result = result.model_copy(update={"spawned_jobs": children})

        await self._store.save_result(result)
        if result.status == "succeeded":
            await self._queue.acknowledge(lease_holder[0])
            self._completed += 1
            await self._emit("succeeded", job=job)
        else:
            await self._queue.reject(
                lease_holder[0],
                reason=result.error or result.status,
            )
            self._failed += 1
            kind: WorkerEventKind = "cancelled" if result.status == "cancelled" else "failed"
            await self._emit(kind, job=job, message=result.error)

    async def aclose(self) -> None:
        await self.stop()

    async def __aenter__(self) -> JobWorker:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.stop()


__all__ = [
    "JobWorker",
    "WorkerConfig",
    "WorkerEvent",
    "WorkerEventKind",
    "WorkerEventSink",
    "WorkerSnapshot",
]
