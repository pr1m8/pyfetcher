"""Example: host the durable-job control plane over gRPC.

Install with:
    python -m pip install 'fetchkit[grpc]'
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from pyfetcher import AsyncFetchClient
from pyfetcher.acquisition import AcquisitionService
from pyfetcher.artifacts import LocalBlobStore
from pyfetcher.integrations.grpc import create_job_grpc_server
from pyfetcher.jobs import JobApplication, JobContext, WorkerConfig
from pyfetcher.search import SearchService


async def main() -> None:
    """Run a loopback gRPC server until interrupted."""
    fetcher = AsyncFetchClient()
    acquisition = AcquisitionService()
    application = JobApplication.create(
        context=JobContext(
            services={
                "fetch": fetcher,
                "acquisition": acquisition,
                "search": SearchService(),
            },
            blob_store=LocalBlobStore(".fetchkit/artifacts"),
        ),
        worker_config=WorkerConfig(concurrency=4),
        owned_resources=(fetcher, acquisition),
    )
    server = create_job_grpc_server(application, address="127.0.0.1:50051")
    async with server:
        print(f"gRPC job service listening on 127.0.0.1:{server.bound_port}")
        await server.wait_for_termination()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
