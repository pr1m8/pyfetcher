"""Tests for the versioned cross-language contract catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pyfetcher import (
    JOB_CONTROL_PLANE_SERVICE,
    ProtocolCatalog,
    ProviderCapabilities,
    RpcMethod,
    RpcService,
    build_protocol_catalog,
    discover_protocol_catalog,
    export_grpc_proto,
    export_protocol_catalog,
    export_typescript_protocol,
)


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_protocol_catalog_is_stable_json_safe_and_omits_runtime_request_fields() -> None:
    catalog = build_protocol_catalog(package_version="test")
    keys = [item.key for item in catalog.schemas]

    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    assert "http.fetch_request@1" in keys
    assert "acquisition.request@1" in keys
    assert "document.gallery_rule@1" in keys
    assert "job.request@1" in keys
    assert "job.record@1" in keys
    assert "job.worker_event@1" in keys
    assert "media.metadata@1" in keys
    assert "rpc.job_lookup@1" in keys
    assert "rpc.worker_event_subscription@1" in keys
    assert catalog.protocol_version == "2"

    request = catalog.schema_for("http.fetch_request@1")
    assert request.json_schema["$schema"] == catalog.schema_dialect
    assert request.json_schema["$id"] == "urn:fetchkit:contract:http.fetch_request:1"
    assert request.checksum_sha256 == _digest(request.json_schema)
    properties = request.json_schema["properties"]
    assert isinstance(properties, dict)
    assert "content" not in properties
    assert "content_factory" not in properties

    payload = json.loads(catalog.model_dump_json(by_alias=True))
    assert "schema" in payload["schemas"][0]
    assert "json_schema" not in payload["schemas"][0]
    assert ProtocolCatalog.model_validate(payload) == catalog


def test_protocol_catalog_binds_rpc_methods_to_known_contracts() -> None:
    catalog = build_protocol_catalog(package_version="test")

    assert catalog.services == (JOB_CONTROL_PLANE_SERVICE,)
    service = catalog.services[0]
    assert service.method_path("Submit") == "/fetchkit.jobs.v1.JobControlPlane/Submit"
    assert service.methods[-1].cardinality == "server_stream"
    assert service.methods[-1].response_contract == "job.worker_event@1"

    unknown = RpcService(
        name="example.v1.Broken",
        methods=(RpcMethod(name="Call", response_contract="missing.output@1"),),
    )
    with pytest.raises(ValueError, match="unknown contracts"):
        build_protocol_catalog(services=(unknown,), package_version="test")


def test_protocol_catalog_keeps_provider_option_schemas() -> None:
    capabilities = ProviderCapabilities(
        name="custom",
        available=True,
        operations=frozenset({"download"}),
        option_schema={
            "type": "object",
            "properties": {"quality": {"type": "integer", "minimum": 1}},
        },
    )
    catalog = build_protocol_catalog(
        providers=(capabilities,),
        package_version="test",
    )

    assert catalog.providers[0].option_schema["properties"]["quality"]["minimum"] == 1


async def test_discovered_protocol_catalog_has_builtin_providers_and_templates() -> None:
    catalog = await discover_protocol_catalog()

    assert {item.name for item in catalog.providers} == {"direct", "gallery_dl", "yt_dlp"}
    assert {item.ref.key for item in catalog.templates} == {
        "media.acquire@1",
        "site.search@1",
        "web.pagination@1",
    }


def test_export_protocol_catalog_bundle_and_split_files(tmp_path: Path) -> None:
    catalog = build_protocol_catalog(package_version="test")
    bundle = tmp_path / "contracts.json"

    assert export_protocol_catalog(catalog, bundle) == (bundle,)
    assert ProtocolCatalog.model_validate_json(bundle.read_text()) == catalog

    directory = tmp_path / "split"
    written = export_protocol_catalog(catalog, directory, split=True)
    assert written[0] == directory / "manifest.json"
    assert len(written) == len(catalog.schemas) + 1
    assert (directory / "schemas" / "job.request@1.schema.json").is_file()
    schema = json.loads((directory / "schemas" / "job.request@1.schema.json").read_text())
    assert schema["$id"] == "urn:fetchkit:contract:job.request:1"


def test_export_protocol_catalog_rejects_wrong_destination_kind(tmp_path: Path) -> None:
    catalog = build_protocol_catalog(package_version="test")
    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(IsADirectoryError):
        export_protocol_catalog(catalog, directory)

    file_path = tmp_path / "file.json"
    file_path.write_text("{}")
    with pytest.raises(NotADirectoryError):
        export_protocol_catalog(catalog, file_path, split=True)


def test_export_grpc_proto_uses_json_contract_framing(tmp_path: Path) -> None:
    target = export_grpc_proto(tmp_path / "jobs.proto")
    content = target.read_text()

    assert "package fetchkit.jobs.v1;" in content
    assert "service JobControlPlane" in content
    assert "rpc Submit(google.protobuf.BytesValue)" in content
    assert "returns (stream google.protobuf.BytesValue)" in content


def test_export_typescript_protocol_generates_types_and_rpc_client(tmp_path: Path) -> None:
    catalog = build_protocol_catalog(package_version="test")
    target = tmp_path / "typescript"

    written = export_typescript_protocol(
        catalog,
        target,
        package_name="@example/fetchkit-protocol",
    )

    assert written
    assert json.loads((target / "package.json").read_text())["name"] == (
        "@example/fetchkit-protocol"
    )
    job_type = (target / "types" / "job-request.v1.ts").read_text()
    assert "export type JobRequestV1" in job_type
    assert "readonly template: JobRequestV1Defs.TemplateRef" in job_type
    assert "readonly target?: string | null" in job_type
    rpc = (target / "rpc.ts").read_text()
    assert "export class JobControlPlaneClient" in rpc
    assert 'path: "/fetchkit.jobs.v1.JobControlPlane/Submit"' in rpc
    assert "watchEvents(" in rpc
    assert "AsyncIterable<JobWorkerEventV1>" in rpc
    assert (target / "schemas" / "rpc.job_lookup@1.schema.json").is_file()
    assert (target / "proto" / "fetchkit" / "jobs" / "v1" / "jobs.proto").is_file()

    first_rpc = rpc
    export_typescript_protocol(catalog, target, package_name="@example/fetchkit-protocol")
    assert (target / "rpc.ts").read_text() == first_rpc
