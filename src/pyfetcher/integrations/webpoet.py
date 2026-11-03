"""Optional WebPoet downloader and page-object bridge.

The bridge makes fetchkit a WebPoet request downloader and provides a small,
allowlisted standalone page registry. Complex dependency graphs, overrides,
and crawling remain the responsibility of ``scrapy-poet``; this module does
not pretend to be a complete WebPoet framework implementation.
"""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any, cast, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from pyfetcher.artifacts import ArtifactRef
from pyfetcher.contracts import FetchRequest, FetchResponse
from pyfetcher.jobs.models import JobRequest, JobResult
from pyfetcher.jobs.registry import JobContext


def _require_web_poet() -> Any:
    try:
        import web_poet
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "WebPoet integration requires `pip install 'fetchkit[web-poet]'`"
        ) from exc
    return web_poet


class WebPoetHttpAdapter:
    """Execute WebPoet ``HttpRequest`` values through a fetchkit async client."""

    def __init__(self, fetcher: object, *, backend: str = "httpx") -> None:
        self._fetcher = fetcher
        self._backend = backend

    async def download(self, request: object) -> object:
        """Download one WebPoet request and return its response type."""
        web_poet = _require_web_poet()
        try:
            from web_poet.exceptions import HttpRequestError

            fetch_request = FetchRequest(
                url=str(request.url),  # type: ignore[attr-defined]
                method=str(request.method).upper(),  # type: ignore[attr-defined]
                headers=dict(request.headers.items()),  # type: ignore[attr-defined]
                data=bytes(request.body) or None,  # type: ignore[attr-defined]
                backend=self._backend,
            )
            if hasattr(self._fetcher, "send"):
                response = await self._fetcher.send(fetch_request)  # type: ignore[union-attr]
            elif hasattr(self._fetcher, "afetch"):
                response = await self._fetcher.afetch(fetch_request)  # type: ignore[union-attr]
            else:
                raise TypeError("fetcher must provide async send() or afetch()")
        except Exception as exc:
            if isinstance(exc, HttpRequestError):
                raise
            raise HttpRequestError(str(exc), request=cast(Any, request)) from exc
        return web_poet.HttpResponse(
            response.final_url,
            response.body or (response.text or "").encode(),
            status=response.status_code,
            headers=response.headers,
        )

    __call__ = download

    def http_client(self, **kwargs: object) -> object:
        """Build a WebPoet ``HttpClient`` for page-object additional requests."""
        return _require_web_poet().HttpClient(request_downloader=self.download, **kwargs)


def to_webpoet_response(response: FetchResponse) -> object:
    """Convert a buffered fetchkit response into WebPoet's response type."""
    web_poet = _require_web_poet()
    return web_poet.HttpResponse(
        response.final_url,
        response.body or (response.text or "").encode(),
        status=response.status_code,
        headers=response.headers,
    )


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, BaseModel):
        return cast(JsonValue, value.model_dump(mode="json"))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_value(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    attrs_fields = getattr(type(value), "__attrs_attrs__", None)
    if attrs_fields is not None:
        return {field.name: _json_value(getattr(value, field.name)) for field in attrs_fields}
    if hasattr(value, "__dict__"):
        return {
            key: _json_value(item) for key, item in vars(value).items() if not key.startswith("_")
        }
    return str(value)


class WebPoetPageRegistry:
    """Allowlist page classes by stable serialized names."""

    def __init__(self) -> None:
        self._pages: dict[str, type[object]] = {}

    def register(
        self,
        page: type[object],
        *,
        name: str | None = None,
        replace: bool = False,
    ) -> str:
        key = (name or f"{page.__module__}.{page.__qualname__}").strip()
        if not key:
            raise ValueError("WebPoet page name cannot be empty")
        if key in self._pages and not replace:
            raise ValueError(f"WebPoet page already registered: {key}")
        self._pages[key] = page
        return key

    def resolve(self, name: str) -> type[object]:
        try:
            return self._pages[name]
        except KeyError as exc:
            choices = ", ".join(sorted(self._pages)) or "none"
            raise KeyError(f"unknown WebPoet page {name!r}; registered: {choices}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._pages))


class WebPoetService:
    """Execute simple registered page objects using fetchkit for all HTTP."""

    def __init__(
        self,
        fetcher: object,
        *,
        pages: WebPoetPageRegistry | None = None,
        backend: str = "httpx",
    ) -> None:
        self.pages = pages or WebPoetPageRegistry()
        self.http = WebPoetHttpAdapter(fetcher, backend=backend)

    async def extract(
        self,
        page_name: str,
        url: str,
        *,
        page_params: Mapping[str, object] | None = None,
    ) -> tuple[JsonValue, object]:
        """Download and execute a page object's ``to_item`` method."""
        web_poet = _require_web_poet()
        response = await self.http.download(web_poet.HttpRequest(url))
        page_type = self.pages.resolve(page_name)
        signature = inspect.signature(page_type)
        hints = get_type_hints(page_type.__init__)
        values: dict[str, object] = {}
        known = {
            web_poet.HttpResponse: response,
            web_poet.HttpClient: self.http.http_client(),
            web_poet.PageParams: web_poet.PageParams(page_params or {}),
            web_poet.RequestUrl: web_poet.RequestUrl(url),
            web_poet.ResponseUrl: web_poet.ResponseUrl(str(response.url)),  # type: ignore[attr-defined]
        }
        unresolved: list[str] = []
        for name, parameter in signature.parameters.items():
            annotation = hints.get(name, parameter.annotation)
            if annotation in known:
                values[name] = known[annotation]
            elif parameter.default is inspect.Parameter.empty:
                unresolved.append(name)
        if unresolved:
            names = ", ".join(unresolved)
            raise TypeError(
                f"standalone WebPoet page has unresolved inputs: {names}; "
                "use scrapy-poet for custom providers, overrides, and complex dependency graphs"
            )
        page = page_type(**values)
        to_item = getattr(page, "to_item", None)
        if not callable(to_item):
            raise TypeError(f"registered WebPoet page {page_name!r} has no to_item()")
        item = to_item()
        if inspect.isawaitable(item):
            item = await item
        return _json_value(item), response


class WebPoetInput(BaseModel):
    """Serializable input for the built-in WebPoet extraction template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page: str
    page_params: dict[str, JsonValue] = Field(default_factory=dict)
    store_response: bool = False
    storage_prefix: str = "webpoet"


class WebPoetTemplate:
    """Execute an allowlisted WebPoet page as a versioned job template."""

    name = "webpoet.extract"
    version = "1"
    input_model = WebPoetInput

    async def execute(self, job: JobRequest, context: JobContext) -> JobResult:
        started = datetime.now(UTC)
        if job.target is None:
            raise ValueError("WebPoet jobs require target URL")
        spec = WebPoetInput.model_validate(job.payload)
        service = context.require("webpoet")
        if not isinstance(service, WebPoetService):
            raise TypeError("runtime service 'webpoet' must be WebPoetService")
        item, response = await service.extract(
            spec.page,
            job.target,
            page_params=spec.page_params,
        )
        artifacts: tuple[ArtifactRef, ...] = ()
        if spec.store_response:
            if context.blob_store is None:
                raise RuntimeError("store_response requires a JobContext blob_store")
            body = bytes(response.body)  # type: ignore[attr-defined]
            key = f"{spec.storage_prefix.rstrip('/')}/{job.id}.html"
            blob = await context.blob_store.put_bytes(
                key,
                body,
                media_type=response.headers.get("Content-Type"),  # type: ignore[attr-defined]
                metadata={"source_url": str(response.url)},  # type: ignore[attr-defined]
            )
            artifacts = (
                ArtifactRef(
                    kind="web_response",
                    source_url=str(response.url),  # type: ignore[attr-defined]
                    blob=blob,
                    media_type=response.headers.get("Content-Type"),  # type: ignore[attr-defined]
                ),
            )
        return JobResult.succeeded(
            job,
            output={"page": spec.page, "item": item},
            artifacts=artifacts,
            started_at=started,
        )


__all__ = [
    "WebPoetHttpAdapter",
    "WebPoetInput",
    "WebPoetPageRegistry",
    "WebPoetService",
    "WebPoetTemplate",
    "to_webpoet_response",
]
