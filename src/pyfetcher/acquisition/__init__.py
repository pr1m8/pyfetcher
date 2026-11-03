"""Provider-neutral metadata and content acquisition APIs."""

from pyfetcher.acquisition.base import (
    AcquisitionError,
    AcquisitionProvider,
    ProviderNotFoundError,
    ProviderOperationError,
    ProviderUnavailableError,
)
from pyfetcher.acquisition.custom import (
    AvailabilityCheck,
    DownloaderAcquisitionProvider,
    DownloaderContext,
    DownloaderFactory,
    ProviderScorer,
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
from pyfetcher.acquisition.providers import (
    DirectAcquisitionProvider,
    GalleryDlAcquisitionProvider,
    YtdlpAcquisitionProvider,
)
from pyfetcher.acquisition.service import AcquisitionService, CredentialResolver

__all__ = [
    "AcquisitionCredentials",
    "AcquisitionError",
    "AcquisitionEvent",
    "AcquisitionOperation",
    "AcquisitionProvider",
    "AcquisitionProvenance",
    "AcquisitionRequest",
    "AcquisitionResult",
    "AcquisitionService",
    "AvailabilityCheck",
    "CredentialResolver",
    "DirectAcquisitionProvider",
    "DownloaderAcquisitionProvider",
    "DownloaderContext",
    "DownloaderFactory",
    "GalleryDlAcquisitionProvider",
    "ProviderCapabilities",
    "ProviderNotFoundError",
    "ProviderOperationError",
    "ProviderScorer",
    "ProviderUnavailableError",
    "YtdlpAcquisitionProvider",
]
