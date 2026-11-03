"""Tests for the transport-neutral job service and worker host."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from pyfetcher.jobs import (
    JobApplication,
    JobContext,
    JobPolicy,
    JobRequest,
    JobResult,
    TemplateRef,
    TemplateRegistry,
    WorkerConfig,
    WorkerEvent,
)


class ValueTemplate:
    name = "test.value"
    version = "1"

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        self.calls += 1
        return JobResult.succeeded(job, output={"value": job.payload.get("value")})


class FanoutTemplate:
    name = "test.fanout"
    version = "1"

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        children = tuple(
            JobRequest(
                template=TemplateRef(name="test.value"),
                payload={"value": index},
            )
            for index in range(int(job.payload.get("count", 0)))
        )
        return JobResult.succeeded(job, spawned_jobs=children)


class RetryTemplate:
    name = "test.retry"
    version = "1"

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        if job.attempt == 1:
            return JobResult.failed(job, "retry me")
        return JobResult.succeeded(job, output={"attempt": job.attempt})


class BlockingTemplate:
    name = "test.blocking"
    version = "1"

    def __init__(self, started: asyncio.Event) -> None:
        self._started = started

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        self._started.set()
        await asyncio.Event().wait()
        return JobResult.succeeded(job)


class ShutdownTemplate:
    name = "test.shutdown"
    version = "1"

    def __init__(self, started: asyncio.Event, stopped: asyncio.Event) -> None:
        self._started = started
        self._stopped = stopped

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        self._started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self._stopped.set()
        return JobResult.succeeded(job)


def _application(
    *templates: object,
    event_sink: Callable[[WorkerEvent], None] | None = None,
) -> JobApplication:
    registry = TemplateRegistry()
    for template in templates:
        registry.register(template)  # type: ignore[arg-type]
    return JobApplication.create(
        registry=registry,
        worker_config=WorkerConfig(
            name="test-worker",
            concurrency=2,
            reserve_timeout_seconds=0.01,
            lease_seconds=0.2,
            heartbeat_seconds=0.01,
            error_backoff_seconds=0,
        ),
        event_sinks=(event_sink,) if event_sink is not None else (),
    )


async def _wait_for_status(application: JobApplication, job_id, status: str):
    async with asyncio.timeout(2):
        while True:
            record = await application.service.get(job_id)
            if record.status == status:
                return record
            await asyncio.sleep(0.005)


async def test_service_deduplicates_by_idempotency_key() -> None:
    application = _application(ValueTemplate())
    first = JobRequest(
        template=TemplateRef(name="test.value"),
        idempotency_key="stable-key",
    )
    second = JobRequest(
        template=TemplateRef(name="test.value"),
        idempotency_key="stable-key",
    )

    submitted = await application.service.submit(first)
    duplicate = await application.service.submit(second)

    assert submitted.accepted is True
    assert duplicate.accepted is False
    assert duplicate.duplicate is True
    assert duplicate.job_id == first.id
    await application.aclose()


async def test_worker_retries_and_submits_idempotent_children() -> None:
    events: list[WorkerEvent] = []
    value = ValueTemplate()
    application = _application(value, FanoutTemplate(), RetryTemplate(), event_sink=events.append)
    fanout = JobRequest(
        template=TemplateRef(name="test.fanout"),
        payload={"count": 3},
    )
    retry = JobRequest(
        template=TemplateRef(name="test.retry"),
        policy=JobPolicy(max_attempts=2, retry_backoff_seconds=0),
    )

    async with application:
        await application.service.submit(fanout)
        await application.service.submit(retry)
        fanout_record = await _wait_for_status(application, fanout.id, "succeeded")
        retry_record = await _wait_for_status(application, retry.id, "succeeded")
        async with asyncio.timeout(2):
            while (await application.store.count()) < 5:
                await asyncio.sleep(0.005)
        async with asyncio.timeout(2):
            while value.calls < 3:
                await asyncio.sleep(0.005)

    assert len(fanout_record.result.spawned_jobs) == 3  # type: ignore[union-attr]
    assert all(
        child.idempotency_key == f"spawn:{fanout.id}:{index}"
        for index, child in enumerate(fanout_record.result.spawned_jobs)  # type: ignore[union-attr]
    )
    assert retry_record.result.output["attempt"] == 2  # type: ignore[union-attr]
    assert any(event.kind == "retried" for event in events)
    assert application.worker.snapshot().retried_jobs == 1


async def test_worker_event_sink_failure_does_not_interrupt_execution() -> None:
    def broken_sink(event: WorkerEvent) -> None:
        raise RuntimeError(f"cannot publish {event.kind}")

    application = _application(ValueTemplate(), event_sink=broken_sink)
    job = JobRequest(template=TemplateRef(name="test.value"))

    async with application:
        await application.service.submit(job)
        record = await _wait_for_status(application, job.id, "succeeded")

    assert record.result is not None
    assert record.result.status == "succeeded"


async def test_worker_honors_running_job_cancellation() -> None:
    started = asyncio.Event()
    application = _application(BlockingTemplate(started))
    job = JobRequest(template=TemplateRef(name="test.blocking"))

    async with application:
        await application.service.submit(job)
        await asyncio.wait_for(started.wait(), timeout=1)
        cancellation = await application.service.cancel(job.id)
        record = await _wait_for_status(application, job.id, "cancelled")

    assert cancellation.accepted is True
    assert record.result is not None
    assert record.result.status == "cancelled"


async def test_terminal_redelivery_is_acknowledged_without_reexecution() -> None:
    value = ValueTemplate()
    application = _application(value)
    job = JobRequest(template=TemplateRef(name="test.value"))

    async with application:
        await application.service.submit(job)
        await _wait_for_status(application, job.id, "succeeded")
        await application.queue.enqueue(job)
        async with asyncio.timeout(2):
            while (await application.queue.stats()).completed < 2:
                await asyncio.sleep(0.005)

    assert value.calls == 1


async def test_worker_bounds_graceful_shutdown_and_cancels_execution() -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()
    registry = TemplateRegistry()
    registry.register(ShutdownTemplate(started, stopped))  # type: ignore[arg-type]
    application = JobApplication.create(
        registry=registry,
        worker_config=WorkerConfig(
            concurrency=1,
            reserve_timeout_seconds=0.01,
            lease_seconds=1,
            heartbeat_seconds=0.1,
            error_backoff_seconds=0,
            shutdown_grace_seconds=0.01,
        ),
    )
    job = JobRequest(template=TemplateRef(name="test.shutdown"))

    await application.start()
    await application.service.submit(job)
    await asyncio.wait_for(started.wait(), timeout=1)
    await application.aclose()

    assert stopped.is_set()
    assert application.closed is True
    assert application.worker.snapshot().status == "stopped"


async def test_service_health_and_record_paging() -> None:
    application = _application(ValueTemplate())
    jobs = [JobRequest(template=TemplateRef(name="test.value")) for _ in range(3)]
    for job in jobs:
        await application.service.submit(job)

    page = await application.service.list_jobs(limit=2, offset=1)
    health = await application.service.health()

    assert page.total == 3
    assert len(page.items) == 2
    assert health.status == "ok"
    assert health.stored_jobs == 3
    assert health.queue.queued == 3
    await application.aclose()
