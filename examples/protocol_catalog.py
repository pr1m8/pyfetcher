"""Example: export portable contracts for a TypeScript control plane.

Run with:
    python examples/protocol_catalog.py ./build/fetchkit-contracts
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from pyfetcher import (
    discover_protocol_catalog,
    export_protocol_catalog,
    export_typescript_protocol,
)


async def main() -> None:
    """Discover built-ins and write a split JSON Schema catalog."""
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", nargs="?", default="build/fetchkit-contracts")
    parser.add_argument(
        "--typescript",
        action="store_true",
        help="Generate TypeScript types, RPC clients, schemas, and protobuf.",
    )
    args = parser.parse_args()

    catalog = await discover_protocol_catalog()
    written = (
        export_typescript_protocol(catalog, Path(args.destination))
        if args.typescript
        else export_protocol_catalog(catalog, Path(args.destination), split=True)
    )
    print(
        f"exported {len(catalog.schemas)} contracts, "
        f"{len(catalog.providers)} providers, {len(catalog.templates)} templates, "
        f"and {len(catalog.services)} RPC services"
    )
    print(written[0])


if __name__ == "__main__":
    asyncio.run(main())
