"""Durable, mechanism-neutral job and flow contracts.

Purpose:
    Describe crawl, scrape, pagination, search, and acquisition work in a form
    that can be serialized into Postgres, Redis Streams, Temporal histories,
    RPC requests, or local files.

Design:
    Jobs name a versioned template instead of serializing Python callables.
    Large values are represented by artifact references. Runtime services and
    credentials are injected separately through :class:`JobContext`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from pyfetcher.artifacts.models import ArtifactCollection, ArtifactRef

type JobStatus = Literal["succeeded", "failed", "retry", "cancelled"]


class TemplateRef(BaseModel):
    """Stable name and revision of a registered executable job template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str = "1"

    @field_validator("name", "version")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("template name and version cannot be empty")
        return normalized

    @property
    def key(self) -> str:
        """Return the registry key for this revision."""
        return f"{self.name}@{self.version}"


class JobPolicy(BaseModel):
    """Portable execution policy shared across queue and workflow runtimes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    priority: int = 0
    max_attempts: int = Field(default=3, ge=1)
    timeout_seconds: float | None = Field(default=None, gt=0)
    retry_backoff_seconds: float = Field(default=1.0, ge=0)
    queue: str = "default"


class JobTraceContext(BaseModel):
    """W3C propagation values carried without importing OpenTelemetry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    traceparent: str | None = None
    tracestate: str | None = None
    baggage: dict[str, str] = Field(default_factory=dict)


class JobRequest(BaseModel):
    """Serializable request for one versioned job template invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    template: TemplateRef
    target: str | None = None
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    artifacts: tuple[ArtifactRef, ...] = ()
    policy: JobPolicy = Field(default_factory=JobPolicy)
    run_id: UUID = Field(default_factory=uuid4)
    parent_job_id: UUID | None = None
    idempotency_key: str | None = None
    attempt: int = Field(default=1, ge=1)
    trace: JobTraceContext = Field(default_factory=JobTraceContext)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def next_attempt(self) -> JobRequest:
        """Return the same logical job with an incremented delivery attempt."""
        return self.model_copy(update={"attempt": self.attempt + 1})


class JobResult(BaseModel):
    """Normalized output from any crawl, scrape, discovery, or media job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    status: JobStatus
    output: dict[str, JsonValue] = Field(default_factory=dict)
    artifacts: tuple[ArtifactRef, ...] = ()
    collections: tuple[ArtifactCollection, ...] = ()
    spawned_jobs: tuple[JobRequest, ...] = ()
    error: str | None = None
    retry_after_seconds: float | None = Field(default=None, ge=0)
    metrics: dict[str, float | int] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def succeeded(
        cls,
        job: JobRequest,
        *,
        output: dict[str, JsonValue] | None = None,
        artifacts: tuple[ArtifactRef, ...] = (),
        collections: tuple[ArtifactCollection, ...] = (),
        spawned_jobs: tuple[JobRequest, ...] = (),
        metrics: dict[str, float | int] | None = None,
        started_at: datetime | None = None,
    ) -> JobResult:
        """Build a successful result for ``job``."""
        return cls(
            job_id=job.id,
            status="succeeded",
            output=output or {},
            artifacts=artifacts,
            collections=collections,
            spawned_jobs=spawned_jobs,
            metrics=metrics or {},
            started_at=started_at or datetime.now(UTC),
        )

    @classmethod
    def failed(
        cls,
        job: JobRequest,
        error: str,
        *,
        started_at: datetime | None = None,
    ) -> JobResult:
        """Build a failed result for ``job``."""
        return cls(
            job_id=job.id,
            status="failed",
            error=error,
            started_at=started_at or datetime.now(UTC),
        )


class FlowRequest(BaseModel):
    """Initial jobs and bounds for one dynamically expanding flow run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    name: str
    version: str = "1"
    jobs: tuple[JobRequest, ...]
    concurrency: int = Field(default=10, ge=1)
    max_jobs: int = Field(default=10_000, ge=1)
    fail_fast: bool = False
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class FlowResult(BaseModel):
    """Terminal snapshot of an in-process or durable flow execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    flow_id: UUID
    name: str
    status: Literal["succeeded", "failed", "cancelled"]
    results: tuple[JobResult, ...]
    submitted_jobs: int = Field(ge=0)
    succeeded_jobs: int = Field(ge=0)
    failed_jobs: int = Field(ge=0)
    started_at: datetime
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


__all__ = [
    "FlowRequest",
    "FlowResult",
    "JobPolicy",
    "JobRequest",
    "JobResult",
    "JobStatus",
    "JobTraceContext",
    "TemplateRef",
]
