"""Built-in direct HTTP, yt-dlp, and gallery-dl acquisition providers."""

from __future__ import annotations

import re
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from pyfetcher.acquisition.base import AcquisitionEventSink
from pyfetcher.acquisition.models import (
    AcquisitionCredentials,
    AcquisitionEvent,
    AcquisitionProvenance,
    AcquisitionRequest,
    AcquisitionResult,
    ProviderCapabilities,
)
from pyfetcher.contracts.policy import RetryPolicy, TimeoutPolicy
from pyfetcher.downloaders.base import DownloadProgress
from pyfetcher.downloaders.direct import DirectDownloader
from pyfetcher.downloaders.gallerydl import GalleryDlDownloader
from pyfetcher.downloaders.ytdlp import YtdlpDownloader
from pyfetcher.fetch.service import FetchService

_DIRECT_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bin",
    ".csv",
    ".epub",
    ".flac",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".json",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".tar",
    ".webm",
    ".webp",
    ".xml",
    ".zip",
}
_VIDEO_HOSTS = re.compile(
    r"(^|\.)(youtube\.com|youtu\.be|vimeo\.com|tiktok\.com|twitch\.tv|"
    r"soundcloud\.com|dailymotion\.com|bilibili\.com)$",
    re.IGNORECASE,
)
_GALLERY_HOSTS = re.compile(
    r"(^|\.)(imgur\.com|pixiv\.net|deviantart\.com|flickr\.com|"
    r"instagram\.com|danbooru\.donmai\.us|gelbooru\.com)$",
    re.IGNORECASE,
)
_DIRECT_RESERVED_OPTIONS = frozenset({"url", "method", "headers", "proxy", "backend"})


def _emit_progress(
    request: AcquisitionRequest,
    provider: str,
    emit: AcquisitionEventSink | None,
):
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


def _credential_options(credentials: AcquisitionCredentials | None) -> dict[str, Any]:
    if credentials is None:
        return {}
    options = dict(credentials.provider_data)
    if credentials.username is not None:
        options.setdefault("username", credentials.username)
    if credentials.password is not None:
        options.setdefault("password", credentials.password.get_secret_value())
    if credentials.cookie_file is not None:
        options.setdefault("cookiefile", str(credentials.cookie_file))
    return options


class DirectAcquisitionProvider:
    """Provider adapter for ordinary streamed HTTP downloads."""

    name = "direct"

    def __init__(self, *, fetch_service: FetchService | None = None) -> None:
        self._service = fetch_service or FetchService()
        self._owns_service = fetch_service is None

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.name,
            available=True,
            operations=frozenset({"metadata", "download"}),
            priority=10,
            url_patterns=("http://*", "https://*"),
            supports_progress=True,
        )

    def score(self, request: AcquisitionRequest) -> int | None:
        if request.url.scheme not in {"http", "https"}:
            return None
        suffix = Path(request.url.path or "").suffix.lower()
        return 70 if suffix in _DIRECT_EXTENSIONS else 10

    async def acquire(
        self,
        request: AcquisitionRequest,
        *,
        credentials: AcquisitionCredentials | None = None,
        emit: AcquisitionEventSink | None = None,
        selected_automatically: bool = False,
    ) -> AcquisitionResult:
        if credentials is not None:
            unsupported = set(credentials.provider_data)
            if credentials.username is not None:
                unsupported.add("username")
            if credentials.password is not None:
                unsupported.add("password")
            if credentials.cookie_file is not None:
                unsupported.add("cookie_file")
            if unsupported:
                names = ", ".join(sorted(unsupported))
                raise ValueError(f"direct provider does not support credentials: {names}")
        options = request.options_for(self.name)
        backend = str(options.pop("backend", "httpx"))
        collisions = sorted(_DIRECT_RESERVED_OPTIONS.intersection(options))
        if collisions:
            names = ", ".join(collisions)
            raise ValueError(f"direct_options cannot override provider-managed fields: {names}")
        if request.timeout_seconds is not None:
            options.setdefault(
                "timeout",
                TimeoutPolicy(
                    total_seconds=request.timeout_seconds,
                    connect_seconds=min(10.0, request.timeout_seconds),
                    read_seconds=request.timeout_seconds,
                    write_seconds=request.timeout_seconds,
                    pool_seconds=min(10.0, request.timeout_seconds),
                ),
            )
        options.setdefault("retry", RetryPolicy(attempts=request.retries + 1))
        downloader = DirectDownloader(
            fetch_service=self._service,
            headers=request.headers,
            cookies=request.cookies,
            proxy=request.proxy,
            backend=backend,
            request_options=options,
        )
        source_url = request.url.unicode_string()
        if request.operation == "metadata":
            media = tuple(await downloader.extract_info(source_url))
            downloads = ()
        else:
            media = ()
            downloads = tuple(
                await downloader.download(
                    source_url,
                    output_dir=str(request.output_dir) if request.output_dir else None,
                    progress_callback=_emit_progress(request, self.name, emit),
                    filename=request.filename_template,
                    overwrite=request.overwrite,
                )
            )
        return AcquisitionResult(
            source_url=source_url,
            operation=request.operation,
            provider=self.name,
            media=media,
            downloads=downloads,
            provenance=AcquisitionProvenance(
                provider=self.name,
                selected_automatically=selected_automatically,
            ),
        )

    async def aclose(self) -> None:
        if self._owns_service:
            await self._service.aclose()


class YtdlpAcquisitionProvider:
    """Provider adapter preserving yt-dlp native option escape hatches."""

    name = "yt_dlp"

    def capabilities(self) -> ProviderCapabilities:
        available = find_spec("yt_dlp") is not None
        return ProviderCapabilities(
            name=self.name,
            available=available,
            operations=frozenset({"metadata", "download"}),
            priority=80,
            url_patterns=("youtube.com", "youtu.be", "vimeo.com", "tiktok.com"),
            install_extra="fetchkit[downloaders]",
            unavailable_reason=None if available else "yt-dlp is not installed",
            supports_progress=True,
        )

    def score(self, request: AcquisitionRequest) -> int | None:
        return 90 if _VIDEO_HOSTS.search(request.url.host or "") else None

    async def acquire(
        self,
        request: AcquisitionRequest,
        *,
        credentials: AcquisitionCredentials | None = None,
        emit: AcquisitionEventSink | None = None,
        selected_automatically: bool = False,
    ) -> AcquisitionResult:
        options = {**_credential_options(credentials), **request.options_for(self.name)}
        headers = dict(request.headers)
        headers.update(options.pop("http_headers", {}))
        has_cookie_header = any(name.lower() == "cookie" for name in headers)
        if request.cookies and not has_cookie_header:
            headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in request.cookies.items()
            )
        if headers:
            options["http_headers"] = headers
        if request.proxy:
            options.setdefault("proxy", request.proxy)
        options.setdefault("retries", request.retries)
        options.setdefault("overwrites", request.overwrite)
        if request.timeout_seconds is not None:
            options.setdefault("socket_timeout", request.timeout_seconds)
        if request.filename_template:
            template = Path(request.filename_template)
            if request.output_dir is not None and not template.is_absolute():
                template = request.output_dir / template
            options.setdefault("outtmpl", str(template))
        format_spec = str(options.pop("format", YtdlpDownloader.DEFAULT_FORMAT))
        downloader = YtdlpDownloader(format_spec=format_spec, extra_opts=options)
        source_url = request.url.unicode_string()
        if request.operation == "metadata":
            media = tuple(await downloader.extract_info(source_url))
            downloads = ()
        else:
            media = ()
            downloads = tuple(
                await downloader.download(
                    source_url,
                    output_dir=str(request.output_dir) if request.output_dir else None,
                    progress_callback=_emit_progress(request, self.name, emit),
                )
            )
        result_media = [*media, *(item.media_info for item in downloads if item.media_info)]
        extractor = next(
            (
                str(item.extra.get("extractor_key") or item.extra.get("extractor"))
                for item in result_media
                if item.extra.get("extractor_key") or item.extra.get("extractor")
            ),
            None,
        )
        return AcquisitionResult(
            source_url=source_url,
            operation=request.operation,
            provider=self.name,
            media=media,
            downloads=downloads,
            provenance=AcquisitionProvenance(
                provider=self.name,
                extractor=extractor,
                selected_automatically=selected_automatically,
            ),
        )

    async def aclose(self) -> None:
        return None


class GalleryDlAcquisitionProvider:
    """Provider adapter preserving gallery-dl native configuration."""

    name = "gallery_dl"

    def capabilities(self) -> ProviderCapabilities:
        available = find_spec("gallery_dl") is not None
        return ProviderCapabilities(
            name=self.name,
            available=available,
            operations=frozenset({"metadata", "download"}),
            priority=70,
            url_patterns=("imgur.com", "pixiv.net", "deviantart.com", "flickr.com"),
            install_extra="fetchkit[downloaders]",
            unavailable_reason=None if available else "gallery-dl is not installed",
            supports_progress=True,
        )

    def score(self, request: AcquisitionRequest) -> int | None:
        return 85 if _GALLERY_HOSTS.search(request.url.host or "") else None

    async def acquire(
        self,
        request: AcquisitionRequest,
        *,
        credentials: AcquisitionCredentials | None = None,
        emit: AcquisitionEventSink | None = None,
        selected_automatically: bool = False,
    ) -> AcquisitionResult:
        config = {**_credential_options(credentials), **request.options_for(self.name)}
        if request.headers:
            config.setdefault("headers", request.headers)
        if request.cookies:
            config.setdefault("cookies", request.cookies)
        if request.proxy:
            config.setdefault("proxy", request.proxy)
        config.setdefault("retries", request.retries)
        if request.timeout_seconds is not None:
            config.setdefault("timeout", request.timeout_seconds)
        if request.filename_template:
            config.setdefault("filename", request.filename_template)
        config.setdefault("skip", not request.overwrite)
        downloader = GalleryDlDownloader(extra_config=config)
        source_url = request.url.unicode_string()
        if request.operation == "metadata":
            media = tuple(await downloader.extract_info(source_url))
            downloads = ()
        else:
            media = ()
            downloads = tuple(
                await downloader.download(
                    source_url,
                    output_dir=str(request.output_dir) if request.output_dir else None,
                    progress_callback=_emit_progress(request, self.name, emit),
                )
            )
        extractor = next(
            (str(item.extra.get("category")) for item in media if item.extra.get("category")),
            None,
        )
        return AcquisitionResult(
            source_url=source_url,
            operation=request.operation,
            provider=self.name,
            media=media,
            downloads=downloads,
            provenance=AcquisitionProvenance(
                provider=self.name,
                extractor=extractor,
                selected_automatically=selected_automatically,
            ),
        )

    async def aclose(self) -> None:
        return None


__all__ = [
    "DirectAcquisitionProvider",
    "GalleryDlAcquisitionProvider",
    "YtdlpAcquisitionProvider",
]
