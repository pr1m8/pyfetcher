"""pyfetcher - Advanced web fetching and scraping toolkit.

Purpose:
    Provide a reusable, transport-agnostic toolkit for HTTP fetching, web
    scraping, realistic browser header generation, and content extraction.
    Supports multiple backends (httpx, aiohttp), per-domain rate limiting,
    retry with exponential backoff, CLI and TUI interfaces, and comprehensive
    scraping utilities.

Design:
    - ``contracts`` defines validated request/response/policy models.
    - ``headers`` provides realistic browser header generation with full
      profile support (Chrome, Firefox, Safari, Edge across platforms).
    - ``retry`` adapts policy models to :mod:`tenacity`.
    - ``ratelimit`` provides per-domain and global rate limiting.
    - ``transports`` encapsulate concrete backend implementations.
    - ``fetch`` exposes the ergonomic function and service APIs.
    - ``scrape`` provides CSS selector extraction, link harvesting, form
      parsing, robots.txt support, sitemap parsing, and content extraction.
    - ``metadata`` parses page metadata after fetch.
    - ``download`` provides file-oriented helpers built on streaming.
    - ``cli`` provides a command-line interface.
    - ``tui`` provides an interactive terminal UI.

Public API:
    - :class:`~pyfetcher.contracts.url.URL`
    - :class:`~pyfetcher.contracts.request.FetchRequest`
    - :class:`~pyfetcher.contracts.response.FetchResponse`
    - :class:`~pyfetcher.contracts.policy.RetryPolicy`
    - :class:`~pyfetcher.contracts.policy.TimeoutPolicy`
    - :class:`~pyfetcher.contracts.policy.PoolPolicy`
    - :class:`~pyfetcher.contracts.policy.StreamPolicy`
    - :class:`~pyfetcher.fetch.client.FetchClient`
    - :class:`~pyfetcher.fetch.client.AsyncFetchClient`
    - :class:`~pyfetcher.fetch.service.FetchService`
    - :func:`~pyfetcher.fetch.functions.fetch`
    - :func:`~pyfetcher.fetch.functions.afetch`
    - :func:`~pyfetcher.fetch.functions.afetch_many`
    - :func:`~pyfetcher.fetch.functions.astream`
    - :func:`~pyfetcher.fetch.functions.stream`
    - :class:`~pyfetcher.headers.browser.BrowserHeaderProvider`
    - :class:`~pyfetcher.headers.rotating.RotatingHeaderProvider`
    - :func:`~pyfetcher.headers.ua.random_user_agent`
    - :class:`~pyfetcher.ratelimit.limiter.DomainRateLimiter`
    - :class:`~pyfetcher.ratelimit.limiter.RateLimitPolicy`

Examples:
    ::

        >>> from pyfetcher import FetchRequest
        >>> request = FetchRequest(url="https://example.com")
        >>> request.method
        'GET'
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fetchkit")
except PackageNotFoundError:  # pragma: no cover - source tree without package metadata
    __version__ = "0+unknown"

from pyfetcher.acquisition import (
    AcquisitionCredentials,
    AcquisitionEvent,
    AcquisitionRequest,
    AcquisitionResult,
    AcquisitionService,
    DownloaderAcquisitionProvider,
    DownloaderContext,
    ProviderCapabilities,
)
from pyfetcher.artifacts import (
    ArtifactCollection,
    ArtifactRef,
    BlobRef,
    LocalBlobStore,
    MemoryBlobStore,
)
from pyfetcher.contracts.policy import (
    PoolPolicy,
    RetryPolicy,
    StreamPolicy,
    TimeoutPolicy,
)
from pyfetcher.contracts.request import BatchFetchRequest, FetchRequest
from pyfetcher.contracts.response import BatchFetchResponse, FetchResponse, StreamChunk
from pyfetcher.contracts.url import URL, DomainParts
from pyfetcher.contracts.url_adapters import (
    URLAdapter,
    URLAdapterRegistry,
    URLRule,
    apply_url_rules,
)
from pyfetcher.contracts.url_pattern import URLMatch, URLPattern, URLTemplate
from pyfetcher.documents import (
    CollectionRule,
    GalleryRule,
    ImageRule,
    LinkRule,
    ModelExtractor,
    PageDocument,
    PageRule,
    SelectorFunctionRegistry,
    SelectorRule,
    extract_collection,
    extract_gallery,
    extract_images,
    extract_page_links,
)
from pyfetcher.extraction import (
    CallableExtractor,
    ExtractionContext,
    ExtractionResult,
    ExtractorRegistry,
    default_extractor_registry,
)
from pyfetcher.jobs import (
    FlowRequest,
    FlowResult,
    InProcessJobRuntime,
    JobContext,
    JobExecutor,
    JobRequest,
    JobResult,
    TemplateRef,
    TemplateRegistry,
)
from pyfetcher.media import (
    MediaMetadata,
    ThumbnailInfo,
    ainspect_media,
    generate_thumbnail,
    inspect_media,
    process_image,
)
from pyfetcher.middleware import AsyncMiddleware, SyncMiddleware
from pyfetcher.protocol import (
    ContractSchema,
    ProtocolCatalog,
    build_protocol_catalog,
    discover_protocol_catalog,
    export_protocol_catalog,
)
from pyfetcher.search import SearchHit, SearchRequest, SearchResult, SearchService
from pyfetcher.streams import ByteStream

__all__ = [
    "__version__",
    "BatchFetchRequest",
    "BatchFetchResponse",
    "DomainParts",
    "FetchRequest",
    "FetchResponse",
    "PoolPolicy",
    "RetryPolicy",
    "StreamChunk",
    "StreamPolicy",
    "TimeoutPolicy",
    "URL",
    "URLAdapter",
    "URLAdapterRegistry",
    "URLMatch",
    "URLPattern",
    "URLRule",
    "URLTemplate",
    "apply_url_rules",
    "ByteStream",
    "CollectionRule",
    "GalleryRule",
    "ImageRule",
    "LinkRule",
    "ModelExtractor",
    "PageDocument",
    "PageRule",
    "SelectorRule",
    "SelectorFunctionRegistry",
    "extract_collection",
    "extract_gallery",
    "extract_images",
    "extract_page_links",
    "CallableExtractor",
    "ExtractionContext",
    "ExtractionResult",
    "ExtractorRegistry",
    "default_extractor_registry",
    "MediaMetadata",
    "ThumbnailInfo",
    "ainspect_media",
    "generate_thumbnail",
    "inspect_media",
    "process_image",
    "AsyncMiddleware",
    "SyncMiddleware",
    "ContractSchema",
    "ProtocolCatalog",
    "build_protocol_catalog",
    "discover_protocol_catalog",
    "export_protocol_catalog",
    "AcquisitionCredentials",
    "AcquisitionEvent",
    "AcquisitionRequest",
    "AcquisitionResult",
    "AcquisitionService",
    "DownloaderAcquisitionProvider",
    "DownloaderContext",
    "ProviderCapabilities",
    "ArtifactCollection",
    "ArtifactRef",
    "BlobRef",
    "LocalBlobStore",
    "MemoryBlobStore",
    "FlowRequest",
    "FlowResult",
    "InProcessJobRuntime",
    "JobContext",
    "JobExecutor",
    "JobRequest",
    "JobResult",
    "TemplateRef",
    "TemplateRegistry",
    "SearchHit",
    "SearchRequest",
    "SearchResult",
    "SearchService",
]

from pyfetcher.fetch.client import AsyncFetchClient, FetchClient  # noqa: F401, E402
from pyfetcher.fetch.functions import (  # noqa: F401, E402
    afetch,
    afetch_many,
    astream,
    fetch,
    stream,
)
from pyfetcher.fetch.service import FetchService  # noqa: F401, E402
from pyfetcher.headers.browser import BrowserHeaderProvider  # noqa: F401, E402
from pyfetcher.headers.rotating import RotatingHeaderProvider  # noqa: F401, E402
from pyfetcher.headers.ua import random_user_agent  # noqa: F401, E402
from pyfetcher.ratelimit.limiter import (  # noqa: F401, E402
    DomainRateLimiter,
    RateLimitPolicy,
)

__all__.extend(
    [
        "FetchService",
        "FetchClient",
        "AsyncFetchClient",
        "afetch",
        "afetch_many",
        "astream",
        "fetch",
        "stream",
        "BrowserHeaderProvider",
        "RotatingHeaderProvider",
        "random_user_agent",
        "DomainRateLimiter",
        "RateLimitPolicy",
    ]
)
