"""Runtime extension points for bespoke URL values and transformations.

The core :class:`pyfetcher.URL` recognizes common structural URL shapes. This
module handles application-specific object types and reusable conditional URL
normalization without adding global mutable adapter state.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Self, cast

from pyfetcher.contracts.url import URL, URLInput

type URLAdapterPredicate = Callable[[object], bool]
type URLAdapterFunction = Callable[[object], object]
type URLPredicate = Callable[[URL], bool]
type URLTransform = Callable[[URL], object]


@dataclass(frozen=True, slots=True)
class URLAdapter:
    """One named predicate and conversion function for a bespoke URL value."""

    name: str
    predicate: URLAdapterPredicate
    convert: URLAdapterFunction

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("URL adapter name cannot be empty")

    @classmethod
    def for_type[ValueT](
        cls,
        value_type: type[ValueT],
        converter: Callable[[ValueT], object],
        *,
        name: str | None = None,
    ) -> Self:
        """Create an adapter selected by ``isinstance``."""

        def matches(value: object) -> bool:
            return isinstance(value, value_type)

        def convert(value: object) -> object:
            return converter(cast(ValueT, value))

        return cls(
            name=name or f"{value_type.__module__}.{value_type.__qualname__}",
            predicate=matches,
            convert=convert,
        )

    def matches(self, value: object) -> bool:
        """Return whether this adapter accepts a value."""
        return bool(self.predicate(value))

    def adapt(self, value: object) -> object:
        """Convert a supported value into another URL-like representation."""
        converted = self.convert(value)
        if converted is value:
            raise TypeError(f"URL adapter {self.name!r} returned its input unchanged")
        return converted


class URLAdapterRegistry:
    """Ordered, application-owned registry of bespoke URL object adapters.

    The first matching adapter wins. Registries are deliberately explicit and
    injectable, so one application or client cannot silently change URL
    semantics for unrelated callers in the same process.
    """

    def __init__(self, adapters: Iterable[URLAdapter] = ()) -> None:
        self._adapters: list[URLAdapter] = []
        for adapter in adapters:
            self.register(adapter)

    @property
    def adapters(self) -> tuple[URLAdapter, ...]:
        """Return adapters in matching order."""
        return tuple(self._adapters)

    def __iter__(self) -> Iterator[URLAdapter]:
        return iter(self._adapters)

    def __len__(self) -> int:
        return len(self._adapters)

    def register(
        self,
        adapter: URLAdapter,
        *,
        prepend: bool = False,
        replace: bool = False,
    ) -> URLAdapter:
        """Register an adapter, optionally replacing one with the same name."""
        existing = next(
            (index for index, item in enumerate(self._adapters) if item.name == adapter.name),
            None,
        )
        if existing is not None:
            if not replace:
                raise ValueError(f"URL adapter {adapter.name!r} is already registered")
            self._adapters.pop(existing)
        if prepend:
            self._adapters.insert(0, adapter)
        else:
            self._adapters.append(adapter)
        return adapter

    def register_type[ValueT](
        self,
        value_type: type[ValueT],
        converter: Callable[[ValueT], object],
        *,
        name: str | None = None,
        prepend: bool = False,
        replace: bool = False,
    ) -> URLAdapter:
        """Create and register an adapter for a concrete or base type."""
        return self.register(
            URLAdapter.for_type(value_type, converter, name=name),
            prepend=prepend,
            replace=replace,
        )

    def adapt(self, value: object) -> object:
        """Run the first matching adapter, returning unmatched values unchanged."""
        for adapter in self._adapters:
            if adapter.matches(value):
                return adapter.adapt(value)
        return value

    def copy(self) -> Self:
        """Return an independent registry with the same ordered adapters."""
        return type(self)(self._adapters)


@dataclass(frozen=True, slots=True)
class URLRule:
    """Conditional URL transformation with declarative and callable matching."""

    name: str
    transform: URLTransform
    schemes: tuple[str, ...] = ()
    hosts: tuple[str, ...] = ()
    path_pattern: str | re.Pattern[str] | None = None
    predicate: URLPredicate | None = None
    include_subdomains: bool = True
    stop: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("URL rule name cannot be empty")
        object.__setattr__(
            self,
            "schemes",
            tuple(value.strip().lower() for value in self.schemes if value.strip()),
        )
        object.__setattr__(
            self,
            "hosts",
            tuple(value.strip().lower().rstrip(".") for value in self.hosts if value.strip()),
        )
        if isinstance(self.path_pattern, str):
            re.compile(self.path_pattern)

    def matches(self, url: URL) -> bool:
        """Return whether all configured selectors accept a URL."""
        if self.schemes and url.scheme.lower() not in self.schemes:
            return False
        host = (url.host or "").lower().rstrip(".")
        if self.hosts and not any(
            host == allowed or (self.include_subdomains and host.endswith(f".{allowed}"))
            for allowed in self.hosts
        ):
            return False
        if self.path_pattern is not None and re.search(self.path_pattern, url.path or "") is None:
            return False
        return self.predicate is None or bool(self.predicate(url))

    def apply(
        self,
        url: URL,
        *,
        adapters: URLAdapterRegistry | None = None,
    ) -> URL:
        """Transform a matched URL and normalize the returned URL-like value."""
        if not self.matches(url):
            return url
        return URL.from_value(self.transform(url), base=url, adapters=adapters)


type URLRuleSpec = URLRule | URLTransform


def apply_url_rules(
    value: URLInput,
    rules: Iterable[URLRuleSpec],
    *,
    base: URLInput | None = None,
    adapters: URLAdapterRegistry | None = None,
) -> URL:
    """Apply unconditional functions and matching URL rules in order."""
    current = URL.from_value(value, base=base, adapters=adapters)
    for rule in rules:
        if isinstance(rule, URLRule):
            matched = rule.matches(current)
            if not matched:
                continue
            current = rule.apply(current, adapters=adapters)
            if rule.stop:
                break
        elif callable(rule):
            current = URL.from_value(rule(current), base=current, adapters=adapters)
        else:
            raise TypeError("URL rules must be URLRule instances or callable transforms")
    return current


__all__ = [
    "URLAdapter",
    "URLAdapterFunction",
    "URLAdapterPredicate",
    "URLAdapterRegistry",
    "URLPredicate",
    "URLRule",
    "URLRuleSpec",
    "URLTransform",
    "apply_url_rules",
]
