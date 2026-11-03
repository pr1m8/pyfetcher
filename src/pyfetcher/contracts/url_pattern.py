"""Typed URL matching and explicit URL-template rendering.

Patterns match normalized URL components and validate named captures with a
Pydantic model. Templates are explicit because arbitrary regular expressions
cannot be reversed safely.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from re import Pattern
from string import Formatter
from urllib.parse import parse_qs

from pydantic import BaseModel, ValidationError

from pyfetcher.contracts.url import URL


class URLPatternError(ValueError):
    """Base error for typed URL matching and rendering."""


class URLBuildError(URLPatternError):
    """Raised when parameters cannot produce a URL accepted by a pattern."""


@dataclass(frozen=True, slots=True)
class URLMatch[ParamsT: BaseModel]:
    """One URL match and its validated named parameters."""

    name: str
    url: URL
    params: ParamsT


class URLTemplate[ParamsT: BaseModel]:
    """Render validated parameters through an explicit URL format string."""

    def __init__(self, template: str, params_model: type[ParamsT]) -> None:
        if not template.strip():
            raise ValueError("URL template cannot be empty")
        self.template = template
        self.params_model = params_model
        self.fields = tuple(
            field_name
            for _, field_name, _, _ in Formatter().parse(template)
            if field_name is not None
        )

    def build(self, params: ParamsT | Mapping[str, object]) -> URL:
        """Validate parameters and render a URL."""
        value = (
            params
            if isinstance(params, self.params_model)
            else self.params_model.model_validate(params)
        )
        values = value.model_dump(mode="python")
        missing = sorted(set(self.fields) - values.keys())
        if missing:
            raise URLBuildError(f"URL template parameters are missing: {', '.join(missing)}")
        try:
            return URL(self.template.format_map(values))
        except (KeyError, ValueError) as exc:
            raise URLBuildError(f"cannot render URL template: {exc}") from exc


class URLPattern[ParamsT: BaseModel]:
    """Match URL components, validate captures, and optionally render them back."""

    def __init__(
        self,
        name: str,
        *,
        params_model: type[ParamsT],
        path: str | Pattern[str],
        schemes: tuple[str, ...] = ("http", "https"),
        hosts: tuple[str, ...] = (),
        host: str | Pattern[str] | None = None,
        query: Mapping[str, str | Pattern[str]] | None = None,
        template: str | URLTemplate[ParamsT] | None = None,
        round_trip: bool = True,
    ) -> None:
        if not name.strip():
            raise ValueError("URL pattern name cannot be empty")
        if hosts and host is not None:
            raise ValueError("use exact hosts or a host regex, not both")
        self.name = name
        self.params_model = params_model
        self.schemes = frozenset(value.lower() for value in schemes)
        self.hosts = frozenset(value.lower().rstrip(".") for value in hosts)
        self.path_pattern = re.compile(path) if isinstance(path, str) else path
        self.host_pattern = re.compile(host, re.IGNORECASE) if isinstance(host, str) else host
        self.query_patterns = {
            key: re.compile(value) if isinstance(value, str) else value
            for key, value in (query or {}).items()
        }
        self.template = (
            URLTemplate(template, params_model) if isinstance(template, str) else template
        )
        self.round_trip = round_trip

    def match(self, value: str | URL | object) -> URLMatch[ParamsT] | None:
        """Return a validated match or ``None`` when any constraint fails."""
        try:
            url = value if isinstance(value, URL) else URL(value)
        except (TypeError, ValueError):
            return None
        if self.schemes and url.scheme.lower() not in self.schemes:
            return None
        host = (url.host or "").lower().rstrip(".")
        if self.hosts and host not in self.hosts:
            return None
        captures: dict[str, object] = {}
        if self.host_pattern is not None:
            host_match = self.host_pattern.fullmatch(host)
            if host_match is None:
                return None
            captures.update(host_match.groupdict())
        path_match = self.path_pattern.fullmatch(url.split().path)
        if path_match is None:
            return None
        captures.update(path_match.groupdict())
        query_values = parse_qs(url.query or "", keep_blank_values=True)
        for name, pattern in self.query_patterns.items():
            values = query_values.get(name)
            if not values:
                return None
            match = pattern.fullmatch(values[-1])
            if match is None:
                return None
            groups = match.groupdict()
            if groups:
                captures.update(groups)
            else:
                captures.setdefault(name, values[-1])
        for field_name in self.params_model.model_fields:
            if field_name not in captures and field_name in query_values:
                captures[field_name] = query_values[field_name][-1]
        try:
            params = self.params_model.model_validate(captures)
        except ValidationError:
            return None
        return URLMatch(name=self.name, url=url, params=params)

    def parse(self, value: str | URL | object) -> ParamsT:
        """Return validated parameters or raise an actionable pattern error."""
        match = self.match(value)
        if match is None:
            raise URLPatternError(f"URL does not match pattern {self.name!r}: {value}")
        return match.params

    def build(self, params: ParamsT | Mapping[str, object]) -> URL:
        """Render a configured template and optionally enforce round-trip matching."""
        if self.template is None:
            raise URLBuildError(f"URL pattern {self.name!r} has no template")
        url = self.template.build(params)
        if self.round_trip and self.match(url) is None:
            raise URLBuildError(
                f"URL rendered by pattern {self.name!r} does not match its constraints"
            )
        return url


__all__ = [
    "URLBuildError",
    "URLMatch",
    "URLPattern",
    "URLPatternError",
    "URLTemplate",
]
