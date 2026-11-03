"""Example: register an application-defined acquisition downloader.

Run with:
    python examples/custom_downloader.py
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from pyfetcher import (
    AcquisitionRequest,
    AcquisitionService,
    DownloaderAcquisitionProvider,
    DownloaderContext,
)
from pyfetcher.downloaders import DownloadResult, MediaInfo


class GeneratedOptions(BaseModel):
    """Serializable options shared with jobs or generated clients."""

    label: str = "example"
    copies: int = Field(default=1, ge=1, le=10)


class GeneratedDownloader:
    """Small downloader whose results can be yielded asynchronously."""

    def __init__(self, options: GeneratedOptions) -> None:
        self.options = options

    def extract_info(self, url: str):
        async def items():
            for index in range(self.options.copies):
                yield MediaInfo(
                    url=url,
                    title=f"{self.options.label}-{index + 1}",
                    provider="generated",
                )

        return items()

    async def download(
        self,
        url: str,
        *,
        output_dir: str | None = None,
        progress_callback=None,
    ) -> list[DownloadResult]:
        raise NotImplementedError("this offline example demonstrates metadata only")


def build_downloader(context: DownloaderContext) -> GeneratedDownloader:
    """Build a request-scoped downloader from validated portable options."""
    return GeneratedDownloader(GeneratedOptions.model_validate(context.options))


async def main() -> None:
    """Run the custom downloader without performing network I/O."""
    provider = DownloaderAcquisitionProvider(
        "generated",
        factory=build_downloader,
        operations=("metadata",),
        url_patterns=("*.example.invalid",),
        options_model=GeneratedOptions,
    )
    request = AcquisitionRequest(
        url="https://media.example.invalid/item/42",
        provider="generated",
        operation="metadata",
        provider_options={
            "generated": {"label": "asset", "copies": 2},
        },
    )
    async with AcquisitionService(providers=[provider]) as service:
        result = await service.acquire(request)
    for item in result.media:
        print(item.title, item.url)


if __name__ == "__main__":
    asyncio.run(main())
