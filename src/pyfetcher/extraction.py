"""Lightweight custom extractor contracts and registry.

This module only standardizes runtime extraction inputs and outputs. It does
not define crawl scheduling, site objects, page types, or job orchestration.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from pyfetcher.contracts import URL
from pyfetcher.media import MediaMetadata, ainspect_media
from pyfetcher.streams import ByteStream, adapt_byte_stream

if TYPE_CHECKING:
    from pyfetcher.documents import PageDocument

type ExtractorOutput = ExtractionResult | MediaMetadata | Mapping[str, JsonValue]
type ExtractorCallable = Callable[
    [ExtractionContext],
    ExtractorOutput | Awaitable[ExtractorOutput],
]


@dataclass(frozen=True, slots=True)
class ExtractionContext:
    """Runtime-only source and hints passed to custom extractors."""

    source: ByteStream
    url: URL | None = None
    media_type: str | None = None
    filename: str | None = None
    hints: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def adapt(
        cls,
        source: object,
        *,
        url: str | URL | None = None,
        media_type: str | None = None,
        filename: str | None = None,
        hints: Mapping[str, object] | None = None,
    ) -> ExtractionContext:
        """Build context from bytes, paths, responses, iterables, or downloads."""
        stream = adapt_byte_stream(source, media_type=media_type)
        return cls(
            source=stream,
            url=URL(url) if url is not None else None,
            media_type=media_type or stream.info.media_type,
            filename=filename or stream.info.name,
            hints=dict(hints or {}),
        )

    def document(self, *, max_bytes: int | None = None) -> PageDocument:
        """Materialize a synchronous source as a typed page document."""
        from pyfetcher.documents import PageDocument

        return PageDocument.from_stream(
            self.source,
            url=self.url,
            media_type=self.media_type,
            max_bytes=max_bytes,
        )

    async def adocument(self, *, max_bytes: int | None = None) -> PageDocument:
        """Materialize a synchronous or asynchronous source as a page document."""
        from pyfetcher.documents import PageDocument

        return await PageDocument.afrom_stream(
            self.source,
            url=self.url,
            media_type=self.media_type,
            max_bytes=max_bytes,
        )


class ExtractionResult(BaseModel):
    """Serializable normalized result from any registered extractor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    extractor: str
    data: dict[str, JsonValue] = Field(default_factory=dict)
    media: tuple[MediaMetadata, ...] = ()
    warnings: tuple[str, ...] = ()


class Extractor(Protocol):
    """Minimal custom extraction adapter."""

    name: str
    priority: int

    def supports(self, context: ExtractionContext) -> bool: ...

    async def extract(self, context: ExtractionContext) -> ExtractionResult: ...


def _normalize(name: str, value: ExtractorOutput) -> ExtractionResult:
    if isinstance(value, ExtractionResult):
        if value.extractor != name:
            return value.model_copy(update={"extractor": name})
        return value
    if isinstance(value, MediaMetadata):
        return ExtractionResult(extractor=name, media=(value,))
    return ExtractionResult(extractor=name, data=dict(value))


class CallableExtractor:
    """Convenience adapter for sync or async extraction functions."""

    def __init__(
        self,
        name: str,
        function: ExtractorCallable,
        *,
        supports: Callable[[ExtractionContext], bool] | None = None,
        priority: int = 0,
    ) -> None:
        if not name.strip():
            raise ValueError("extractor name cannot be empty")
        self.name = name
        self.priority = priority
        self._function = function
        self._supports = supports or (lambda context: True)

    def supports(self, context: ExtractionContext) -> bool:
        return self._supports(context)

    async def extract(self, context: ExtractionContext) -> ExtractionResult:
        value = self._function(context)
        if inspect.isawaitable(value):
            value = await value
        return _normalize(self.name, cast(ExtractorOutput, value))


class MediaFileExtractor:
    """Built-in adapter from local/streamed media to ``MediaMetadata``."""

    name = "media.metadata"
    priority = 10

    def supports(self, context: ExtractionContext) -> bool:
        media_type = context.media_type or ""
        filename = (context.filename or "").lower()
        return media_type.startswith(("image/", "video/", "audio/")) or filename.endswith(
            (
                ".gif",
                ".webp",
                ".png",
                ".jpg",
                ".jpeg",
                ".mp4",
                ".webm",
                ".mkv",
                ".mp3",
                ".flac",
                ".wav",
            )
        )

    async def extract(self, context: ExtractionContext) -> ExtractionResult:
        metadata = await ainspect_media(
            context.source,
            mime_type=context.media_type,
            source_url=context.url.unicode_string() if context.url else None,
        )
        return ExtractionResult(extractor=self.name, media=(metadata,))


class ExtractorRegistry:
    """Allowlisted, priority-ordered registry for custom extractors."""

    def __init__(self, extractors: Iterable[Extractor] = ()) -> None:
        self._extractors: dict[str, Extractor] = {}
        for extractor in extractors:
            self.register(extractor)

    def register(self, extractor: Extractor, *, replace: bool = False) -> None:
        name = extractor.name.strip()
        if not name:
            raise ValueError("extractor name cannot be empty")
        if name in self._extractors and not replace:
            raise ValueError(f"extractor already registered: {name}")
        self._extractors[name] = extractor

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._extractors))

    def candidates(self, context: ExtractionContext) -> tuple[Extractor, ...]:
        """Return supporting extractors in stable priority order."""
        return tuple(
            sorted(
                (
                    extractor
                    for extractor in self._extractors.values()
                    if extractor.supports(context)
                ),
                key=lambda extractor: (-extractor.priority, extractor.name),
            )
        )

    async def extract(
        self,
        context: ExtractionContext,
        *,
        extractor: str = "auto",
        strict: bool = True,
    ) -> ExtractionResult:
        """Run an explicit extractor or the first successful supporting one."""
        if extractor != "auto":
            try:
                selected = self._extractors[extractor]
            except KeyError as exc:
                choices = ", ".join(self.names()) or "none"
                raise KeyError(f"unknown extractor {extractor!r}; registered: {choices}") from exc
            if not selected.supports(context):
                raise ValueError(f"extractor {extractor!r} does not support this source")
            return await selected.extract(context)

        candidates = self.candidates(context)
        if not candidates:
            raise LookupError("no registered extractor supports this source")
        if not strict and len(candidates) > 1 and not context.source.info.replayable:
            raise ValueError("non-strict extractor fallback requires a replayable byte source")
        failures: list[str] = []
        for selected in candidates:
            try:
                result = await selected.extract(context)
            except Exception as exc:
                if strict:
                    raise
                failures.append(f"{selected.name}: {exc}")
                continue
            if failures:
                result = result.model_copy(update={"warnings": (*result.warnings, *failures)})
            return result
        raise RuntimeError("all supporting extractors failed: " + "; ".join(failures))

    async def extract_all(self, context: ExtractionContext) -> tuple[ExtractionResult, ...]:
        """Run every supporting extractor; one-shot sources allow only one consumer."""
        candidates = self.candidates(context)
        if len(candidates) > 1 and not context.source.info.replayable:
            raise ValueError("extract_all requires a replayable byte source")
        return tuple([await item.extract(context) for item in candidates])


def default_extractor_registry() -> ExtractorRegistry:
    """Return a fresh registry containing dependency-light built-ins."""
    return ExtractorRegistry((MediaFileExtractor(),))


__all__ = [
    "CallableExtractor",
    "ExtractionContext",
    "ExtractionResult",
    "Extractor",
    "ExtractorRegistry",
    "MediaFileExtractor",
    "default_extractor_registry",
]
