"""Portable job status and result storage.

Purpose:
    Separate queue delivery from queryable job state so workers, APIs, CLIs,
    and future RPC adapters share one control-plane view.

Design:
    A queue owns delivery and leases. A :class:`JobStore` owns status,
    cancellation intent, and terminal results. The in-memory implementation is
    intended for tests and single-process applications; distributed workers
    should inject a durable implementation.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from pyfetcher.jobs.models import JobRequest, JobResult

type JobRecordStatus = Literal[
    "queued",
    "running",
    "retrying",
    "succeeded",
    "failed",
    "cancelled",
]

TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


class JobRecord(BaseModel):
    """Queryable state for one logical job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job: JobRequest
    status: JobRecordStatus = "queued"
    result: JobResult | None = None
    worker_id: str | None = None
    delivery_count: int = Field(default=0, ge=0)
    cancel_requested: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def terminal(self) -> bool:
        """Return whether no further execution is expected."""
        return self.status in TERMINAL_JOB_STATUSES


class JobStore(Protocol):
    """Status, cancellation, and result-store contract."""

    async def create(self, job: JobRequest) -> tuple[JobRecord, bool]: ...

    async def get(self, job_id: UUID) -> JobRecord | None: ...

    async def list(
        self,
        *,
        status: JobRecordStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[JobRecord, ...]: ...

    async def count(self, *, status: JobRecordStatus | None = None) -> int: ...

    async def mark_running(
        self,
        job: JobRequest,
        *,
        worker_id: str,
        delivery_count: int,
    ) -> JobRecord: ...

    async def mark_retry(
        self,
        job: JobRequest,
        result: JobResult,
    ) -> JobRecord: ...

    async def save_result(self, result: JobResult) -> JobRecord: ...

    async def request_cancel(self, job_id: UUID) -> JobRecord | None: ...

    async def cancel_requested(self, job_id: UUID) -> bool: ...

    async def delete(self, job_id: UUID) -> None: ...

    async def aclose(self) -> None: ...


class InMemoryJobStore:
    """Concurrency-safe local status and result store."""

    def __init__(self) -> None:
        self._records: dict[UUID, JobRecord] = {}
        self._idempotency: dict[str, UUID] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: JobRequest) -> tuple[JobRecord, bool]:
        async with self._lock:
            existing = self._records.get(job.id)
            if existing is not None:
                return existing, False
            if job.idempotency_key is not None:
                existing_id = self._idempotency.get(job.idempotency_key)
                if existing_id is not None:
                    return self._records[existing_id], False
            record = JobRecord(job=job)
            self._records[job.id] = record
            if job.idempotency_key is not None:
                self._idempotency[job.idempotency_key] = job.id
            return record, True

    async def get(self, job_id: UUID) -> JobRecord | None:
        async with self._lock:
            return self._records.get(job_id)

    async def list(
        self,
        *,
        status: JobRecordStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[JobRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        async with self._lock:
            records = (
                record
                for record in self._records.values()
                if status is None or record.status == status
            )
            ordered = sorted(records, key=lambda item: item.created_at, reverse=True)
            return tuple(ordered[offset : offset + limit])

    async def count(self, *, status: JobRecordStatus | None = None) -> int:
        async with self._lock:
            return sum(
                status is None or record.status == status for record in self._records.values()
            )

    def _require(self, job_id: UUID) -> JobRecord:
        try:
            return self._records[job_id]
        except KeyError as exc:
            raise KeyError(f"unknown job record: {job_id}") from exc

    async def mark_running(
        self,
        job: JobRequest,
        *,
        worker_id: str,
        delivery_count: int,
    ) -> JobRecord:
        now = datetime.now(UTC)
        async with self._lock:
            current = self._require(job.id)
            updated = current.model_copy(
                update={
                    "job": job,
                    "status": "running",
                    "worker_id": worker_id,
                    "delivery_count": delivery_count,
                    "updated_at": now,
                    "started_at": current.started_at or now,
                }
            )
            self._records[job.id] = updated
            return updated

    async def mark_retry(self, job: JobRequest, result: JobResult) -> JobRecord:
        async with self._lock:
            current = self._require(job.id)
            updated = current.model_copy(
                update={
                    "job": job,
                    "status": "retrying",
                    "result": result,
                    "worker_id": None,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._records[job.id] = updated
            return updated

    async def save_result(self, result: JobResult) -> JobRecord:
        status: JobRecordStatus = "failed" if result.status == "retry" else result.status
        now = datetime.now(UTC)
        async with self._lock:
            current = self._require(result.job_id)
            updated = current.model_copy(
                update={
                    "status": status,
                    "result": result,
                    "updated_at": now,
                    "completed_at": now,
                }
            )
            self._records[result.job_id] = updated
            return updated

    async def request_cancel(self, job_id: UUID) -> JobRecord | None:
        async with self._lock:
            current = self._records.get(job_id)
            if current is None or current.terminal:
                return current
            updated = current.model_copy(
                update={"cancel_requested": True, "updated_at": datetime.now(UTC)}
            )
            self._records[job_id] = updated
            return updated

    async def cancel_requested(self, job_id: UUID) -> bool:
        async with self._lock:
            current = self._records.get(job_id)
            return current.cancel_requested if current is not None else False

    async def delete(self, job_id: UUID) -> None:
        async with self._lock:
            current = self._records.pop(job_id, None)
            if current is not None and current.job.idempotency_key is not None:
                self._idempotency.pop(current.job.idempotency_key, None)

    async def aclose(self) -> None:
        """Close the store; in-memory state needs no external cleanup."""
        return None


__all__ = [
    "InMemoryJobStore",
    "JobRecord",
    "JobRecordStatus",
    "JobStore",
    "TERMINAL_JOB_STATUSES",
]
