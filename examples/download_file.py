"""Download file examples for pyfetcher.

Demonstrates streaming file downloads.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.download.service import DownloadService
from pyfetcher.fetch.service import FetchService
from pyfetcher.headers.browser import BrowserHeaderProvider


async def download_example() -> None:
    """Download a file using the DownloadService."""
    print("=== Download File ===")

    service = FetchService(header_provider=BrowserHeaderProvider("chrome_win"))
    dl = DownloadService(fetch_service=service)

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "example.html"
        request = FetchRequest(url="https://httpbin.org/html")

        print(f"  Downloading to {dest}...")
        result_path = await dl.adownload_to_path(request, dest)
        size = result_path.stat().st_size
        print(f"  Downloaded {size} bytes to {result_path}")
        print(f"  Preview: {result_path.read_text()[:200]}...")

    await service.aclose()


def show_usage() -> None:
    """Show download usage patterns."""
    print("\n=== Download Usage ===")
    print("  from pyfetcher.download.service import DownloadService")
    print("  from pyfetcher.contracts.request import FetchRequest")
    print()
    print("  dl = DownloadService()")
    print("  request = FetchRequest(url='https://example.com/file.pdf')")
    print("  path = await dl.adownload_to_path(request, './file.pdf')")


if __name__ == "__main__":
    asyncio.run(download_example())
    show_usage()
