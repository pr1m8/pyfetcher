"""Adapters for application-defined acquisition downloaders.

Purpose:
    Let small downloader implementations participate in provider selection,
    credentials, progress events, capability discovery, and durable jobs.

Design:
    The downloader factory is runtime-only. Requests contain only a stable
    provider name and JSON-safe namespaced options.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, cast

from pydantic import BaseModel

from pyfetcher.acquisition.base import (
    AcquisitionEventSink,
    ProviderOperationError,
)
from pyfetcher.acquisition.models import (
    AcquisitionCredentials,
    AcquisitionEvent,
    AcquisitionOperation,
    AcquisitionProvenance,
    AcquisitionRequest,
    AcquisitionResult,
    ProviderCapabilities,
)
from pyfetcher.downloaders.base import (
    DownloaderProtocol,
    DownloadProgress,
    DownloadResult,
    MediaInfo,
)


@dataclass(frozen=True, slots=True)
class DownloaderContext:
    """Runtime inputs used to construct one custom downloader."""

    request: AcquisitionRequest
    credentials: AcquisitionCredentials | None
    options: Mapping[str, Any]


type DownloaderFactory = Callable[
    [DownloaderContext],
    DownloaderProtocol | Awaitable[DownloaderProtocol],
]
type ProviderScorer = Callable[[AcquisitionRequest], int | None]
type AvailabilityCheck = Callable[[], bool]


async def _collect[ItemT](value: object, expected: type[ItemT]) -> tuple[ItemT, ...]:
    if inspect.isawaitable(value):
        value = await value
    if isinstance(value, AsyncIterable):
        items = [item async for item in value]
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value)
    else:
        raise TypeError("custom downloader methods must return an iterable or async iterable")
    for item in items:
        if not isinstance(item, expected):
            raise TypeError(
                f"custom downloader returned {type(item).__name__}; expected {expected.__name__}"
            )
    return tuple(cast(list[ItemT], items))


async def _close(value: object) -> None:
    close = getattr(value, "aclose", None) or getattr(value, "close", None)
    if not callable(close):
        return
    result = close()
    if inspect.isawaitable(result):
        await result


class DownloaderAcquisitionProvider:
    """Adapt a small downloader or request-scoped factory as a provider.

    Pass a shared ``downloader`` when it owns a reusable pool or session. Pass
    ``factory`` when downloader construction depends on request options or
    resolved credentials; factory-created instances are closed after each
    acquisition.
    """

    def __init__(
        self,
        name: str,
        *,
        downloader: DownloaderProtocol | None = None,
        factory: DownloaderFactory | None = None,
        operations: Iterable[AcquisitionOperation] = ("metadata", "download"),
        scorer: ProviderScorer | None = None,
        auto_score: int | None = None,
        priority: int = 0,
        url_patterns: Iterable[str] = (),
        options_model: type[BaseModel] | None = None,
        available: bool | AvailabilityCheck = True,
        install_extra: str | None = None,
        unavailable_reason: str | None = None,
        extractor: str | None = None,
    ) -> None:
        normalized = name.strip().lower().replace("-", "_")
        if not normalized:
            raise ValueError("provider name cannot be empty")
        if (downloader is None) == (factory is None):
            raise ValueError("provide exactly one of downloader or factory")
        resolved_operations = frozenset(operations)
        if not resolved_operations:
            raise ValueError("custom downloader must support at least one operation")
        unsupported = resolved_operations.difference({"metadata", "download"})
        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise ValueError(f"unsupported custom downloader operations: {names}")
        self.name = normalized
        self._downloader = downloader
        self._factory = factory
        self._operations = resolved_operations
        self._scorer = scorer
        self._auto_score = auto_score
        self._priority = priority
        self._url_patterns = tuple(url_patterns)
        self._options_model = options_model
        self._available = available
        self._install_extra = install_extra
        self._unavailable_reason = unavailable_reason
        self._extractor = extractor
        self._closed = False

    def _availability(self) -> tuple[bool, str | None]:
        if isinstance(self._available, bool):
            return self._available, self._unavailable_reason
        try:
            return bool(self._available()), self._unavailable_reason
        except Exception as exc:
            return False, self._unavailable_reason or str(exc)

    def capabilities(self) -> ProviderCapabilities:
        available, reason = self._availability()
        return ProviderCapabilities(
            name=self.name,
            available=available,
            operations=self._operations,
            priority=self._priority,
            url_patterns=self._url_patterns,
            install_extra=self._install_extra,
            unavailable_reason=None if available else (reason or "provider dependency unavailable"),
            option_schema=(
                self._options_model.model_json_schema() if self._options_model is not None else {}
            ),
            supports_progress="download" in self._operations,
        )

    def _matches_patterns(self, request: AcquisitionRequest) -> bool:
        url = request.url.unicode_string()
        host = request.url.host or ""
        return any(
            fnmatchcase(url, pattern) if "://" in pattern else fnmatchcase(host, pattern)
            for pattern in self._url_patterns
        )

    def score(self, request: AcquisitionRequest) -> int | None:
        if self._scorer is not None:
            return self._scorer(request)
        if self._url_patterns and not self._matches_patterns(request):
            return None
        if self._auto_score is not None:
            return self._auto_score
        return 50 if self._url_patterns else None

    def _options(self, request: AcquisitionRequest) -> dict[str, Any]:
        options = request.options_for(self.name)
        if self._options_model is None:
            return options
        return self._options_model.model_validate(options).model_dump(mode="python")

    async def _resolve_downloader(
        self,
        context: DownloaderContext,
    ) -> tuple[DownloaderProtocol, bool]:
        if self._downloader is not None:
            return self._downloader, False
        assert self._factory is not None
        value = self._factory(context)
        downloader = await value if inspect.isawaitable(value) else value
        return downloader, True

    @staticmethod
    def _progress_sink(
        request: AcquisitionRequest,
        provider: str,
        emit: AcquisitionEventSink | None,
    ) -> Callable[[DownloadProgress], None]:
        def callback(progress: DownloadProgress) -> None:
            if emit is not None:
                emit(
                    AcquisitionEvent(
                        kind="progress",
                        source_url=request.url.unicode_string(),
                        provider=provider,
                        progress=progress,
                    )
                )

        return callback

    async def acquire(
        self,
        request: AcquisitionRequest,
        *,
        credentials: AcquisitionCredentials | None = None,
        emit: AcquisitionEventSink | None = None,
        selected_automatically: bool = False,
    ) -> AcquisitionResult:
        if request.operation not in self._operations:
            supported = ", ".join(sorted(self._operations))
            raise ProviderOperationError(
                f"provider {self.name!r} does not support {request.operation!r}; "
                f"supported operations: {supported}"
            )
        context = DownloaderContext(
            request=request,
            credentials=credentials,
            options=self._options(request),
        )
        downloader, request_scoped = await self._resolve_downloader(context)
        source_url = request.url.unicode_string()
        try:
            if request.operation == "metadata":
                extract_info = getattr(downloader, "extract_info", None)
                if not callable(extract_info):
                    raise ProviderOperationError(
                        f"custom downloader {self.name!r} does not provide extract_info()"
                    )
                media = await _collect(extract_info(source_url), MediaInfo)
                downloads: tuple[DownloadResult, ...] = ()
            else:
                download = getattr(downloader, "download", None)
                if not callable(download):
                    raise ProviderOperationError(
                        f"custom downloader {self.name!r} does not provide download()"
                    )
                downloads = await _collect(
                    download(
                        source_url,
                        output_dir=str(request.output_dir) if request.output_dir else None,
                        progress_callback=self._progress_sink(request, self.name, emit),
                    ),
                    DownloadResult,
                )
                media = ()
        finally:
            if request_scoped:
                await _close(downloader)
        return AcquisitionResult(
            source_url=source_url,
            operation=request.operation,
            provider=self.name,
            media=media,
            downloads=downloads,
            provenance=AcquisitionProvenance(
                provider=self.name,
                extractor=self._extractor,
                selected_automatically=selected_automatically,
            ),
        )

    async def aclose(self) -> None:
        if not self._closed and self._downloader is not None:
            await _close(self._downloader)
        self._closed = True


__all__ = [
    "AvailabilityCheck",
    "DownloaderAcquisitionProvider",
    "DownloaderContext",
    "DownloaderFactory",
    "ProviderScorer",
]
