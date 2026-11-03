"""Tests for provider-neutral acquisition services and built-in adapters."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, Field, SecretStr

from pyfetcher.acquisition import (
    AcquisitionCredentials,
    AcquisitionRequest,
    AcquisitionResult,
    AcquisitionService,
    DownloaderAcquisitionProvider,
    DownloaderContext,
    ProviderCapabilities,
    ProviderNotFoundError,
    ProviderOperationError,
    ProviderUnavailableError,
)
from pyfetcher.acquisition.models import AcquisitionProvenance
from pyfetcher.acquisition.providers import (
    DirectAcquisitionProvider,
    GalleryDlAcquisitionProvider,
    YtdlpAcquisitionProvider,
)
from pyfetcher.downloaders.base import DownloadProgress, DownloadResult, MediaInfo


class FakeProvider:
    name = "fake"

    def __init__(self, *, score: int = 50, available: bool = True) -> None:
        self._score = score
        self._available = available
        self.closed = False
        self.credentials: AcquisitionCredentials | None = None

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.name,
            available=self._available,
            operations=frozenset({"metadata", "download"}),
            install_extra="fetchkit[fake]",
            unavailable_reason=None if self._available else "fake SDK missing",
        )

    def score(self, request: AcquisitionRequest) -> int | None:
        return self._score

    async def acquire(
        self,
        request: AcquisitionRequest,
        *,
        credentials=None,
        emit=None,
        selected_automatically: bool = False,
    ) -> AcquisitionResult:
        self.credentials = credentials
        return AcquisitionResult(
            source_url=request.url.unicode_string(),
            operation=request.operation,
            provider=self.name,
            media=(MediaInfo(url=request.url.unicode_string()),),
            provenance=AcquisitionProvenance(
                provider=self.name,
                selected_automatically=selected_automatically,
            ),
        )

    async def aclose(self) -> None:
        self.closed = True


class CustomDownloaderOptions(BaseModel):
    quality: int = Field(ge=1, le=100)


class StreamingCustomDownloader:
    def __init__(self) -> None:
        self.closed = False

    def extract_info(self, url: str):
        async def generate():
            yield MediaInfo(url=url, title="custom item", provider="custom_dl")

        return generate()

    def download(self, url: str, *, output_dir=None, progress_callback=None):
        async def generate():
            if progress_callback is not None:
                progress_callback(
                    DownloadProgress(
                        status="downloading",
                        downloaded_bytes=4,
                        total_bytes=4,
                        percent=100,
                    )
                )
            yield DownloadResult(
                source_url=url,
                local_path=str(Path(output_dir or ".") / "custom.bin"),
                filename="custom.bin",
                file_size_bytes=4,
            )

        return generate()

    async def aclose(self) -> None:
        self.closed = True


def test_acquisition_request_normalizes_provider_and_serializes_reference() -> None:
    request = AcquisitionRequest(
        url="https://example.com/video",
        provider="YT-DLP",
        credential_ref="media-account",
    )

    assert request.provider == "yt_dlp"
    assert request.model_dump(mode="json")["credential_ref"] == "media-account"


def test_acquisition_request_rejects_invalid_proxy() -> None:
    with pytest.raises(ValueError, match=r"absolute HTTP\(S\) URL"):
        AcquisitionRequest(url="https://example.com/video", proxy="localhost:8080")


def test_acquisition_request_normalizes_namespaced_provider_options() -> None:
    request = AcquisitionRequest(
        url="https://example.com/video",
        yt_dlp_options={"format": "best"},
        provider_options={
            "Custom-DL": {"quality": 80},
            "YT-DLP": {"noplaylist": True},
        },
    )

    assert request.provider_options["custom_dl"] == {"quality": 80}
    assert request.options_for("yt-dlp") == {
        "noplaylist": True,
        "format": "best",
    }


def test_provider_capability_json_sorts_operations() -> None:
    capabilities = ProviderCapabilities(
        name="custom",
        available=True,
        operations=frozenset({"metadata", "download"}),
    )

    assert capabilities.model_dump(mode="json")["operations"] == ["download", "metadata"]


async def test_service_auto_selects_highest_score_and_runs_middleware() -> None:
    low = FakeProvider(score=10)
    low.name = "low"
    high = FakeProvider(score=90)
    high.name = "high"
    observed: list[str] = []

    async def middleware(request: AcquisitionRequest, call_next):
        observed.append(request.provider)
        return await call_next(request)

    service = AcquisitionService(providers=[low, high], middleware=[middleware])
    result = await service.acquire(AcquisitionRequest(url="https://example.com/item"))

    assert result.provider == "high"
    assert result.provenance.selected_automatically is True
    assert observed == ["auto"]


async def test_custom_downloader_factory_supports_options_credentials_and_async_items() -> None:
    contexts: list[DownloaderContext] = []
    downloaders: list[StreamingCustomDownloader] = []

    async def factory(context: DownloaderContext) -> StreamingCustomDownloader:
        contexts.append(context)
        downloader = StreamingCustomDownloader()
        downloaders.append(downloader)
        return downloader

    provider = DownloaderAcquisitionProvider(
        "Custom-DL",
        factory=factory,
        url_patterns=("*.example.com",),
        auto_score=95,
        priority=20,
        options_model=CustomDownloaderOptions,
        extractor="custom-extractor",
    )

    async def resolve(reference: str) -> AcquisitionCredentials:
        assert reference == "custom-account"
        return AcquisitionCredentials(username="agent")

    service = AcquisitionService(providers=[provider], credential_resolver=resolve)
    result = await service.acquire(
        AcquisitionRequest(
            url="https://media.example.com/item/1",
            operation="metadata",
            credential_ref="custom-account",
            provider_options={"custom-dl": {"quality": 85}},
        )
    )

    assert result.provider == "custom_dl"
    assert result.provenance.extractor == "custom-extractor"
    assert result.provenance.selected_automatically is True
    assert result.media[0].title == "custom item"
    assert contexts[0].options == {"quality": 85}
    assert contexts[0].credentials is not None
    assert contexts[0].credentials.username == "agent"
    assert downloaders[0].closed is True
    capabilities = provider.capabilities()
    assert capabilities.option_schema["properties"]["quality"]["minimum"] == 1
    assert capabilities.supports_progress is True


async def test_custom_downloader_emits_progress_and_download_items(tmp_path: Path) -> None:
    provider = DownloaderAcquisitionProvider(
        "custom",
        factory=lambda _context: StreamingCustomDownloader(),
        operations=("download",),
    )
    service = AcquisitionService(providers=[provider])
    events = [
        event
        async for event in service.aiter_events(
            AcquisitionRequest(
                url="https://example.com/item",
                provider="custom",
                output_dir=tmp_path,
            )
        )
    ]

    assert [event.kind for event in events] == [
        "started",
        "progress",
        "item",
        "completed",
    ]
    assert events[1].progress is not None
    assert events[1].progress.percent == 100
    assert events[2].download is not None
    assert events[2].download.filename == "custom.bin"


async def test_service_resolves_credentials_by_reference() -> None:
    provider = FakeProvider()
    resolved_refs: list[str] = []

    async def resolve(reference: str) -> AcquisitionCredentials:
        resolved_refs.append(reference)
        return AcquisitionCredentials(username="user", password=SecretStr("secret"))

    service = AcquisitionService(providers=[provider], credential_resolver=resolve)
    await service.acquire(
        AcquisitionRequest(
            url="https://example.com/item",
            provider="fake",
            credential_ref="account-1",
        )
    )

    assert resolved_refs == ["account-1"]
    assert provider.credentials is not None
    assert provider.credentials.password is not None
    assert provider.credentials.password.get_secret_value() == "secret"


async def test_event_stream_yields_started_and_completed() -> None:
    service = AcquisitionService(providers=[FakeProvider()])
    events = [
        event
        async for event in service.aiter_events(
            AcquisitionRequest(url="https://example.com/item", provider="fake")
        )
    ]

    assert [event.kind for event in events] == ["started", "item", "completed"]
    assert events[1].media is not None
    assert events[-1].result is not None


async def test_event_stream_reports_selection_failure_before_raising() -> None:
    service = AcquisitionService(providers=[FakeProvider()])
    events = []

    with pytest.raises(ProviderNotFoundError, match="unknown acquisition provider"):
        async for event in service.aiter_events(
            AcquisitionRequest(url="https://example.com/item", provider="missing")
        ):
            events.append(event)

    assert [event.kind for event in events] == ["failed"]
    assert events[0].provider == "missing"


async def test_unknown_and_unavailable_providers_are_actionable() -> None:
    service = AcquisitionService(providers=[FakeProvider(available=False)])

    with pytest.raises(ProviderNotFoundError, match="registered: fake"):
        await service.acquire(
            AcquisitionRequest(url="https://example.com/item", provider="missing")
        )
    with pytest.raises(ProviderUnavailableError, match=r"fetchkit\[fake\]"):
        await service.acquire(AcquisitionRequest(url="https://example.com/item"))


async def test_explicit_provider_must_support_requested_operation() -> None:
    provider = FakeProvider()
    provider.capabilities = lambda: ProviderCapabilities(  # type: ignore[method-assign]
        name="fake",
        available=True,
        operations=frozenset({"metadata"}),
    )
    service = AcquisitionService(providers=[provider])

    with pytest.raises(ProviderOperationError, match="supported operations: metadata"):
        await service.acquire(
            AcquisitionRequest(
                url="https://example.com/item",
                operation="download",
                provider="fake",
            )
        )


async def test_service_closes_registered_providers() -> None:
    provider = FakeProvider()
    service = AcquisitionService(providers=[provider])
    await service.aclose()
    assert provider.closed is True


def test_service_loads_provider_entry_points_explicitly(monkeypatch) -> None:
    provider = FakeProvider()

    class FakeEntryPoint:
        name = "fake"

        @staticmethod
        def load():
            return lambda: provider

    def discovered(*, group: str):
        assert group == "fetchkit.acquisition.providers"
        return (FakeEntryPoint(),)

    monkeypatch.setattr(
        "pyfetcher.acquisition.service.package_entry_points",
        discovered,
    )
    service = AcquisitionService(providers=[])

    assert service.load_entry_points() == ("fake",)
    assert [capability.name for capability in service.capabilities()] == ["fake"]


async def test_direct_adapter_rejects_provider_managed_option_collisions() -> None:
    provider = DirectAcquisitionProvider(fetch_service=object())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="provider-managed fields: headers"):
        await provider.acquire(
            AcquisitionRequest(
                url="https://example.com/file.zip",
                provider="direct",
                direct_options={"headers": {"X-Other": "value"}},
            )
        )


async def test_direct_adapter_rejects_unsupported_resolved_credentials() -> None:
    provider = DirectAcquisitionProvider(fetch_service=object())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="does not support credentials: username"):
        await provider.acquire(
            AcquisitionRequest(url="https://example.com/file.zip", provider="direct"),
            credentials=AcquisitionCredentials(username="user"),
        )


async def test_ytdlp_adapter_preserves_shared_and_native_options(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class FakeDownloader:
        DEFAULT_FORMAT = "default"

        def __init__(self, *, format_spec: str, extra_opts: dict) -> None:
            captured["format"] = format_spec
            captured["options"] = extra_opts

        async def extract_info(self, url: str):
            return [MediaInfo(url=url, extra={"extractor_key": "Youtube"})]

        async def download(self, url: str, *, output_dir=None, progress_callback=None):
            return [DownloadResult(source_url=url, local_path=str(Path(output_dir) / "x.mp4"))]

    monkeypatch.setattr("pyfetcher.acquisition.providers.YtdlpDownloader", FakeDownloader)
    request = AcquisitionRequest(
        url="https://youtube.com/watch?v=abc",
        provider="yt_dlp",
        output_dir=tmp_path,
        headers={"authorization": "Bearer value"},
        cookies={"session": "cookie-value"},
        proxy="http://proxy.example:8080",
        filename_template="%(id)s.%(ext)s",
        yt_dlp_options={"format": "best", "noplaylist": True},
    )

    result = await YtdlpAcquisitionProvider().acquire(
        request,
        credentials=AcquisitionCredentials(username="user", password=SecretStr("pass")),
    )

    assert result.provider == "yt_dlp"
    assert captured["format"] == "best"
    options = captured["options"]
    assert isinstance(options, dict)
    assert options["proxy"] == "http://proxy.example:8080"
    assert options["username"] == "user"
    assert options["password"] == "pass"
    assert options["noplaylist"] is True
    assert options["http_headers"] == {
        "authorization": "Bearer value",
        "Cookie": "session=cookie-value",
    }


async def test_ytdlp_download_provenance_uses_download_media_info(monkeypatch) -> None:
    class FakeDownloader:
        DEFAULT_FORMAT = "default"

        def __init__(self, *, format_spec: str, extra_opts: dict) -> None:
            pass

        async def extract_info(self, url: str):
            return []

        async def download(self, url: str, *, output_dir=None, progress_callback=None):
            return [
                DownloadResult(
                    source_url=url,
                    media_info=MediaInfo(url=url, extra={"extractor": "youtube"}),
                )
            ]

    monkeypatch.setattr("pyfetcher.acquisition.providers.YtdlpDownloader", FakeDownloader)
    result = await YtdlpAcquisitionProvider().acquire(
        AcquisitionRequest(url="https://youtube.com/watch?v=abc", provider="yt_dlp")
    )

    assert result.provenance.extractor == "youtube"


async def test_gallery_adapter_keeps_gallery_options_isolated(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeDownloader:
        def __init__(self, *, extra_config: dict) -> None:
            captured.update(extra_config)

        async def extract_info(self, url: str):
            return [MediaInfo(url=url, extra={"category": "imgur"})]

        async def download(self, url: str, *, output_dir=None, progress_callback=None):
            return []

    monkeypatch.setattr("pyfetcher.acquisition.providers.GalleryDlDownloader", FakeDownloader)
    request = AcquisitionRequest(
        url="https://imgur.com/a/example",
        operation="metadata",
        provider="gallery_dl",
        cookies={"session": "value"},
        timeout_seconds=12,
        gallery_dl_options={"range": "1-5"},
    )

    result = await GalleryDlAcquisitionProvider().acquire(request)

    assert result.provenance.extractor == "imgur"
    assert captured["cookies"] == {"session": "value"}
    assert captured["range"] == "1-5"
    assert captured["retries"] == 3
    assert captured["timeout"] == 12
