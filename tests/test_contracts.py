"""Unit tests for pyfetcher.contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyfetcher.contracts.policy import (
    PoolPolicy,
    RetryPolicy,
    StreamPolicy,
    TimeoutPolicy,
)
from pyfetcher.contracts.request import BatchFetchRequest, FetchRequest
from pyfetcher.contracts.resource import MediaResource, WebPage, WebResource
from pyfetcher.contracts.response import (
    BatchItemResponse,
    FetchResponse,
    StreamChunk,
)
from pyfetcher.contracts.url import URL


class TestURL:
    def test_basic_url(self) -> None:
        url = URL("https://example.com")
        assert url.scheme == "https"
        assert url.host == "example.com"

    def test_url_with_port(self) -> None:
        url = URL("https://example.com:8443")
        assert url.port == 8443

    def test_url_path_segments(self) -> None:
        url = URL("https://example.com/a/b/c/")
        assert url.path_segments == ["a", "b", "c"]

    def test_url_query_params(self) -> None:
        url = URL("https://example.com?a=1&a=2&b=")
        assert url.query_params == {"a": ["1", "2"], "b": [""]}

    def test_url_string(self) -> None:
        url = URL("https://example.com")
        assert str(url).startswith("https://example.com")

    def test_url_unicode_string(self) -> None:
        url = URL("https://example.com/path")
        result = url.unicode_string()
        assert "example.com" in result

    def test_invalid_url(self) -> None:
        with pytest.raises(ValidationError):
            URL("not-a-url")

    def test_url_frozen(self) -> None:
        url = URL("https://example.com")
        with pytest.raises(ValidationError):
            url.root = "https://other.com"  # type: ignore


class TestRetryPolicy:
    def test_defaults(self) -> None:
        policy = RetryPolicy()
        assert policy.attempts == 3
        assert policy.wait_base_seconds == 0.5
        assert 429 in policy.retry_status_codes

    def test_custom_values(self) -> None:
        policy = RetryPolicy(attempts=5, wait_max_seconds=16.0)
        assert policy.attempts == 5
        assert policy.wait_max_seconds == 16.0

    def test_json_serialization_sorts_status_codes(self) -> None:
        policy = RetryPolicy(retry_status_codes={503, 429, 500})
        assert policy.model_dump(mode="json")["retry_status_codes"] == [429, 500, 503]

    def test_frozen(self) -> None:
        policy = RetryPolicy()
        with pytest.raises(ValidationError):
            policy.attempts = 10  # type: ignore


class TestTimeoutPolicy:
    def test_defaults(self) -> None:
        policy = TimeoutPolicy()
        assert policy.total_seconds == 30.0
        assert policy.connect_seconds == 10.0


class TestPoolPolicy:
    def test_defaults(self) -> None:
        policy = PoolPolicy()
        assert policy.max_connections == 100
        assert policy.concurrency == 8


class TestStreamPolicy:
    def test_defaults(self) -> None:
        policy = StreamPolicy()
        assert policy.chunk_size == 65_536
        assert policy.decode_text is False
        assert policy.max_bytes is None


class TestFetchRequest:
    def test_basic_request(self) -> None:
        request = FetchRequest(url="https://example.com")
        assert request.method == "GET"
        assert request.backend == "httpx"
        assert request.verify_ssl is True

    def test_method_literal_validation(self) -> None:
        """Literal type enforces uppercase methods at validation time."""
        request = FetchRequest(url="https://example.com", method="GET")
        assert request.method == "GET"
        with pytest.raises(ValidationError):
            FetchRequest(url="https://example.com", method="get")  # type: ignore

    def test_request_with_headers(self) -> None:
        request = FetchRequest(
            url="https://example.com",
            headers={"x-custom": "value"},
        )
        assert request.headers["x-custom"] == "value"

    def test_request_with_params(self) -> None:
        request = FetchRequest(
            url="https://example.com",
            params={"key": "value"},
        )
        assert request.params["key"] == "value"

    def test_request_accepts_registered_backend_name(self) -> None:
        request = FetchRequest(url="https://example.com", backend="scrapy")
        assert request.backend == "scrapy"

    def test_request_accepts_proxy(self) -> None:
        request = FetchRequest(
            url="https://example.com",
            proxy="http://proxy.example:8080",
        )
        assert request.proxy == "http://proxy.example:8080"

    def test_request_rejects_invalid_proxy(self) -> None:
        with pytest.raises(ValidationError, match=r"absolute HTTP\(S\) URL"):
            FetchRequest(url="https://example.com", proxy="proxy.example:8080")

    def test_request_preserves_runtime_content_generator(self) -> None:
        def content():
            yield b"one"

        generator = content()
        request = FetchRequest(url="https://example.com", content=generator)
        assert request.content is generator
        assert "content" not in request.model_dump()

    def test_request_content_factory_is_runtime_only(self) -> None:
        request = FetchRequest(url="https://example.com", content_factory=lambda: [b"one"])
        assert request.content_factory is not None
        assert "content_factory" not in request.model_dump()

    def test_request_rejects_non_callable_content_factory(self) -> None:
        with pytest.raises(ValidationError, match="must be callable"):
            FetchRequest(url="https://example.com", content_factory="nope")  # type: ignore[arg-type]

    def test_request_rejects_multiple_body_sources(self) -> None:
        with pytest.raises(ValidationError, match="mutually exclusive"):
            FetchRequest(url="https://example.com", data=b"one", content=[b"two"])


class TestBatchFetchRequest:
    def test_batch_request(self) -> None:
        req = FetchRequest(url="https://example.com")
        batch = BatchFetchRequest(requests=[req, req])
        assert len(batch.requests) == 2
        assert batch.concurrency is None

    def test_batch_with_concurrency(self) -> None:
        req = FetchRequest(url="https://example.com")
        batch = BatchFetchRequest(requests=[req], concurrency=4)
        assert batch.concurrency == 4


class TestFetchResponse:
    def test_ok_response(self) -> None:
        response = FetchResponse(
            request_url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            headers={},
            backend="httpx",
            elapsed_ms=1.0,
        )
        assert response.ok is True

    def test_redirect_is_ok(self) -> None:
        response = FetchResponse(
            request_url="https://example.com/",
            final_url="https://example.com/new",
            status_code=301,
            headers={},
            backend="httpx",
            elapsed_ms=1.0,
        )
        assert response.ok is True

    def test_error_response(self) -> None:
        response = FetchResponse(
            request_url="https://example.com/",
            final_url="https://example.com/",
            status_code=404,
            headers={},
            backend="httpx",
            elapsed_ms=1.0,
        )
        assert response.ok is False

    def test_server_error(self) -> None:
        response = FetchResponse(
            request_url="https://example.com/",
            final_url="https://example.com/",
            status_code=500,
            headers={},
            backend="httpx",
            elapsed_ms=1.0,
        )
        assert response.ok is False


class TestStreamChunk:
    def test_chunk(self) -> None:
        chunk = StreamChunk(
            request_url="https://example.com/",
            final_url="https://example.com/",
            backend="httpx",
            index=0,
            data=b"hello",
        )
        assert chunk.index == 0
        assert chunk.data == b"hello"


class TestBatchItemResponse:
    def test_success(self) -> None:
        item = BatchItemResponse(
            request_url="https://example.com/",
            ok=True,
        )
        assert item.ok is True

    def test_failure(self) -> None:
        item = BatchItemResponse(
            request_url="https://example.com/",
            ok=False,
            error="timeout",
        )
        assert item.error == "timeout"


class TestWebResource:
    def test_web_resource(self) -> None:
        resource = WebResource(url="https://example.com")
        assert resource.url.host == "example.com"

    def test_web_page(self) -> None:
        page = WebPage(url="https://example.com", title="Home")
        assert page.title == "Home"

    def test_media_resource(self) -> None:
        media = MediaResource(
            url="https://example.com/file.mp4",
            filename="file.mp4",
            content_length=1024,
        )
        assert media.filename == "file.mp4"
