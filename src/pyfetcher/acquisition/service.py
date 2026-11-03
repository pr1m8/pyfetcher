"""Provider registry, selection, middleware, and async event streaming."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from importlib.metadata import entry_points as package_entry_points
from typing import cast

from pyfetcher.acquisition.base import (
    AcquisitionEventSink,
    AcquisitionProvider,
    ProviderNotFoundError,
    ProviderOperationError,
    ProviderUnavailableError,
)
from pyfetcher.acquisition.models import (
    AcquisitionCredentials,
    AcquisitionEvent,
    AcquisitionRequest,
    AcquisitionResult,
    ProviderCapabilities,
)
from pyfetcher.acquisition.providers import (
    DirectAcquisitionProvider,
    GalleryDlAcquisitionProvider,
    YtdlpAcquisitionProvider,
)
from pyfetcher.middleware import AsyncMiddleware, compose_async

type CredentialResolver = Callable[
    [str],
    AcquisitionCredentials | Awaitable[AcquisitionCredentials],
]


class AcquisitionService:
    """Select and execute acquisition providers behind one typed API."""

    def __init__(
        self,
        *,
        providers: Iterable[AcquisitionProvider] | None = None,
        credential_resolver: CredentialResolver | None = None,
        middleware: Iterable[AsyncMiddleware[AcquisitionRequest, AcquisitionResult]] = (),
    ) -> None:
        resolved_providers = (
            providers
            if providers is not None
            else (
                DirectAcquisitionProvider(),
                YtdlpAcquisitionProvider(),
                GalleryDlAcquisitionProvider(),
            )
        )
        self._providers: dict[str, AcquisitionProvider] = {}
        for provider in resolved_providers:
            self.register(provider)
        self._credential_resolver = credential_resolver
        self._middleware = tuple(middleware)

    def register(self, provider: AcquisitionProvider, *, replace: bool = False) -> None:
        """Register a provider by its stable name."""
        name = provider.name.strip().lower().replace("-", "_")
        if not name:
            raise ValueError("provider name cannot be empty")
        if name in self._providers and not replace:
            raise ValueError(f"provider already registered: {name}")
        self._providers[name] = provider

    def load_entry_points(
        self,
        *,
        group: str = "fetchkit.acquisition.providers",
        replace: bool = False,
    ) -> tuple[str, ...]:
        """Load explicitly installed provider plugins from package entry points.

        Loading is opt-in because importing a plugin executes third-party code.
        Each entry point may expose a provider instance, provider class, or
        zero-argument factory returning a provider.
        """
        registered: list[str] = []
        for entry_point in package_entry_points(group=group):
            loaded = entry_point.load()
            if inspect.isclass(loaded):
                loaded = loaded()
            elif not all(
                hasattr(loaded, attribute)
                for attribute in ("name", "capabilities", "score", "acquire", "aclose")
            ):
                if not callable(loaded):
                    raise TypeError(
                        f"acquisition provider entry point {entry_point.name!r} "
                        "must expose a provider or zero-argument factory"
                    )
                loaded = loaded()
            if inspect.isawaitable(loaded):
                raise TypeError(
                    f"acquisition provider entry point {entry_point.name!r} "
                    "cannot use an async factory"
                )
            if not all(
                hasattr(loaded, attribute)
                for attribute in ("name", "capabilities", "score", "acquire", "aclose")
            ):
                raise TypeError(
                    f"acquisition provider entry point {entry_point.name!r} "
                    "did not return a complete provider"
                )
            provider = cast(AcquisitionProvider, loaded)
            self.register(provider, replace=replace)
            registered.append(provider.name)
        return tuple(registered)

    def capabilities(self) -> tuple[ProviderCapabilities, ...]:
        """Return capabilities for every registered provider."""
        return tuple(provider.capabilities() for provider in self._providers.values())

    def resolve(self, request: AcquisitionRequest) -> tuple[AcquisitionProvider, bool]:
        """Resolve an explicit or automatically selected provider."""
        if request.provider != "auto":
            provider = self._providers.get(request.provider)
            if provider is None:
                choices = ", ".join(sorted(self._providers)) or "none"
                raise ProviderNotFoundError(
                    f"unknown acquisition provider {request.provider!r}; registered: {choices}"
                )
            self._ensure_operation(provider, request)
            self._ensure_available(provider)
            return provider, False

        candidates = []
        for provider in self._providers.values():
            capabilities = provider.capabilities()
            score = provider.score(request)
            if request.operation in capabilities.operations and score is not None:
                candidates.append((score, capabilities.priority, provider))
        if not candidates:
            raise ProviderNotFoundError(
                f"no acquisition provider supports {request.operation!r} for {request.url}"
            )
        _, _, provider = max(candidates, key=lambda item: (item[0], item[1], item[2].name))
        self._ensure_available(provider)
        return provider, True

    @staticmethod
    def _ensure_operation(
        provider: AcquisitionProvider,
        request: AcquisitionRequest,
    ) -> None:
        operations = provider.capabilities().operations
        if request.operation not in operations:
            choices = ", ".join(sorted(operations)) or "none"
            raise ProviderOperationError(
                f"provider {provider.name!r} does not support {request.operation!r}; "
                f"supported operations: {choices}"
            )

    @staticmethod
    def _ensure_available(provider: AcquisitionProvider) -> None:
        capabilities = provider.capabilities()
        if capabilities.available:
            return
        install = (
            f"; install with `pip install '{capabilities.install_extra}'`"
            if capabilities.install_extra
            else ""
        )
        reason = capabilities.unavailable_reason or "optional dependency unavailable"
        raise ProviderUnavailableError(
            f"provider {provider.name!r} is unavailable: {reason}{install}"
        )

    async def _resolve_credentials(
        self,
        request: AcquisitionRequest,
    ) -> AcquisitionCredentials | None:
        if request.credential_ref is None:
            return None
        if self._credential_resolver is None:
            raise ValueError("credential_ref requires an AcquisitionService credential_resolver")
        resolved = self._credential_resolver(request.credential_ref)
        return await resolved if inspect.isawaitable(resolved) else resolved

    async def _acquire_impl(
        self,
        request: AcquisitionRequest,
        emit: AcquisitionEventSink | None,
    ) -> AcquisitionResult:
        source_url = request.url.unicode_string()
        provider_name = request.provider
        try:
            provider, selected_automatically = self.resolve(request)
            provider_name = provider.name
            if emit is not None:
                emit(
                    AcquisitionEvent(
                        kind="started",
                        source_url=source_url,
                        provider=provider_name,
                    )
                )
            credentials = await self._resolve_credentials(request)
            result = await provider.acquire(
                request,
                credentials=credentials,
                emit=emit,
                selected_automatically=selected_automatically,
            )
        except Exception as exc:
            if emit is not None:
                emit(
                    AcquisitionEvent(
                        kind="failed",
                        source_url=source_url,
                        provider=provider_name,
                        message=str(exc),
                    )
                )
            raise
        if emit is not None:
            for media in result.media:
                emit(
                    AcquisitionEvent(
                        kind="item",
                        source_url=source_url,
                        provider=provider_name,
                        media=media,
                    )
                )
            for download in result.downloads:
                emit(
                    AcquisitionEvent(
                        kind="item",
                        source_url=source_url,
                        provider=provider_name,
                        download=download,
                    )
                )
            emit(
                AcquisitionEvent(
                    kind="completed",
                    source_url=source_url,
                    provider=provider_name,
                    result=result,
                )
            )
        return result

    async def acquire(
        self,
        request: AcquisitionRequest,
        *,
        event_callback: AcquisitionEventSink | None = None,
    ) -> AcquisitionResult:
        """Acquire metadata or content through the selected provider."""

        async def handler(value: AcquisitionRequest) -> AcquisitionResult:
            return await self._acquire_impl(value, event_callback)

        return await compose_async(handler, self._middleware)(request)

    async def aiter_events(self, request: AcquisitionRequest) -> AsyncIterator[AcquisitionEvent]:
        """Run an acquisition and yield progress events without blocking provider threads."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[AcquisitionEvent | None] = asyncio.Queue()

        def emit(event: AcquisitionEvent) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        async def run() -> AcquisitionResult:
            try:
                return await self.acquire(request, event_callback=emit)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        task = asyncio.create_task(run())
        try:
            while (event := await queue.get()) is not None:
                yield event
            await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def aclose(self) -> None:
        """Close every registered provider that owns resources."""
        await asyncio.gather(
            *(provider.aclose() for provider in self._providers.values()),
            return_exceptions=False,
        )

    async def __aenter__(self) -> AcquisitionService:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


__all__ = ["AcquisitionService", "CredentialResolver"]
