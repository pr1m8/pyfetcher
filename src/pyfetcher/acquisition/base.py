"""Provider protocol and errors for content acquisition."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from pyfetcher.acquisition.models import (
    AcquisitionCredentials,
    AcquisitionEvent,
    AcquisitionRequest,
    AcquisitionResult,
    ProviderCapabilities,
)

type AcquisitionEventSink = Callable[[AcquisitionEvent], None]


class AcquisitionError(RuntimeError):
    """Base error for acquisition selection and execution."""


class ProviderNotFoundError(AcquisitionError):
    """Raised when a named provider is not registered."""


class ProviderUnavailableError(AcquisitionError):
    """Raised when a provider's optional dependency is unavailable."""


class ProviderOperationError(AcquisitionError):
    """Raised when a provider does not implement the requested operation."""


class AcquisitionProvider(Protocol):
    """Protocol implemented by provider-specific acquisition adapters."""

    name: str

    def capabilities(self) -> ProviderCapabilities: ...

    def score(self, request: AcquisitionRequest) -> int | None: ...

    async def acquire(
        self,
        request: AcquisitionRequest,
        *,
        credentials: AcquisitionCredentials | None = None,
        emit: AcquisitionEventSink | None = None,
        selected_automatically: bool = False,
    ) -> AcquisitionResult: ...

    async def aclose(self) -> None: ...


__all__ = [
    "AcquisitionError",
    "AcquisitionEventSink",
    "AcquisitionProvider",
    "ProviderNotFoundError",
    "ProviderOperationError",
    "ProviderUnavailableError",
]
