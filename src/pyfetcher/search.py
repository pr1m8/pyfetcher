"""Provider-neutral search contracts and registry.

Search is intentionally a capability beside fetching rather than a special
HTTP verb. Site adapters can use APIs, HTML pages, browsers, or external
indexes while callers receive the same serializable result shape.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class SearchRequest(BaseModel):
    """Serializable query for a named or automatically selected provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    provider: str = "auto"
    limit: int = Field(default=20, ge=1, le=1_000)
    cursor: str | None = None
    filters: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("query", "provider")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("search query and provider cannot be empty")
        return normalized


class SearchHit(BaseModel):
    """One provider-neutral search match."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    title: str | None = None
    summary: str | None = None
    score: float | None = None
    media_type: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """One page of ordered search matches and an optional continuation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    provider: str
    hits: tuple[SearchHit, ...] = ()
    next_cursor: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SearchProvider(Protocol):
    """Runtime adapter implemented by API-, HTML-, or browser-backed search."""

    name: str

    def score(self, request: SearchRequest) -> int | None: ...

    async def search(self, request: SearchRequest) -> SearchResult: ...


class SearchService:
    """Allowlisted registry and selector for site-specific search clients."""

    def __init__(self, providers: tuple[SearchProvider, ...] = ()) -> None:
        self._providers: dict[str, SearchProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: SearchProvider, *, replace: bool = False) -> None:
        name = provider.name.strip().lower().replace("-", "_")
        if not name:
            raise ValueError("search provider name cannot be empty")
        if name in self._providers and not replace:
            raise ValueError(f"search provider already registered: {name}")
        self._providers[name] = provider

    def providers(self) -> tuple[str, ...]:
        """Return registered provider names in stable order."""
        return tuple(sorted(self._providers))

    async def search(self, request: SearchRequest) -> SearchResult:
        """Resolve and execute one explicit or automatically routed query."""
        if request.provider != "auto":
            provider = self._providers.get(request.provider.replace("-", "_"))
            if provider is None:
                choices = ", ".join(self.providers()) or "none"
                raise KeyError(
                    f"unknown search provider {request.provider!r}; registered: {choices}"
                )
            return await provider.search(request)

        candidates = [
            (score, provider.name, provider)
            for provider in self._providers.values()
            if (score := provider.score(request)) is not None
        ]
        if not candidates:
            raise LookupError(f"no search provider accepts query {request.query!r}")
        _, _, provider = max(candidates, key=lambda value: (value[0], value[1]))
        return await provider.search(request)


__all__ = [
    "SearchHit",
    "SearchProvider",
    "SearchRequest",
    "SearchResult",
    "SearchService",
]
