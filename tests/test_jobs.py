from __future__ import annotations

import asyncio
from pathlib import Path

from pyfetcher.artifacts import LocalBlobStore, MemoryBlobStore
from pyfetcher.contracts import FetchResponse
from pyfetcher.jobs import (
    FlowRequest,
    InMemoryJobQueue,
    InProcessJobRuntime,
    JobContext,
    JobExecutor,
    JobPolicy,
    JobRequest,
    JobResult,
    MediaAcquisitionInput,
    PaginationInput,
    PaginationTemplate,
    TemplateRef,
    TemplateRegistry,
    register_builtin_templates,
)
from pyfetcher.search import SearchHit, SearchRequest, SearchResult, SearchService


class ValueTemplate:
    name = "test.value"
    version = "1"

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        return JobResult.succeeded(job, output={"value": job.payload.get("value")})


class FanoutTemplate:
    name = "test.fanout"
    version = "1"

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        count = int(job.payload.get("count", 0))
        children = tuple(
            JobRequest(
                template=TemplateRef(name="test.value"),
                payload={"value": index},
            )
            for index in range(count)
        )
        return JobResult.succeeded(job, spawned_jobs=children)


class FlakyTemplate:
    name = "test.flaky"
    version = "1"

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        if job.attempt == 1:
            return JobResult.failed(job, "try again")
        return JobResult.succeeded(job, output={"attempt": job.attempt})


class SlowTemplate:
    name = "test.slow"
    version = "1"

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        await asyncio.sleep(0.05)
        return JobResult.succeeded(job)


class FakeFetch:
    async def afetch(self, request):
        html = b"""
        <a class='page' href='?page=1'>1</a>
        <a class='page' href='?page=2'>2</a>
        <a class='page' href='?page=7'>Last</a>
        """
        return FetchResponse(
            request_url=request.url.unicode_string(),
            final_url="https://example.com/items?page=1",
            status_code=200,
            headers={"content-type": "text/html"},
            content_type="text/html",
            text=html.decode(),
            body=html,
            backend="fake",
            elapsed_ms=1,
        )


class FakeSearchProvider:
    name = "example"

    def score(self, request: SearchRequest) -> int | None:
        return 10

    async def search(self, request: SearchRequest) -> SearchResult:
        return SearchResult(
            query=request.query,
            provider=self.name,
            hits=(SearchHit(url="https://example.com/one", title="One"),),
            next_cursor="next",
        )


async def test_blob_stores_create_portable_integrity_refs(tmp_path: Path) -> None:
    memory = MemoryBlobStore(namespace="tests")
    memory_ref = await memory.put_bytes("raw/page.html", b"hello", media_type="text/html")
    assert memory_ref.uri == "memory://tests/raw/page.html"
    assert memory_ref.size_bytes == 5
    assert await memory.get_bytes(memory_ref) == b"hello"

    source = tmp_path / "source.bin"
    source.write_bytes(b"streamed file")
    local = LocalBlobStore(tmp_path / "blobs")
    local_ref = await local.put_file("media/item.bin", source)
    assert local_ref.provider == "local"
    assert local_ref.size_bytes == 13
    assert await local.exists(local_ref)
    assert await local.get_bytes(local_ref) == b"streamed file"


def test_jobs_are_json_round_trip_safe() -> None:
    job = JobRequest(
        template=TemplateRef(name="web.pagination", version="1"),
        target="https://example.com",
        payload=PaginationInput(mode="enumerate").model_dump(mode="json"),
    )
    assert JobRequest.model_validate_json(job.model_dump_json()) == job


def test_media_job_preserves_custom_provider_options() -> None:
    payload = MediaAcquisitionInput(
        provider="custom_dl",
        provider_options={"custom_dl": {"quality": 85, "variant": "mobile"}},
    )

    assert MediaAcquisitionInput.model_validate_json(payload.model_dump_json()) == payload


def test_builtin_template_catalog_is_discoverable() -> None:
    registry = TemplateRegistry()
    register_builtin_templates(registry)
    assert [item.ref.key for item in registry.descriptors()] == [
        "media.acquire@1",
        "site.search@1",
        "web.pagination@1",
    ]
    assert registry.descriptors()[-1].input_schema["title"] == "PaginationInput"


async def test_executor_applies_portable_job_timeout() -> None:
    registry = TemplateRegistry()
    registry.register(SlowTemplate())
    executor = JobExecutor(registry)
    job = JobRequest(
        template=TemplateRef(name="test.slow"),
        policy=JobPolicy(timeout_seconds=0.001, max_attempts=1),
    )
    result = await executor.execute(job)
    assert result.status == "failed"
    assert result.error == "job timed out after 0.001 seconds"


async def test_local_runtime_handles_retry_and_dynamic_fanout() -> None:
    registry = TemplateRegistry()
    registry.register(ValueTemplate())
    registry.register(FanoutTemplate())
    registry.register(FlakyTemplate())
    executor = JobExecutor(registry)
    flow = FlowRequest(
        name="dynamic",
        jobs=(
            JobRequest(template=TemplateRef(name="test.fanout"), payload={"count": 3}),
            JobRequest(
                template=TemplateRef(name="test.flaky"),
                policy=JobPolicy(max_attempts=2, retry_backoff_seconds=0),
            ),
        ),
        concurrency=3,
    )
    async with InProcessJobRuntime(executor) as runtime:
        result = await runtime.run(flow)
    assert result.status == "succeeded"
    assert result.submitted_jobs == 5
    assert result.succeeded_jobs == 5
    assert any(item.output.get("attempt") == 2 for item in result.results)


async def test_local_runtime_reports_fanout_limit_without_leaving_leases() -> None:
    registry = TemplateRegistry()
    registry.register(ValueTemplate())
    registry.register(FanoutTemplate())
    queue = InMemoryJobQueue()
    flow = FlowRequest(
        name="bounded",
        jobs=(JobRequest(template=TemplateRef(name="test.fanout"), payload={"count": 5}),),
        max_jobs=3,
    )
    runtime = InProcessJobRuntime(JobExecutor(registry), queue=queue)
    result = await runtime.run(flow)
    assert result.status == "failed"
    assert result.submitted_jobs == 3
    assert (await queue.stats()).leased == 0


async def test_pagination_template_finds_last_page_and_fans_out() -> None:
    template = PaginationTemplate()
    context = JobContext(services={"fetch": FakeFetch()})
    payload = PaginationInput(
        mode="enumerate",
        page_link_selector="a.page",
        visit_template=TemplateRef(name="test.value"),
    ).model_dump(mode="json")
    job = JobRequest(
        template=TemplateRef(name=template.name),
        target="https://example.com/items?page=1",
        payload=payload,
    )
    result = await template.execute(job, context)
    assert result.output["last_page"] == 7
    assert len(result.output["page_urls"]) == 7
    assert len(result.spawned_jobs) == 7
    assert result.spawned_jobs[-1].target == "https://example.com/items?page=7"


async def test_search_service_routes_and_returns_portable_results() -> None:
    service = SearchService((FakeSearchProvider(),))
    result = await service.search(SearchRequest(query="one"))
    assert result.provider == "example"
    assert result.hits[0].title == "One"
