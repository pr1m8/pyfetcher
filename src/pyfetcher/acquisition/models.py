"""Typed contracts for provider-neutral content acquisition.

Purpose:
    Describe metadata and download operations without flattening yt-dlp,
    gallery-dl, and direct HTTP into one provider-specific option namespace.

Design:
    Shared policy stays on :class:`AcquisitionRequest`; provider-native escape
    hatches remain isolated in explicitly named option dictionaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    computed_field,
    field_serializer,
    field_validator,
)

from pyfetcher.contracts.url import URL
from pyfetcher.downloaders.base import DownloadProgress, DownloadResult, MediaInfo

type AcquisitionOperation = Literal["metadata", "download"]
type AcquisitionEventKind = Literal["started", "progress", "item", "completed", "failed"]


def _provider_name(value: str) -> str:
    return value.strip().lower().replace("-", "_")


class AcquisitionRequest(BaseModel):
    """Provider-neutral acquisition request.

    ``provider="auto"`` uses capability scoring. Set ``provider`` explicitly
    when a URL can reasonably be handled by more than one acquisition engine.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    url: URL
    operation: AcquisitionOperation = "download"
    provider: str = "auto"
    output_dir: Path | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    proxy: str | None = None
    credential_ref: str | None = None
    filename_template: str | None = None
    overwrite: bool = False
    timeout_seconds: float | None = Field(default=None, gt=0)
    retries: int = Field(default=3, ge=0)
    direct_options: dict[str, Any] = Field(default_factory=dict)
    yt_dlp_options: dict[str, Any] = Field(default_factory=dict)
    gallery_dl_options: dict[str, Any] = Field(default_factory=dict)
    provider_options: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, value: str) -> str:
        normalized = _provider_name(value)
        if not normalized:
            raise ValueError("provider cannot be empty")
        return normalized

    @field_validator("provider_options")
    @classmethod
    def _normalize_provider_options(
        cls,
        value: dict[str, dict[str, JsonValue]],
    ) -> dict[str, dict[str, JsonValue]]:
        normalized: dict[str, dict[str, JsonValue]] = {}
        for name, options in value.items():
            key = _provider_name(name)
            if not key:
                raise ValueError("provider option names cannot be empty")
            if key in normalized:
                raise ValueError(f"duplicate provider options after normalization: {key}")
            normalized[key] = dict(options)
        return normalized

    @field_validator("proxy")
    @classmethod
    def _validate_proxy(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("proxy must be an absolute HTTP(S) URL")
        return value

    def options_for(self, provider: str) -> dict[str, Any]:
        """Return merged native options for one normalized provider name.

        The namespaced ``provider_options`` mapping is the portable extension
        surface for custom providers. The three legacy built-in mappings remain
        supported and take precedence when both forms are present.
        """
        name = _provider_name(provider)
        options: dict[str, Any] = dict(self.provider_options.get(name, {}))
        legacy = {
            "direct": self.direct_options,
            "yt_dlp": self.yt_dlp_options,
            "gallery_dl": self.gallery_dl_options,
        }.get(name)
        if legacy:
            options.update(legacy)
        return options


class AcquisitionCredentials(BaseModel):
    """Resolved credentials passed separately from serializable requests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    username: str | None = None
    password: SecretStr | None = None
    cookie_file: Path | None = None
    provider_data: dict[str, Any] = Field(default_factory=dict)


class ProviderCapabilities(BaseModel):
    """Discoverable acquisition-provider capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    available: bool
    operations: frozenset[AcquisitionOperation]
    priority: int = 0
    url_patterns: tuple[str, ...] = ()
    install_extra: str | None = None
    unavailable_reason: str | None = None
    option_schema: dict[str, Any] = Field(default_factory=dict)
    supports_progress: bool = False

    @field_serializer("operations")
    def _serialize_operations(
        self,
        value: frozenset[AcquisitionOperation],
    ) -> list[AcquisitionOperation]:
        """Keep discovery manifests stable across Python hash seeds."""
        return sorted(value)


class AcquisitionProvenance(BaseModel):
    """Record which provider and extractor handled an acquisition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    extractor: str | None = None
    selected_automatically: bool = False


class AcquisitionResult(BaseModel):
    """Normalized result from metadata or download acquisition."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    source_url: str
    operation: AcquisitionOperation
    provider: str
    media: tuple[MediaInfo, ...] = ()
    downloads: tuple[DownloadResult, ...] = ()
    provenance: AcquisitionProvenance

    @computed_field
    @property
    def item_count(self) -> int:
        """Return the number of metadata or downloaded items."""
        return len(self.downloads) if self.operation == "download" else len(self.media)


class AcquisitionEvent(BaseModel):
    """One event in an acquisition operation's async event stream."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    kind: AcquisitionEventKind
    source_url: str
    provider: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    progress: DownloadProgress | None = None
    media: MediaInfo | None = None
    download: DownloadResult | None = None
    result: AcquisitionResult | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AcquisitionCredentials",
    "AcquisitionEvent",
    "AcquisitionEventKind",
    "AcquisitionOperation",
    "AcquisitionProvenance",
    "AcquisitionRequest",
    "AcquisitionResult",
    "ProviderCapabilities",
]
