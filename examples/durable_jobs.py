"""Run a bounded, serializable pagination job in process."""

from __future__ import annotations

import asyncio

from pyfetcher import AsyncFetchClient
from pyfetcher.artifacts import LocalBlobStore
from pyfetcher.jobs import (
    FlowRequest,
    InProcessJobRuntime,
    JobContext,
    JobExecutor,
    JobRequest,
    PaginationInput,
    TemplateRef,
    TemplateRegistry,
    register_builtin_templates,
)


async def main() -> None:
    registry = TemplateRegistry()
    register_builtin_templates(registry)
    job = JobRequest(
        template=TemplateRef(name="web.pagination", version="1"),
        target="https://example.com/archive?page=1",
        payload=PaginationInput(
            mode="discover_last",
            page_link_selector="nav.pagination a[href]",
            store_page=True,
        ).model_dump(mode="json"),
    )

    async with AsyncFetchClient() as fetcher:
        executor = JobExecutor(
            registry,
            context=JobContext(
                services={"fetch": fetcher},
                blob_store=LocalBlobStore("./artifacts"),
            ),
        )
        async with InProcessJobRuntime(executor) as runtime:
            result = await runtime.run(
                FlowRequest(name="archive-discovery", jobs=(job,), concurrency=4)
            )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
