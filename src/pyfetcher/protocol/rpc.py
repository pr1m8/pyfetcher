"""Transport-neutral RPC discovery contracts for fetchkit services.

JSON Schema remains the source of truth for request and response bodies. RPC
descriptors bind those contracts to stable method paths, while gRPC, HTTP, or
TypeScript adapters provide framing and lifecycle behavior.
"""

from __future__ import annotations

import re
from importlib.resources import files
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pyfetcher.jobs import JobRecordStatus, TemplateDescriptor

type RpcCardinality = Literal["unary", "server_stream"]

_SERVICE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*$")
_METHOD_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")


class JobLookupRequest(BaseModel):
    """Identify one job for inspection or cancellation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID


class JobListRequest(BaseModel):
    """Bounded job-status query shared by RPC and generated clients."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: JobRecordStatus | None = None
    limit: int = Field(default=100, ge=1, le=1_000)
    offset: int = Field(default=0, ge=0)


class WorkerEventSubscription(BaseModel):
    """Optional filter for a worker-event server stream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID | None = None


class TemplateCatalog(BaseModel):
    """Discoverable template descriptors returned by a control plane."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[TemplateDescriptor, ...]


class RpcMethod(BaseModel):
    """One RPC method bound to versioned JSON request and response contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    request_contract: str | None = None
    response_contract: str
    cardinality: RpcCardinality = "unary"
    description: str = ""

    @model_validator(mode="after")
    def _validate_name(self) -> RpcMethod:
        if _METHOD_PATTERN.fullmatch(self.name) is None:
            raise ValueError("RPC method names must use UpperCamelCase")
        return self


class RpcService(BaseModel):
    """Versioned service and its deterministic RPC method catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str = "1"
    methods: tuple[RpcMethod, ...]

    @model_validator(mode="after")
    def _validate_identity(self) -> RpcService:
        if _SERVICE_PATTERN.fullmatch(self.name) is None:
            raise ValueError("RPC service names must use dotted identifiers")
        if not self.version.strip():
            raise ValueError("RPC service version cannot be empty")
        names = [method.name for method in self.methods]
        if len(names) != len(set(names)):
            raise ValueError("RPC service contains duplicate method names")
        return self

    @property
    def key(self) -> str:
        """Return the versioned service discovery key."""
        return f"{self.name}@{self.version}"

    def method_path(self, method: RpcMethod | str) -> str:
        """Return the canonical gRPC path for one declared method."""
        name = method.name if isinstance(method, RpcMethod) else method
        if name not in {item.name for item in self.methods}:
            raise KeyError(f"unknown RPC method: {self.name}/{name}")
        return f"/{self.name}/{name}"


JOB_CONTROL_PLANE_SERVICE = RpcService(
    name="fetchkit.jobs.v1.JobControlPlane",
    methods=(
        RpcMethod(
            name="Submit",
            request_contract="job.request@1",
            response_contract="job.submission@1",
            description="Submit one versioned job request.",
        ),
        RpcMethod(
            name="Get",
            request_contract="rpc.job_lookup@1",
            response_contract="job.record@1",
            description="Inspect one logical job.",
        ),
        RpcMethod(
            name="List",
            request_contract="rpc.job_list@1",
            response_contract="job.record_page@1",
            description="List a bounded page of job records.",
        ),
        RpcMethod(
            name="Cancel",
            request_contract="rpc.job_lookup@1",
            response_contract="job.cancellation@1",
            description="Request cooperative cancellation.",
        ),
        RpcMethod(
            name="Health",
            response_contract="job.service_health@1",
            description="Read queue and job-store health.",
        ),
        RpcMethod(
            name="Templates",
            response_contract="rpc.template_catalog@1",
            description="Discover registered template versions.",
        ),
        RpcMethod(
            name="Worker",
            response_contract="job.worker_snapshot@1",
            description="Read the local worker snapshot.",
        ),
        RpcMethod(
            name="WatchEvents",
            request_contract="rpc.worker_event_subscription@1",
            response_contract="job.worker_event@1",
            cardinality="server_stream",
            description="Stream bounded in-process worker events.",
        ),
    ),
)


def grpc_proto_text() -> str:
    """Read the packaged gRPC transport definition."""
    resource = files("pyfetcher.protocol").joinpath(
        "proto",
        "fetchkit",
        "jobs",
        "v1",
        "jobs.proto",
    )
    return resource.read_text(encoding="utf-8")


def export_grpc_proto(destination: str | Path) -> Path:
    """Write the packaged job-control-plane ``.proto`` file atomically."""
    target = Path(destination)
    if target.exists() and target.is_dir():
        target = target / "jobs.proto"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(grpc_proto_text(), encoding="utf-8")
    temporary.replace(target)
    return target


__all__ = [
    "JOB_CONTROL_PLANE_SERVICE",
    "JobListRequest",
    "JobLookupRequest",
    "RpcCardinality",
    "RpcMethod",
    "RpcService",
    "TemplateCatalog",
    "WorkerEventSubscription",
    "export_grpc_proto",
    "grpc_proto_text",
]
