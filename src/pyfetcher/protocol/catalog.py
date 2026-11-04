"""Versioned, machine-readable contracts for cross-language integrations.

Purpose:
    Export fetchkit's portable Pydantic models as a deterministic JSON Schema
    catalog that TypeScript, RPC, queue, and worker projects can consume.

Design:
    The catalog describes JSON-safe values only. Runtime clients, callables,
    credentials, byte iterators, and transport handles remain process-local.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from pyfetcher.acquisition import (
    AcquisitionEvent,
    AcquisitionProvenance,
    AcquisitionRequest,
    AcquisitionResult,
    AcquisitionService,
    ProviderCapabilities,
)
from pyfetcher.artifacts import ArtifactCollection, ArtifactMember, ArtifactRef, BlobRef
from pyfetcher.contracts import (
    URL,
    BatchFetchRequest,
    BatchFetchResponse,
    DomainParts,
    FetchRequest,
    FetchResponse,
    PoolPolicy,
    RetryPolicy,
    StreamChunk,
    StreamPolicy,
    TimeoutPolicy,
)
from pyfetcher.contracts.resource import MediaResource, WebPage, WebResource
from pyfetcher.contracts.response import BatchItemResponse
from pyfetcher.documents import (
    CollectionItem,
    CollectionRule,
    ExtractedCollection,
    ExtractedLink,
    GalleryRule,
    ImageCandidate,
    ImageRule,
    LinkRule,
    SelectorRule,
    SrcsetCandidate,
)
from pyfetcher.extraction import ExtractionResult
from pyfetcher.jobs import (
    FlowRequest,
    FlowResult,
    JobCancellation,
    JobLease,
    JobPolicy,
    JobRecord,
    JobRecordPage,
    JobRequest,
    JobResult,
    JobServiceHealth,
    JobSubmission,
    JobTraceContext,
    MediaAcquisitionInput,
    PaginationInput,
    QueueStats,
    SearchInput,
    TemplateDescriptor,
    TemplateRef,
    TemplateRegistry,
    WorkerConfig,
    WorkerEvent,
    WorkerSnapshot,
    register_builtin_templates,
)
from pyfetcher.media import (
    AudioStreamInfo,
    ImageInfo,
    ImageProcessingSpec,
    MediaMetadata,
    MediaProcessingResult,
    MediaProvenance,
    PixelDimensions,
    ThumbnailInfo,
    VideoStreamInfo,
)
from pyfetcher.metadata.models import FaviconLink, OpenGraphMetadata, PageMetadata
from pyfetcher.protocol.rpc import (
    JOB_CONTROL_PLANE_SERVICE,
    JobListRequest,
    JobLookupRequest,
    RpcService,
    TemplateCatalog,
    WorkerEventSubscription,
)
from pyfetcher.search import SearchHit, SearchRequest, SearchResult
from pyfetcher.streams import ByteStreamInfo

type ContractRole = Literal["input", "output", "event", "value", "policy"]

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
PROTOCOL_VERSION = "2"
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


def _package_version() -> str:
    try:
        return version("fetchkit")
    except PackageNotFoundError:  # pragma: no cover - source tree without metadata
        return "0+unknown"


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _description(model: type[BaseModel]) -> str:
    doc = (model.__doc__ or "").strip()
    return doc.split("\n\n", 1)[0].replace("\n", " ")


class ContractSchema(BaseModel):
    """One stable contract revision and its self-contained JSON Schema."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        serialize_by_alias=True,
        validate_by_name=True,
    )

    name: str
    version: str = "1"
    key: str
    category: str
    role: ContractRole
    title: str
    description: str = ""
    json_schema: dict[str, JsonValue] = Field(alias="schema", serialization_alias="schema")
    checksum_sha256: str

    @model_validator(mode="after")
    def _validate_identity(self) -> ContractSchema:
        if _NAME_PATTERN.fullmatch(self.name) is None:
            raise ValueError("contract names must use lowercase dotted identifiers")
        if not self.version.strip():
            raise ValueError("contract version cannot be empty")
        if not self.category.strip():
            raise ValueError("contract category cannot be empty")
        if self.key != f"{self.name}@{self.version}":
            raise ValueError("contract key must match name and version")
        return self

    @property
    def file_name(self) -> str:
        """Return a deterministic filename for split catalog exports."""
        return f"{self.name}@{self.version}.schema.json"


class ProtocolCatalog(BaseModel):
    """Portable schema, provider, and template discovery manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = "fetchkit"
    protocol_version: str = PROTOCOL_VERSION
    package_version: str
    schema_dialect: str = SCHEMA_DIALECT
    schemas: tuple[ContractSchema, ...]
    providers: tuple[ProviderCapabilities, ...] = ()
    templates: tuple[TemplateDescriptor, ...] = ()
    services: tuple[RpcService, ...] = ()

    @model_validator(mode="after")
    def _validate_unique_entries(self) -> ProtocolCatalog:
        schema_keys = [item.key for item in self.schemas]
        if len(schema_keys) != len(set(schema_keys)):
            raise ValueError("protocol catalog contains duplicate schema keys")
        provider_names = [item.name for item in self.providers]
        if len(provider_names) != len(set(provider_names)):
            raise ValueError("protocol catalog contains duplicate provider names")
        template_keys = [item.ref.key for item in self.templates]
        if len(template_keys) != len(set(template_keys)):
            raise ValueError("protocol catalog contains duplicate template keys")
        service_keys = [item.key for item in self.services]
        if len(service_keys) != len(set(service_keys)):
            raise ValueError("protocol catalog contains duplicate service keys")
        available_contracts = set(schema_keys)
        for service in self.services:
            for method in service.methods:
                referenced = (method.request_contract, method.response_contract)
                missing = [key for key in referenced if key and key not in available_contracts]
                if missing:
                    raise ValueError(
                        f"RPC method {service.name}/{method.name} references unknown "
                        f"contracts: {', '.join(missing)}"
                    )
        return self

    def schema_for(self, key: str) -> ContractSchema:
        """Resolve one contract by its ``name@version`` key."""
        for item in self.schemas:
            if item.key == key:
                return item
        raise KeyError(f"unknown protocol contract: {key}")


@dataclass(frozen=True, slots=True)
class _SchemaSpec:
    name: str
    category: str
    role: ContractRole
    model: type[BaseModel]
    version: str = "1"


_SCHEMA_SPECS = (
    _SchemaSpec("url.value", "url", "value", URL),
    _SchemaSpec("url.domain_parts", "url", "value", DomainParts),
    _SchemaSpec("http.retry_policy", "http", "policy", RetryPolicy),
    _SchemaSpec("http.timeout_policy", "http", "policy", TimeoutPolicy),
    _SchemaSpec("http.pool_policy", "http", "policy", PoolPolicy),
    _SchemaSpec("http.stream_policy", "http", "policy", StreamPolicy),
    _SchemaSpec("http.fetch_request", "http", "input", FetchRequest),
    _SchemaSpec("http.batch_request", "http", "input", BatchFetchRequest),
    _SchemaSpec("http.fetch_response", "http", "output", FetchResponse),
    _SchemaSpec("http.stream_chunk", "http", "event", StreamChunk),
    _SchemaSpec("http.batch_item", "http", "output", BatchItemResponse),
    _SchemaSpec("http.batch_response", "http", "output", BatchFetchResponse),
    _SchemaSpec("resource.web", "resource", "value", WebResource),
    _SchemaSpec("resource.page", "resource", "value", WebPage),
    _SchemaSpec("resource.media", "resource", "value", MediaResource),
    _SchemaSpec("stream.info", "stream", "value", ByteStreamInfo),
    _SchemaSpec("document.selector_rule", "document", "input", SelectorRule),
    _SchemaSpec("document.link_rule", "document", "input", LinkRule),
    _SchemaSpec("document.image_rule", "document", "input", ImageRule),
    _SchemaSpec("document.collection_rule", "document", "input", CollectionRule),
    _SchemaSpec("document.gallery_rule", "document", "input", GalleryRule),
    _SchemaSpec("document.link", "document", "output", ExtractedLink),
    _SchemaSpec("document.srcset_candidate", "document", "output", SrcsetCandidate),
    _SchemaSpec("document.image_candidate", "document", "output", ImageCandidate),
    _SchemaSpec("document.collection_item", "document", "output", CollectionItem),
    _SchemaSpec("document.collection", "document", "output", ExtractedCollection),
    _SchemaSpec("extraction.result", "extraction", "output", ExtractionResult),
    _SchemaSpec("acquisition.request", "acquisition", "input", AcquisitionRequest),
    _SchemaSpec("acquisition.capabilities", "acquisition", "value", ProviderCapabilities),
    _SchemaSpec("acquisition.provenance", "acquisition", "value", AcquisitionProvenance),
    _SchemaSpec("acquisition.result", "acquisition", "output", AcquisitionResult),
    _SchemaSpec("acquisition.event", "acquisition", "event", AcquisitionEvent),
    _SchemaSpec("media.pixel_dimensions", "media", "value", PixelDimensions),
    _SchemaSpec("media.thumbnail", "media", "value", ThumbnailInfo),
    _SchemaSpec("media.image", "media", "value", ImageInfo),
    _SchemaSpec("media.video_stream", "media", "value", VideoStreamInfo),
    _SchemaSpec("media.audio_stream", "media", "value", AudioStreamInfo),
    _SchemaSpec("media.provenance", "media", "value", MediaProvenance),
    _SchemaSpec("media.metadata", "media", "output", MediaMetadata),
    _SchemaSpec("media.image_processing", "media", "input", ImageProcessingSpec),
    _SchemaSpec("media.processing_result", "media", "output", MediaProcessingResult),
    _SchemaSpec("metadata.favicon", "metadata", "value", FaviconLink),
    _SchemaSpec("metadata.open_graph", "metadata", "value", OpenGraphMetadata),
    _SchemaSpec("metadata.page", "metadata", "output", PageMetadata),
    _SchemaSpec("artifact.blob_ref", "artifact", "value", BlobRef),
    _SchemaSpec("artifact.ref", "artifact", "value", ArtifactRef),
    _SchemaSpec("artifact.member", "artifact", "value", ArtifactMember),
    _SchemaSpec("artifact.collection", "artifact", "value", ArtifactCollection),
    _SchemaSpec("job.template_ref", "job", "value", TemplateRef),
    _SchemaSpec("job.policy", "job", "policy", JobPolicy),
    _SchemaSpec("job.trace_context", "job", "value", JobTraceContext),
    _SchemaSpec("job.request", "job", "input", JobRequest),
    _SchemaSpec("job.result", "job", "output", JobResult),
    _SchemaSpec("job.flow_request", "job", "input", FlowRequest),
    _SchemaSpec("job.flow_result", "job", "output", FlowResult),
    _SchemaSpec("job.lease", "job", "value", JobLease),
    _SchemaSpec("job.queue_stats", "job", "output", QueueStats),
    _SchemaSpec("job.record", "job", "output", JobRecord),
    _SchemaSpec("job.record_page", "job", "output", JobRecordPage),
    _SchemaSpec("job.submission", "job", "output", JobSubmission),
    _SchemaSpec("job.cancellation", "job", "output", JobCancellation),
    _SchemaSpec("job.service_health", "job", "output", JobServiceHealth),
    _SchemaSpec("job.worker_config", "job", "policy", WorkerConfig),
    _SchemaSpec("job.worker_event", "job", "event", WorkerEvent),
    _SchemaSpec("job.worker_snapshot", "job", "output", WorkerSnapshot),
    _SchemaSpec("job.pagination_input", "job-template", "input", PaginationInput),
    _SchemaSpec("job.media_acquisition_input", "job-template", "input", MediaAcquisitionInput),
    _SchemaSpec("job.search_input", "job-template", "input", SearchInput),
    _SchemaSpec("search.request", "search", "input", SearchRequest),
    _SchemaSpec("search.hit", "search", "output", SearchHit),
    _SchemaSpec("search.result", "search", "output", SearchResult),
    _SchemaSpec("rpc.job_lookup", "rpc", "input", JobLookupRequest),
    _SchemaSpec("rpc.job_list", "rpc", "input", JobListRequest),
    _SchemaSpec(
        "rpc.worker_event_subscription",
        "rpc",
        "input",
        WorkerEventSubscription,
    ),
    _SchemaSpec("rpc.template_catalog", "rpc", "output", TemplateCatalog),
)


def _contract(spec: _SchemaSpec) -> ContractSchema:
    # Serialization mode intentionally omits process-local fields such as
    # request content iterators and retry factories from the portable schema.
    schema: dict[str, JsonValue] = spec.model.model_json_schema(mode="serialization")
    schema = {
        "$schema": SCHEMA_DIALECT,
        "$id": f"urn:fetchkit:contract:{spec.name}:{spec.version}",
        **schema,
    }
    return ContractSchema(
        name=spec.name,
        version=spec.version,
        key=f"{spec.name}@{spec.version}",
        category=spec.category,
        role=spec.role,
        title=str(schema.get("title", spec.model.__name__)),
        description=_description(spec.model),
        schema=schema,
        checksum_sha256=_checksum(schema),
    )


def build_protocol_catalog(
    *,
    providers: tuple[ProviderCapabilities, ...] = (),
    templates: tuple[TemplateDescriptor, ...] = (),
    services: tuple[RpcService, ...] | None = None,
    package_version: str | None = None,
) -> ProtocolCatalog:
    """Build a deterministic catalog from portable models and runtime metadata."""
    schemas = tuple(sorted((_contract(spec) for spec in _SCHEMA_SPECS), key=lambda item: item.key))
    return ProtocolCatalog(
        package_version=package_version or _package_version(),
        schemas=schemas,
        providers=tuple(sorted(providers, key=lambda item: item.name)),
        templates=tuple(sorted(templates, key=lambda item: item.ref.key)),
        services=tuple(
            sorted(
                services if services is not None else (JOB_CONTROL_PLANE_SERVICE,),
                key=lambda item: item.key,
            )
        ),
    )


async def discover_protocol_catalog(
    *,
    load_provider_plugins: bool = False,
) -> ProtocolCatalog:
    """Build a catalog with built-in templates and installed provider metadata.

    Provider entry points are loaded only when explicitly requested because
    loading them imports and executes third-party package code.
    """
    registry = TemplateRegistry()
    register_builtin_templates(registry)
    async with AcquisitionService() as service:
        if load_provider_plugins:
            service.load_entry_points()
        providers = service.capabilities()
    return build_protocol_catalog(
        providers=providers,
        templates=registry.descriptors(),
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def export_protocol_catalog(
    catalog: ProtocolCatalog,
    destination: str | Path,
    *,
    split: bool = False,
) -> tuple[Path, ...]:
    """Write a catalog bundle or a manifest plus one file per schema.

    Split exports are convenient for TypeScript generators that accept one
    JSON Schema document at a time. The manifest remains self-contained so a
    consumer can also read only ``manifest.json``.
    """
    target = Path(destination)
    payload = catalog.model_dump(mode="json", by_alias=True)
    if not split:
        if target.exists() and target.is_dir():
            raise IsADirectoryError(f"catalog destination is a directory: {target}")
        _write_json(target, payload)
        return (target,)

    if target.exists() and not target.is_dir():
        raise NotADirectoryError(f"split catalog destination is not a directory: {target}")
    target.mkdir(parents=True, exist_ok=True)
    manifest = target / "manifest.json"
    _write_json(manifest, payload)
    written = [manifest]
    schema_dir = target / "schemas"
    for contract in catalog.schemas:
        path = schema_dir / contract.file_name
        _write_json(path, contract.json_schema)
        written.append(path)
    return tuple(written)


__all__ = [
    "ContractRole",
    "ContractSchema",
    "PROTOCOL_VERSION",
    "ProtocolCatalog",
    "SCHEMA_DIALECT",
    "build_protocol_catalog",
    "discover_protocol_catalog",
    "export_protocol_catalog",
]
