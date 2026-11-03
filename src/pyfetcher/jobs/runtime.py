"""Bounded in-process runtime for dynamic job-template flows.

Purpose:
    Provide a runnable reference implementation and testing target for the same
    job contracts used by durable and distributed adapters.

Design:
    Workers consume an at-least-once :class:`JobQueue`. Successful templates
    may spawn child jobs, enabling pagination and collection expansion without
    requiring a static DAG.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from pyfetcher.jobs.models import FlowRequest, FlowResult, JobResult
from pyfetcher.jobs.queue import InMemoryJobQueue, JobQueue
from pyfetcher.jobs.registry import JobExecutor


class InProcessJobRuntime:
    """Execute a dynamic flow with bounded local worker concurrency."""

    def __init__(
        self,
        executor: JobExecutor,
        *,
        queue: JobQueue | None = None,
    ) -> None:
        self._executor = executor
        self._queue = queue or InMemoryJobQueue()
        self._owns_queue = queue is None

    async def run(self, flow: FlowRequest) -> FlowResult:
        """Run initial and dynamically spawned jobs to terminal states."""
        started_at = datetime.now(UTC)
        results: list[JobResult] = []
        submitted = 0
        pending = 0
        condition = asyncio.Condition()
        aborting = False
        limit_exceeded = False

        async def submit(job) -> bool:
            nonlocal limit_exceeded, pending, submitted
            async with condition:
                if submitted >= flow.max_jobs:
                    limit_exceeded = True
                    return False
                accepted = await self._queue.enqueue(job.model_copy(update={"run_id": flow.id}))
                if accepted:
                    pending += 1
                    submitted += 1
                    condition.notify_all()
                return accepted

        for job in flow.jobs:
            await submit(job)

        if pending == 0:
            return FlowResult(
                flow_id=flow.id,
                name=flow.name,
                status="succeeded",
                results=(),
                submitted_jobs=0,
                succeeded_jobs=0,
                failed_jobs=0,
                started_at=started_at,
            )

        async def worker(index: int) -> None:
            nonlocal aborting, pending
            consumer = f"local-{index}"
            while True:
                async with condition:
                    if pending == 0:
                        return
                lease = await self._queue.reserve(consumer, timeout_seconds=0.1)
                if lease is None:
                    continue
                if aborting:
                    await self._queue.reject(lease, reason="flow stopped after an earlier failure")
                    results.append(
                        JobResult(
                            job_id=lease.job.id,
                            status="cancelled",
                            error="flow stopped after an earlier failure",
                        )
                    )
                    async with condition:
                        pending -= 1
                        condition.notify_all()
                    continue
                result = await self._executor.execute(lease.job)

                should_retry = result.status in {"failed", "retry"} and (
                    lease.job.attempt < lease.job.policy.max_attempts
                )
                if should_retry:
                    delay = (
                        result.retry_after_seconds
                        if result.retry_after_seconds is not None
                        else lease.job.policy.retry_backoff_seconds * (2 ** (lease.job.attempt - 1))
                    )
                    await self._queue.retry(lease, delay_seconds=delay)
                    continue

                if result.status in {"failed", "cancelled"}:
                    await self._queue.reject(lease, reason=result.error or result.status)
                else:
                    await self._queue.acknowledge(lease)

                if result.status == "succeeded" and not aborting:
                    for child in result.spawned_jobs:
                        child_job = child.model_copy(
                            update={
                                "run_id": flow.id,
                                "parent_job_id": child.parent_job_id or lease.job.id,
                            }
                        )
                        await submit(child_job)

                results.append(result)
                async with condition:
                    pending -= 1
                    if flow.fail_fast and result.status in {"failed", "cancelled"}:
                        aborting = True
                    condition.notify_all()

        workers = [asyncio.create_task(worker(index)) for index in range(flow.concurrency)]
        await asyncio.gather(*workers)

        failed = sum(result.status in {"failed", "cancelled"} for result in results)
        succeeded = sum(result.status == "succeeded" for result in results)
        return FlowResult(
            flow_id=flow.id,
            name=flow.name,
            status="failed" if failed or limit_exceeded else "succeeded",
            results=tuple(results),
            submitted_jobs=submitted,
            succeeded_jobs=succeeded,
            failed_jobs=failed,
            started_at=started_at,
        )

    async def aclose(self) -> None:
        """Close an internally owned queue."""
        if self._owns_queue:
            await self._queue.aclose()

    async def __aenter__(self) -> InProcessJobRuntime:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


__all__ = ["InProcessJobRuntime"]
