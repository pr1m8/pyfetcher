"""Optional FastAPI control-plane adapter for durable jobs.

The HTTP layer delegates all job semantics to :class:`JobService` and
:class:`JobWorker`. The same service contracts can back gRPC, MCP, or another
transport without duplicating queue and cancellation behavior.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import StreamingResponse
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError("job API support requires `pip install 'fetchkit[api]'`") from exc

from pyfetcher.jobs import (
    JobApplication,
    JobCancellation,
    JobNotFoundError,
    JobRecord,
    JobRecordPage,
    JobRecordStatus,
    JobRequest,
    JobServiceHealth,
    JobSubmission,
    TemplateDescriptor,
    WorkerSnapshot,
)
from pyfetcher.jobs.events import WorkerEventBroker


def create_job_api(
    application: JobApplication,
    *,
    title: str = "fetchkit job API",
    start_worker: bool = True,
    event_broker: WorkerEventBroker | None = None,
) -> FastAPI:
    """Create a lifecycle-aware HTTP adapter over one job application."""
    broker = event_broker or WorkerEventBroker()
    application.worker.add_event_sink(broker.publish)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if start_worker:
            await application.start()
        try:
            yield
        finally:
            await application.aclose()

    app = FastAPI(title=title, version="1", lifespan=lifespan)

    @app.get("/health", response_model=JobServiceHealth)
    async def health() -> JobServiceHealth:
        return await application.service.health()

    @app.get("/v1/worker", response_model=WorkerSnapshot)
    async def worker() -> WorkerSnapshot:
        return application.worker.snapshot()

    @app.get("/v1/templates", response_model=list[TemplateDescriptor])
    async def templates() -> tuple[TemplateDescriptor, ...]:
        return application.service.templates()

    @app.post("/v1/jobs", response_model=JobSubmission, status_code=202)
    async def submit(job: JobRequest) -> JobSubmission:
        return await application.service.submit(job)

    @app.get("/v1/jobs", response_model=JobRecordPage)
    async def list_jobs(
        status: JobRecordStatus | None = None,
        limit: int = Query(default=100, ge=1, le=1_000),
        offset: int = Query(default=0, ge=0),
    ) -> JobRecordPage:
        return await application.service.list_jobs(
            status=status,
            limit=limit,
            offset=offset,
        )

    @app.get("/v1/jobs/{job_id}", response_model=JobRecord)
    async def get_job(job_id: UUID) -> JobRecord:
        try:
            return await application.service.get(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.post("/v1/jobs/{job_id}/cancel", response_model=JobCancellation)
    async def cancel(job_id: UUID) -> JobCancellation:
        try:
            return await application.service.cancel(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.get("/v1/events")
    async def events(job_id: UUID | None = None) -> StreamingResponse:
        async def stream() -> AsyncIterator[str]:
            async for event in broker.subscribe(job_id=job_id):
                yield f"event: {event.kind}\ndata: {event.model_dump_json()}\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


__all__ = ["WorkerEventBroker", "create_job_api"]
