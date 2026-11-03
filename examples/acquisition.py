"""Example: inspect or download a URL through an acquisition provider.

Run with:
    python examples/acquisition.py URL --metadata
    python examples/acquisition.py URL --provider yt_dlp --output-dir media
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from pyfetcher import AcquisitionRequest, AcquisitionService


def parse_args() -> argparse.Namespace:
    """Parse example command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument(
        "--provider",
        choices=("auto", "direct", "yt_dlp", "gallery_dl"),
        default="auto",
    )
    parser.add_argument("--metadata", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


async def main() -> None:
    """Run one explicit live acquisition and print compact events."""
    args = parse_args()
    request = AcquisitionRequest(
        url=args.url,
        provider=args.provider,
        operation="metadata" if args.metadata else "download",
        output_dir=args.output_dir,
    )
    async with AcquisitionService() as service:
        async for event in service.aiter_events(request):
            if event.progress:
                print(event.provider, event.progress.status, event.progress.percent)
            elif event.media:
                print(event.provider, event.media.title or event.media.url)
            elif event.download:
                print(event.provider, event.download.local_path)
            else:
                print(event.provider, event.kind)


if __name__ == "__main__":
    asyncio.run(main())
