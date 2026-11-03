"""Versioned JSON Schema contracts for Python and cross-language clients."""

from pyfetcher.protocol.catalog import (
    PROTOCOL_VERSION,
    SCHEMA_DIALECT,
    ContractRole,
    ContractSchema,
    ProtocolCatalog,
    build_protocol_catalog,
    discover_protocol_catalog,
    export_protocol_catalog,
)

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
