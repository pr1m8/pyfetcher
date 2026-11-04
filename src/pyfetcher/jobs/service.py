"""Transport-neutral durable job control plane.

Purpose:
    Give Python callers, HTTP APIs, CLIs, and gRPC adapters one service
    for submission, inspection, cancellation, queue health, and discovery.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from pyfetcher.jobs.models import JobRequest
from pyfetcher.jobs.queue import JobQueue, QueueStats
from pyfetcher.jobs.registry import TemplateDescriptor, TemplateRegistry
from pyfetcher.jobs.store import JobRecord, JobRecordStatus, JobStore


class JobNotFoundError(LookupError):
    """Raised when a control-plane operation targets an unknown job."""


class JobSubmission(BaseModel):
    """Result of submitting a job to the configured queue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    accepted: bool
    duplicate: bool = False
    record: JobRecord | None = None


class JobCancellation(BaseModel):
    """Result of requesting cooperative job cancellation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    accepted: bool
    record: JobRecord


class JobRecordPage(BaseModel):
    """One bounded page of queryable job records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[JobRecord, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class JobServiceHealth(BaseModel):
    """Portable health snapshot for APIs and operational commands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = "ok"
    queue: QueueStats
    stored_jobs: int = Field(ge=0)


class JobControlPlane(Protocol):
    """Adapter surface shared by HTTP, gRPC, CLI, and application code."""

    async def submit(self, job: JobRequest) -> JobSubmission: ...

    async def get(self, job_id: UUID) -> JobRecord: ...

    async def cancel(self, job_id: UUID) -> JobCancellation: ...

    async def list_jobs(
        self,
        *,
        status: JobRecordStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> JobRecordPage: ...

    async def health(self) -> JobServiceHealth: ...

    def templates(self) -> tuple[TemplateDescriptor, ...]: ...


class JobService:
    """Coordinate a queue, status store, and template catalog."""

    def __init__(
        self,
        queue: JobQueue,
        store: JobStore,
        registry: TemplateRegistry,
    ) -> None:
        self.queue = queue
        self.store = store
        self.registry = registry

    async def submit(self, job: JobRequest) -> JobSubmission:
        """Persist submission state and enqueue one logical job."""
        record, created = await self.store.create(job)
        if not created:
            return JobSubmission(
                job_id=record.job.id,
                accepted=False,
                duplicate=True,
                record=record,
            )
        try:
            accepted = await self.queue.enqueue(job)
        except BaseException:
            await self.store.delete(job.id)
            raise
        if not accepted:
            await self.store.delete(job.id)
            return JobSubmission(job_id=job.id, accepted=False, duplicate=True)
        return JobSubmission(job_id=job.id, accepted=True, record=record)

    async def get(self, job_id: UUID) -> JobRecord:
        record = await self.store.get(job_id)
        if record is None:
            raise JobNotFoundError(str(job_id))
        return record

    async def cancel(self, job_id: UUID) -> JobCancellation:
        record = await self.store.request_cancel(job_id)
        if record is None:
            raise JobNotFoundError(str(job_id))
        return JobCancellation(
            job_id=job_id,
            accepted=record.cancel_requested and not record.terminal,
            record=record,
        )

    async def list_jobs(
        self,
        *,
        status: JobRecordStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> JobRecordPage:
        items = await self.store.list(status=status, limit=limit, offset=offset)
        return JobRecordPage(
            items=items,
            total=await self.store.count(status=status),
            limit=limit,
            offset=offset,
        )

    async def health(self) -> JobServiceHealth:
        return JobServiceHealth(
            queue=await self.queue.stats(),
            stored_jobs=await self.store.count(),
        )

    def templates(self) -> tuple[TemplateDescriptor, ...]:
        return self.registry.descriptors()


__all__ = [
    "JobCancellation",
    "JobControlPlane",
    "JobNotFoundError",
    "JobRecordPage",
    "JobService",
    "JobServiceHealth",
    "JobSubmission",
]
