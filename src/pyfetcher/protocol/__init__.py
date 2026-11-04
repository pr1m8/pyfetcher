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
from pyfetcher.protocol.rpc import (
    JOB_CONTROL_PLANE_SERVICE,
    JobListRequest,
    JobLookupRequest,
    RpcCardinality,
    RpcMethod,
    RpcService,
    TemplateCatalog,
    WorkerEventSubscription,
    export_grpc_proto,
    grpc_proto_text,
)
from pyfetcher.protocol.typescript import (
    export_typescript_protocol,
    render_typescript_contract,
    typescript_contract_name,
)

__all__ = [
    "ContractRole",
    "ContractSchema",
    "JOB_CONTROL_PLANE_SERVICE",
    "JobListRequest",
    "JobLookupRequest",
    "PROTOCOL_VERSION",
    "ProtocolCatalog",
    "RpcCardinality",
    "RpcMethod",
    "RpcService",
    "SCHEMA_DIALECT",
    "TemplateCatalog",
    "WorkerEventSubscription",
    "build_protocol_catalog",
    "discover_protocol_catalog",
    "export_grpc_proto",
    "export_protocol_catalog",
    "export_typescript_protocol",
    "grpc_proto_text",
    "render_typescript_contract",
    "typescript_contract_name",
]
