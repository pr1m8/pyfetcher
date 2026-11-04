"""Dependency-free TypeScript source generation from the protocol catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pyfetcher.protocol.catalog import ContractSchema, ProtocolCatalog, export_protocol_catalog
from pyfetcher.protocol.rpc import export_grpc_proto

_IDENTIFIER_PARTS = re.compile(r"[^A-Za-z0-9]+")
_PROPERTY_NAME = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def _pascal(value: str) -> str:
    parts = [part for part in _IDENTIFIER_PARTS.split(value) if part]
    rendered = "".join(part[:1].upper() + part[1:] for part in parts)
    return rendered if rendered and not rendered[0].isdigit() else f"Contract{rendered}"


def typescript_contract_name(contract: ContractSchema) -> str:
    """Return the stable exported TypeScript name for a contract revision."""
    version = "".join(
        part[:1].upper() + part[1:] for part in _IDENTIFIER_PARTS.split(contract.version) if part
    )
    return f"{_pascal(contract.name)}V{version or '1'}"


def _contract_file(contract: ContractSchema) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", contract.name.lower()).strip("-")
    version = re.sub(r"[^a-z0-9]+", "-", contract.version.lower()).strip("-")
    return f"{name}.v{version}.ts"


def _property_name(value: str) -> str:
    return value if _PROPERTY_NAME.fullmatch(value) else json.dumps(value)


def _literal(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int | float):
        return str(value).lower()
    return "unknown"


def _join_types(values: list[str], separator: str) -> str:
    unique = list(dict.fromkeys(values))
    return f" {separator} ".join(unique) if unique else "unknown"


def _render_type(
    schema: object,
    *,
    ref_prefix: str,
    indent: int = 0,
) -> str:
    if not isinstance(schema, dict) or not schema:
        return "unknown"
    reference = schema.get("$ref")
    if isinstance(reference, str):
        marker = "#/$defs/"
        if not reference.startswith(marker):
            return "unknown"
        return f"{ref_prefix}{_pascal(reference.removeprefix(marker))}"
    if "const" in schema:
        return _literal(schema["const"])
    enum = schema.get("enum")
    if isinstance(enum, list):
        return _join_types([_literal(value) for value in enum], "|")
    for keyword, separator in (("anyOf", "|"), ("oneOf", "|"), ("allOf", "&")):
        variants = schema.get(keyword)
        if isinstance(variants, list):
            return _join_types(
                [_render_type(value, ref_prefix=ref_prefix, indent=indent) for value in variants],
                separator,
            )

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        return _join_types(
            [
                _render_type({"type": value}, ref_prefix=ref_prefix, indent=indent)
                for value in schema_type
            ],
            "|",
        )
    if schema_type == "null":
        return "null"
    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "array":
        item_type = _render_type(
            schema.get("items", {}),
            ref_prefix=ref_prefix,
            indent=indent,
        )
        return f"ReadonlyArray<{item_type}>"

    properties = schema.get("properties")
    additional = schema.get("additionalProperties")
    if schema_type == "object" or isinstance(properties, dict) or additional is not None:
        if isinstance(properties, dict) and properties:
            required = set(schema.get("required", ()))
            padding = "  " * indent
            child_padding = "  " * (indent + 1)
            lines = ["{"]
            for name, value in properties.items():
                optional = "" if name in required else "?"
                rendered = _render_type(
                    value,
                    ref_prefix=ref_prefix,
                    indent=indent + 1,
                )
                lines.append(
                    f"{child_padding}readonly {_property_name(name)}{optional}: {rendered};"
                )
            lines.append(f"{padding}}}")
            object_type = "\n".join(lines)
            if additional is True:
                return f"{object_type} & Readonly<Record<string, unknown>>"
            if isinstance(additional, dict):
                value_type = _render_type(
                    additional,
                    ref_prefix=ref_prefix,
                    indent=indent,
                )
                return f"{object_type} & Readonly<Record<string, {value_type}>>"
            return object_type
        if additional is False:
            return "Readonly<Record<string, never>>"
        value_type = (
            _render_type(additional, ref_prefix=ref_prefix, indent=indent)
            if isinstance(additional, dict)
            else "unknown"
        )
        return f"Readonly<Record<string, {value_type}>>"
    return "unknown"


def render_typescript_contract(contract: ContractSchema) -> str:
    """Render one self-contained TypeScript type module."""
    name = typescript_contract_name(contract)
    schema = contract.json_schema
    definitions = schema.get("$defs", {})
    lines = [
        "// Generated by fetchkit. Do not edit by hand.",
        f"// Contract: {contract.key}",
        f"// SHA-256: {contract.checksum_sha256}",
        "",
    ]
    ref_prefix = ""
    if isinstance(definitions, dict) and definitions:
        namespace = f"{name}Defs"
        ref_prefix = f"{namespace}."
        lines.append(f"export namespace {namespace} {{")
        for definition_name, definition in sorted(definitions.items()):
            rendered = _render_type(definition, ref_prefix="", indent=1)
            lines.append(f"  export type {_pascal(definition_name)} = {rendered};")
        lines.extend(("}", ""))
    rendered_root = _render_type(schema, ref_prefix=ref_prefix)
    schema_id = str(schema.get("$id", ""))
    lines.extend(
        (
            f"export type {name} = {rendered_root};",
            "",
            f"export const {name}Contract = {{",
            f"  key: {json.dumps(contract.key)},",
            f"  schemaId: {json.dumps(schema_id)},",
            f"  checksumSha256: {json.dumps(contract.checksum_sha256)},",
            "} as const;",
            "",
        )
    )
    return "\n".join(lines)


def _method_name(value: str) -> str:
    return value[:1].lower() + value[1:]


def _render_rpc(catalog: ProtocolCatalog) -> str:
    contracts = {contract.key: contract for contract in catalog.schemas}
    referenced_keys = {
        key
        for service in catalog.services
        for method in service.methods
        for key in (method.request_contract, method.response_contract)
        if key is not None
    }
    lines = ["// Generated by fetchkit. Do not edit by hand.", ""]
    for key in sorted(referenced_keys):
        contract = contracts[key]
        lines.append(
            f"import type {{ {typescript_contract_name(contract)} }} "
            f'from "./types/{_contract_file(contract).removesuffix(".ts")}.js";'
        )
    lines.extend(
        (
            "import type { JsonRpcTransport, RpcCallOptions, RpcServiceDescriptor } "
            'from "./runtime.js";',
            "",
        )
    )
    for service in catalog.services:
        descriptor_name = f"{_method_name(service.name.rsplit('.', 1)[-1])}Descriptor"
        lines.append(f"export const {descriptor_name} = {{")
        lines.append(f"  name: {json.dumps(service.name)},")
        lines.append(f"  version: {json.dumps(service.version)},")
        lines.append("  methods: {")
        for method in service.methods:
            name = _method_name(method.name)
            lines.extend(
                (
                    f"    {name}: {{",
                    f"      name: {json.dumps(method.name)},",
                    f"      path: {json.dumps(service.method_path(method))},",
                    f"      requestContract: {json.dumps(method.request_contract)},",
                    f"      responseContract: {json.dumps(method.response_contract)},",
                    f"      cardinality: {json.dumps(method.cardinality)},",
                    "    },",
                )
            )
        lines.extend(("  },", "} as const satisfies RpcServiceDescriptor;", ""))

        client_name = f"{service.name.rsplit('.', 1)[-1]}Client"
        lines.extend(
            (
                f"export class {client_name} {{",
                "  constructor(private readonly transport: JsonRpcTransport) {}",
                "",
            )
        )
        for method in service.methods:
            name = _method_name(method.name)
            response = typescript_contract_name(contracts[method.response_contract])
            request = (
                typescript_contract_name(contracts[method.request_contract])
                if method.request_contract is not None
                else "undefined"
            )
            return_type = (
                f"AsyncIterable<{response}>"
                if method.cardinality == "server_stream"
                else f"Promise<{response}>"
            )
            if method.request_contract is None:
                signature = f"options?: RpcCallOptions): {return_type}"
                request_value = "undefined"
            else:
                signature = f"request: {request}, options?: RpcCallOptions): {return_type}"
                request_value = "request"
            lines.append(f"  {name}({signature} {{")
            transport_method = "serverStream" if method.cardinality == "server_stream" else "unary"
            lines.append(f"    return this.transport.{transport_method}<{request}, {response}>(")
            lines.append(f"      {descriptor_name}.methods.{name},")
            lines.append(f"      {request_value},")
            lines.append("      options,")
            lines.extend(("    );", "  }", ""))
        lines.extend(("}", ""))
    return "\n".join(lines)


def _render_runtime(catalog: ProtocolCatalog) -> str:
    contract_keys = "\n  | ".join(json.dumps(item.key) for item in catalog.schemas)
    return f"""// Generated by fetchkit. Do not edit by hand.

export type ContractKey =
  | {contract_keys};

export interface RpcMethodDescriptor {{
  readonly name: string;
  readonly path: string;
  readonly requestContract: ContractKey | null;
  readonly responseContract: ContractKey;
  readonly cardinality: "unary" | "server_stream";
}}

export interface RpcServiceDescriptor {{
  readonly name: string;
  readonly version: string;
  readonly methods: Readonly<Record<string, RpcMethodDescriptor>>;
}}

export interface RpcCallOptions {{
  readonly metadata?: Readonly<Record<string, string>>;
  readonly deadlineMs?: number;
}}

export interface JsonRpcTransport {{
  unary<TRequest, TResponse>(
    method: RpcMethodDescriptor,
    request: TRequest,
    options?: RpcCallOptions,
  ): Promise<TResponse>;

  serverStream<TRequest, TResponse>(
    method: RpcMethodDescriptor,
    request: TRequest,
    options?: RpcCallOptions,
  ): AsyncIterable<TResponse>;
}}

export function serializeContractJson(value: unknown): string {{
  return JSON.stringify(value);
}}

export function parseContractJson<T>(value: string): T {{
  return JSON.parse(value) as T;
}}
"""


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def export_typescript_protocol(
    catalog: ProtocolCatalog,
    destination: str | Path,
    *,
    package_name: str = "@fetchkit/protocol",
) -> tuple[Path, ...]:
    """Export schemas, generated TypeScript types, RPC clients, and protobuf."""
    if not package_name.strip():
        raise ValueError("TypeScript package name cannot be empty")
    target = Path(destination)
    if target.exists() and not target.is_dir():
        raise NotADirectoryError(f"TypeScript destination is not a directory: {target}")
    target.mkdir(parents=True, exist_ok=True)
    written = list(export_protocol_catalog(catalog, target, split=True))

    type_paths: list[Path] = []
    for contract in catalog.schemas:
        path = target / "types" / _contract_file(contract)
        _write_text(path, render_typescript_contract(contract))
        type_paths.append(path)
    written.extend(type_paths)

    runtime = target / "runtime.ts"
    rpc = target / "rpc.ts"
    index = target / "index.ts"
    _write_text(runtime, _render_runtime(catalog))
    _write_text(rpc, _render_rpc(catalog))
    index_lines = ["// Generated by fetchkit. Do not edit by hand.", ""]
    for contract in catalog.schemas:
        module = _contract_file(contract).removesuffix(".ts")
        index_lines.append(f'export * from "./types/{module}.js";')
    index_lines.extend(('export * from "./runtime.js";', 'export * from "./rpc.js";', ""))
    _write_text(index, "\n".join(index_lines))
    written.extend((runtime, rpc, index))

    package = target / "package.json"
    tsconfig = target / "tsconfig.json"
    _write_text(
        package,
        json.dumps(
            {
                "name": package_name,
                "private": True,
                "type": "module",
                "sideEffects": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _write_text(
        tsconfig,
        json.dumps(
            {
                "compilerOptions": {
                    "exactOptionalPropertyTypes": True,
                    "lib": ["ES2022", "DOM"],
                    "module": "NodeNext",
                    "moduleResolution": "NodeNext",
                    "noEmit": True,
                    "strict": True,
                    "target": "ES2022",
                },
                "include": ["*.ts", "types/*.ts"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    written.extend((package, tsconfig))

    proto = export_grpc_proto(target / "proto" / "fetchkit" / "jobs" / "v1" / "jobs.proto")
    written.append(proto)
    return tuple(written)


__all__ = [
    "export_typescript_protocol",
    "render_typescript_contract",
    "typescript_contract_name",
]
