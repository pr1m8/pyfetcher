"""Tests for mechanism-neutral middleware composition."""

from __future__ import annotations

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import FetchResponse
from pyfetcher.fetch.service import FetchService
from pyfetcher.middleware import compose_async, compose_sync


def test_compose_sync_preserves_declaration_order() -> None:
    events: list[str] = []

    def first(request: str, call_next):
        events.append("first:before")
        response = call_next(f"{request}:first")
        events.append("first:after")
        return response

    def second(request: str, call_next):
        events.append("second:before")
        response = call_next(f"{request}:second")
        events.append("second:after")
        return response

    result = compose_sync(lambda request: request, [first, second])("start")

    assert result == "start:first:second"
    assert events == ["first:before", "second:before", "second:after", "first:after"]


async def test_compose_async_can_short_circuit() -> None:
    called = False

    async def handler(request: str) -> str:
        nonlocal called
        called = True
        return request

    async def middleware(request: str, call_next):
        return f"cached:{request}"

    result = await compose_async(handler, [middleware])("value")

    assert result == "cached:value"
    assert called is False


def _response(request: FetchRequest) -> FetchResponse:
    return FetchResponse(
        request_url=request.url.unicode_string(),
        final_url=request.url.unicode_string(),
        status_code=200,
        headers={},
        backend=request.backend,
        elapsed_ms=1.0,
    )


def test_fetch_service_runs_sync_middleware() -> None:
    class Transport:
        def fetch(self, request: FetchRequest) -> FetchResponse:
            return _response(request)

        def close(self) -> None:
            return None

    def add_header(request: FetchRequest, call_next):
        return call_next(request.model_copy(update={"headers": {"x-middleware": "yes"}}))

    class HeaderProvider:
        def build(self, *, request: FetchRequest) -> dict[str, str]:
            assert request.headers["x-middleware"] == "yes"
            return {}

    service = FetchService(
        httpx_transport=Transport(),  # type: ignore[arg-type]
        header_provider=HeaderProvider(),
        sync_middleware=[add_header],
    )

    response = service.fetch(FetchRequest(url="https://example.com"))
    assert response.status_code == 200


async def test_fetch_service_runs_async_middleware() -> None:
    class Transport:
        async def afetch(self, request: FetchRequest) -> FetchResponse:
            return _response(request)

        async def aclose(self) -> None:
            return None

    seen: list[str] = []

    async def observe(request: FetchRequest, call_next):
        seen.append("before")
        response = await call_next(request)
        seen.append("after")
        return response

    service = FetchService(
        httpx_transport=Transport(),  # type: ignore[arg-type]
        async_middleware=[observe],
    )

    response = await service.afetch(FetchRequest(url="https://example.com"))
    assert response.status_code == 200
    assert seen == ["before", "after"]
