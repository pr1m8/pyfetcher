"""Entry point for running the pyfetcher MCP server.

Usage:
    python -m pyfetcher.mcp              # stdio (default)
    python -m pyfetcher.mcp --http 8000  # HTTP on port 8000
"""

from __future__ import annotations

import sys

from pyfetcher.mcp.server import mcp


def main() -> None:
    """Run the MCP server."""
    if "--http" in sys.argv:
        idx = sys.argv.index("--http")
        port = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 8000
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
