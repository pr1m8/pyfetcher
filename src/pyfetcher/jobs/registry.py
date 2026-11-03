"""Job-template registration, dependency context, and execution."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from pyfetcher.artifacts.store import BlobStore
from pyfetcher.jobs.models import JobRequest, JobResult, TemplateRef

type JobExecutionHook = Callable[
    [JobRequest, Callable[[JobRequest], Awaitable[JobResult]]],
    Awaitable[JobResult],
]


@dataclass(frozen=True, slots=True)
class JobContext:
    """Runtime-only dependencies that never enter serialized job payloads."""

    services: Mapping[str, object] = field(default_factory=dict)
    blob_store: BlobStore | None = None

    def require(self, name: str) -> object:
        """Return a named runtime service or raise an actionable error."""
        try:
            return self.services[name]
        except KeyError as exc:
            raise RuntimeError(f"job template requires runtime service {name!r}") from exc


class JobTemplate(Protocol):
    """Executable implementation for one stable template revision."""

    name: str
    version: str
    input_model: type[BaseModel]

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult: ...


class TemplateDescriptor(BaseModel):
    """Discoverable template metadata for APIs, CLIs, and worker catalogs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: TemplateRef
    description: str
    category: str
    input_schema: dict[str, Any]


class TemplateRegistry:
    """Process-local allowlist mapping serialized refs to implementations."""

    def __init__(self) -> None:
        self._templates: dict[str, JobTemplate] = {}
        self._descriptors: dict[str, TemplateDescriptor] = {}

    def register(
        self,
        template: JobTemplate,
        *,
        description: str = "",
        category: str = "custom",
        input_schema: dict[str, Any] | None = None,
        replace: bool = False,
    ) -> TemplateRef:
        """Register an executable template and return its serializable ref."""
        ref = TemplateRef(name=template.name, version=template.version)
        if ref.key in self._templates and not replace:
            raise ValueError(f"job template already registered: {ref.key}")
        self._templates[ref.key] = template
        self._descriptors[ref.key] = TemplateDescriptor(
            ref=ref,
            description=description,
            category=category,
            input_schema=input_schema or {},
        )
        return ref

    def resolve(self, ref: TemplateRef) -> JobTemplate:
        """Resolve only explicitly registered template implementations."""
        try:
            return self._templates[ref.key]
        except KeyError as exc:
            choices = ", ".join(sorted(self._templates)) or "none"
            raise KeyError(f"unknown job template {ref.key!r}; registered: {choices}") from exc

    def descriptors(self) -> tuple[TemplateDescriptor, ...]:
        """Return registered templates in stable key order."""
        return tuple(self._descriptors[key] for key in sorted(self._descriptors))

    def validate_payload(self, ref: TemplateRef, payload: object) -> BaseModel | None:
        """Validate a payload when the registered template declares a model."""
        template = self.resolve(ref)
        model = getattr(template, "input_model", None)
        return model.model_validate(payload) if model is not None else None


class JobExecutor:
    """Execute registered templates with shared context and async hooks."""

    def __init__(
        self,
        registry: TemplateRegistry,
        *,
        context: JobContext | None = None,
        hooks: tuple[JobExecutionHook, ...] = (),
    ) -> None:
        self._registry = registry
        self._context = context or JobContext()
        self._hooks = hooks

    async def execute(self, job: JobRequest) -> JobResult:
        """Execute one job and normalize uncaught template failures."""

        async def invoke(value: JobRequest) -> JobResult:
            started = datetime.now(UTC)
            try:
                result = await self._registry.resolve(value.template).execute(
                    value,
                    self._context,
                )
            except Exception as exc:
                return JobResult.failed(value, str(exc), started_at=started)
            if result.job_id != value.id:
                return JobResult.failed(
                    value,
                    "job template returned a result for a different job ID",
                    started_at=started,
                )
            return result

        handler = invoke
        for hook in reversed(self._hooks):
            call_next = handler

            async def handler(
                value: JobRequest,
                *,
                _hook: JobExecutionHook = hook,
                _next: Callable[[JobRequest], Awaitable[JobResult]] = call_next,
            ) -> JobResult:
                return await _hook(value, _next)

        if job.policy.timeout_seconds is None:
            return await handler(job)
        started = datetime.now(UTC)
        try:
            async with asyncio.timeout(job.policy.timeout_seconds):
                return await handler(job)
        except TimeoutError:
            return JobResult.failed(
                job,
                f"job timed out after {job.policy.timeout_seconds:g} seconds",
                started_at=started,
            )


__all__ = [
    "JobContext",
    "JobExecutionHook",
    "JobExecutor",
    "JobTemplate",
    "TemplateDescriptor",
    "TemplateRegistry",
]
