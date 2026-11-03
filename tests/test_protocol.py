"""Tests for the versioned cross-language contract catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pyfetcher import (
    ProtocolCatalog,
    ProviderCapabilities,
    build_protocol_catalog,
    discover_protocol_catalog,
    export_protocol_catalog,
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
    assert "media.metadata@1" in keys

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
