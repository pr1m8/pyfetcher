"""Optional Temporal durable runtime for fetchkit job flows.

The workflow contains only deterministic scheduling. Fetching, parsing,
downloading, and blob I/O execute inside activities through ``JobExecutor``.
This keeps the same serialized jobs usable by local and Redis runtimes while
allowing Temporal to persist orchestration state and resume after failures.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import timedelta

try:
    from temporalio import activity, workflow
    from temporalio.client import Client
    from temporalio.client import Interceptor as ClientInterceptor
    from temporalio.common import RetryPolicy
    from temporalio.contrib.pydantic import pydantic_data_converter
    from temporalio.worker import Interceptor as WorkerInterceptor
    from temporalio.worker import Worker
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError("Temporal support requires `pip install 'fetchkit[temporal]'`") from exc

with workflow.unsafe.imports_passed_through():
    from pyfetcher.jobs.models import FlowRequest, FlowResult, JobRequest, JobResult
    from pyfetcher.jobs.registry import JobExecutor


class TemporalActivities:
    """Worker-side activity collection bound to one configured executor."""

    def __init__(self, executor: JobExecutor, *, heartbeat_seconds: float = 10.0) -> None:
        self._executor = executor
        self._heartbeat_seconds = heartbeat_seconds

    @activity.defn(name="fetchkit.execute_job")
    async def execute_job(self, job: JobRequest) -> JobResult:
        """Execute one job outside workflow replay and heartbeat while active."""
        activity.heartbeat({"job_id": str(job.id), "attempt": job.attempt})

        async def heartbeat() -> None:
            while True:
                await asyncio.sleep(self._heartbeat_seconds)
                activity.heartbeat({"job_id": str(job.id), "attempt": job.attempt})

        task = asyncio.create_task(heartbeat())
        try:
            return await self._executor.execute(job)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@workflow.defn(name="fetchkit.flow")
class FetchkitFlowWorkflow:
    """Deterministic, bounded, dynamically expanding durable flow."""

    @workflow.run
    async def run(self, flow: FlowRequest) -> FlowResult:
        started_at = workflow.now()
        pending = [job.model_copy(update={"run_id": flow.id}) for job in flow.jobs]
        results: list[JobResult] = []
        submitted = len(pending)
        limit_exceeded = submitted > flow.max_jobs
        if limit_exceeded:
            pending = pending[: flow.max_jobs]
            submitted = flow.max_jobs
        aborting = False

        while pending and not aborting:
            batch, pending = pending[: flow.concurrency], pending[flow.concurrency :]
            operations = [
                workflow.execute_activity(
                    "fetchkit.execute_job",
                    job,
                    result_type=JobResult,
                    start_to_close_timeout=timedelta(seconds=job.policy.timeout_seconds or 3_600),
                    heartbeat_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                    activity_id=f"{job.id}-{job.attempt}",
                )
                for job in batch
            ]
            batch_results = await asyncio.gather(*operations)
            for job, result in zip(batch, batch_results, strict=True):
                if result.status in {"failed", "retry"} and (job.attempt < job.policy.max_attempts):
                    delay = (
                        result.retry_after_seconds
                        if result.retry_after_seconds is not None
                        else job.policy.retry_backoff_seconds * (2 ** (job.attempt - 1))
                    )
                    if delay:
                        await workflow.sleep(delay)
                    pending.append(job.next_attempt())
                    continue

                results.append(result)
                if flow.fail_fast and result.status in {"failed", "cancelled"}:
                    aborting = True
                    continue
                if result.status != "succeeded" or aborting:
                    continue
                for child in result.spawned_jobs:
                    if submitted >= flow.max_jobs:
                        limit_exceeded = True
                        break
                    pending.append(
                        child.model_copy(
                            update={
                                "run_id": flow.id,
                                "parent_job_id": child.parent_job_id or job.id,
                            }
                        )
                    )
                    submitted += 1

        failed = sum(result.status in {"failed", "cancelled"} for result in results)
        succeeded = sum(result.status == "succeeded" for result in results)
        return FlowResult(
            flow_id=flow.id,
            name=flow.name,
            status="failed" if failed or aborting or limit_exceeded else "succeeded",
            results=tuple(results),
            submitted_jobs=submitted,
            succeeded_jobs=succeeded,
            failed_jobs=failed,
            started_at=started_at,
            completed_at=workflow.now(),
        )


class TemporalJobRuntime:
    """Client-side runtime that starts and awaits a durable flow workflow."""

    def __init__(
        self,
        client: Client,
        *,
        task_queue: str = "fetchkit",
        workflow_id_prefix: str = "fetchkit-flow",
    ) -> None:
        self._client = client
        self._task_queue = task_queue
        self._workflow_id_prefix = workflow_id_prefix

    async def run(self, flow: FlowRequest) -> FlowResult:
        handle = await self._client.start_workflow(
            FetchkitFlowWorkflow.run,
            flow,
            id=f"{self._workflow_id_prefix}-{flow.id}",
            task_queue=self._task_queue,
            result_type=FlowResult,
        )
        return await handle.result()


async def connect_temporal(
    target: str,
    *,
    namespace: str = "default",
    interceptors: Sequence[ClientInterceptor] = (),
) -> Client:
    """Connect with fetchkit's Pydantic job/flow data converter."""
    return await Client.connect(
        target,
        namespace=namespace,
        data_converter=pydantic_data_converter,
        interceptors=interceptors,
    )


def build_temporal_worker(
    client: Client,
    executor: JobExecutor,
    *,
    task_queue: str = "fetchkit",
    interceptors: Sequence[WorkerInterceptor] = (),
) -> Worker:
    """Build a worker; the application owns running and shutting it down."""
    activities = TemporalActivities(executor)
    return Worker(
        client,
        task_queue=task_queue,
        workflows=[FetchkitFlowWorkflow],
        activities=[activities.execute_job],
        interceptors=interceptors,
    )


def temporal_tracing_interceptor():
    """Return Temporal's OpenTelemetry interceptor using the global tracer."""
    try:
        from temporalio.contrib.opentelemetry import TracingInterceptor
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Temporal tracing requires `pip install 'fetchkit[temporal,observe]'`"
        ) from exc
    return TracingInterceptor()


__all__ = [
    "FetchkitFlowWorkflow",
    "TemporalActivities",
    "TemporalJobRuntime",
    "build_temporal_worker",
    "connect_temporal",
    "pydantic_data_converter",
    "temporal_tracing_interceptor",
]
