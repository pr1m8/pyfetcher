"""Validated URL value objects for :mod:`pyfetcher`.

Purpose:
    Provide a small immutable wrapper around :class:`pydantic.HttpUrl` with
    useful derived helpers for host, path, and query decomposition.

Design:
    - ``URL`` is intentionally pure and contains no I/O behavior.
    - Computed properties remain deterministic and serialization-friendly.
    - The model is frozen so it behaves like a value object.

Examples:
    ::

        >>> url = URL("https://example.com/a/b/?x=1&x=2&y=")
        >>> url.host
        'example.com'
        >>> url.path_segments
        ['a', 'b']
        >>> url.query_params["x"]
        ['1', '2']
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol, Self, TypeVar, overload
from urllib.parse import (
    DefragResult,
    DefragResultBytes,
    ParseResult,
    ParseResultBytes,
    SplitResult,
    SplitResultBytes,
    parse_qs,
    parse_qsl,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)

import httpx
from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    HttpUrl,
    RootModel,
    TypeAdapter,
    computed_field,
    field_validator,
)

if TYPE_CHECKING:
    import yarl

type QueryScalar = str | int | float | bool | None
type QueryValue = QueryScalar | Iterable[QueryScalar]
type UrllibURL = (
    ParseResult
    | ParseResultBytes
    | SplitResult
    | SplitResultBytes
    | DefragResult
    | DefragResultBytes
)

_PydanticURL = TypeVar("_PydanticURL", bound=AnyUrl)


class SupportsGetURL(Protocol):
    """Structural type for URL objects exposing ``geturl()``."""

    def geturl(self) -> str | bytes:
        """Return the serialized URL."""


class SupportsGetFullURL(Protocol):
    """Structural type for request objects exposing ``get_full_url()``."""

    def get_full_url(self) -> str | bytes:
        """Return the request URL."""


class SupportsToText(Protocol):
    """Structural type used by URL libraries such as ``hyperlink``."""

    def to_text(self) -> str:
        """Return the serialized URL."""


class SupportsURL(Protocol):
    """Structural type for requests and responses exposing ``url``."""

    @property
    def url(self) -> object:
        """Return the wrapped URL value."""


class SupportsFinalURL(Protocol):
    """Structural type for responses exposing ``final_url``."""

    @property
    def final_url(self) -> object:
        """Return the final URL value."""


class SupportsUnsplit(Protocol):
    """Structural type used by RFC 3986-style URL libraries."""

    def unsplit(self) -> str | bytes:
        """Return the serialized URL."""


class URLAdapterResolver(Protocol):
    """Structural boundary implemented by bespoke URL adapter registries."""

    def adapt(self, value: object) -> object:
        """Convert a matching bespoke value or return it unchanged."""


class SupportsDomainParts(Protocol):
    """Structural type for ``tldextract``-style domain results."""

    subdomain: str
    domain: str
    suffix: str


class DomainParts(BaseModel):
    """Public-suffix-aware domain decomposition returned by ``URL.domain_parts``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subdomain: str = ""
    domain: str = ""
    suffix: str = ""
    is_private: bool = False

    @classmethod
    def from_tldextract(cls, value: SupportsDomainParts) -> Self:
        """Adapt a ``tldextract.ExtractResult`` or compatible domain object."""
        try:
            subdomain = value.subdomain
            domain = value.domain
            suffix = value.suffix
        except AttributeError as exc:
            raise TypeError(
                "value must expose tldextract-style subdomain, domain, and suffix fields"
            ) from exc
        if not all(isinstance(part, str) for part in (subdomain, domain, suffix)):
            raise TypeError("tldextract-style domain fields must be strings")
        return cls(
            subdomain=subdomain,
            domain=domain,
            suffix=suffix,
            is_private=bool(getattr(value, "is_private", False)),
        )

    @property
    def registered_domain(self) -> str:
        """Return the registrable domain, or the bare domain when no suffix exists."""
        return ".".join(part for part in (self.domain, self.suffix) if part)

    @property
    def host(self) -> str:
        """Reassemble the complete host represented by these domain parts."""
        return ".".join(part for part in (self.subdomain, self.domain, self.suffix) if part)


@lru_cache(maxsize=1)
def _tld_extractor():
    try:
        import tldextract
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "public-suffix URL helpers require `pip install 'fetchkit[url-tools]'`"
        ) from exc
    return tldextract.TLDExtract(suffix_list_urls=())


def _decode_url_bytes(value: bytes | bytearray | memoryview) -> str:
    """Decode an ASCII-compatible serialized URL."""
    return bytes(value).decode("utf-8")


def _coerce_url_text(value: object, *, _seen: set[int] | None = None) -> str:
    """Adapt common URL, request, and response objects to serialized text."""
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _decode_url_bytes(value)
    if isinstance(value, URL):
        return value.unicode_string()
    if isinstance(value, AnyUrl):
        return str(value)

    seen = set() if _seen is None else _seen
    identity = id(value)
    if identity in seen:
        raise TypeError("cyclic URL adapter value")
    seen.add(identity)

    for name in ("get_full_url", "geturl", "to_text", "unsplit"):
        accessor = getattr(value, name, None)
        if not callable(accessor):
            continue
        try:
            candidate = accessor()
        except TypeError:
            continue
        if candidate is value:
            continue
        try:
            return _coerce_url_text(candidate, _seen=seen)
        except TypeError:
            continue

    for name in ("final_url", "url"):
        candidate = getattr(value, name, None)
        if candidate is None or candidate is value:
            continue
        try:
            return _coerce_url_text(candidate, _seen=seen)
        except TypeError:
            continue

    if hasattr(value, "__str__"):
        text = str(value)
        if text and not (text.startswith("<") and text.endswith(">")):
            return text

    raise TypeError(
        f"cannot adapt {type(value).__name__} to a URL; pass URL text or an object "
        "exposing geturl(), get_full_url(), to_text(), unsplit(), .url, or .final_url"
    )


class URL(RootModel[HttpUrl]):
    """Validated HTTP/HTTPS URL with derived helpers.

    Wraps :class:`pydantic.HttpUrl` to provide computed decomposition of
    scheme, host, port, path segments, and query parameters as a frozen
    value object suitable for embedding in request models.

    Args:
        root: The raw URL string or ``HttpUrl`` instance to validate.

    Raises:
        pydantic.ValidationError: If the value is not a valid HTTP/HTTPS URL.

    Examples:
        ::

            >>> url = URL("https://example.com:8443/a/b/?x=1&x=2")
            >>> url.host
            'example.com'
            >>> url.port
            8443
    """

    model_config = ConfigDict(frozen=True)

    @field_validator("root", mode="before")
    @classmethod
    def _adapt_url_values(cls, value: object) -> object:
        """Accept urllib, Pydantic, yarl, and other string-like URL values."""
        try:
            return _coerce_url_text(value)
        except (TypeError, UnicodeError):
            return value

    @classmethod
    def from_value(
        cls,
        value: URLInput,
        *,
        base: URLInput | None = None,
        adapters: URLAdapterResolver | None = None,
    ) -> Self:
        """Adapt a URL-like value, optionally resolving it against an absolute base.

        This is the broad interoperability entry point. It supports URL text and
        bytes, this model, Pydantic URL values, urllib parse results and requests,
        objects with ``geturl()``, ``get_full_url()``, ``to_text()``, or ``unsplit()``,
        and request/response objects exposing ``url`` or ``final_url``.
        """
        if adapters is not None:
            value = adapters.adapt(value)
        text = _coerce_url_text(value)
        if base is not None:
            if adapters is not None:
                base = adapters.adapt(base)
            base_url = cls(_coerce_url_text(base))
            text = urljoin(base_url.unicode_string(), text)
        return cls(text)

    @classmethod
    def from_pydantic(cls, value: AnyUrl) -> Self:
        """Adapt a Pydantic URL while retaining the HTTP/HTTPS invariant."""
        if not isinstance(value, AnyUrl):
            raise TypeError("value must be a pydantic AnyUrl instance")
        return cls(str(value))

    @classmethod
    def from_urllib(cls, value: UrllibURL) -> Self:
        """Adapt any string or bytes result returned by :mod:`urllib.parse`."""
        if not isinstance(
            value,
            (
                ParseResult,
                ParseResultBytes,
                SplitResult,
                SplitResultBytes,
                DefragResult,
                DefragResultBytes,
            ),
        ):
            raise TypeError("value must be a urllib.parse result")
        return cls.from_value(value)

    @classmethod
    def from_httpx(cls, value: httpx.URL) -> Self:
        """Adapt an :class:`httpx.URL`."""
        if not isinstance(value, httpx.URL):
            raise TypeError("value must be an httpx.URL instance")
        return cls(str(value))

    @classmethod
    def from_yarl(cls, value: yarl.URL) -> Self:
        """Adapt a :class:`yarl.URL` without making yarl a core dependency."""
        try:
            import yarl
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "yarl conversion requires `pip install 'fetchkit[url-tools]'`"
            ) from exc
        if not isinstance(value, yarl.URL):
            raise TypeError("value must be a yarl.URL instance")
        return cls(str(value))

    @classmethod
    def from_request(
        cls,
        value: SupportsGetFullURL | SupportsURL | SupportsFinalURL,
    ) -> Self:
        """Adapt an urllib, HTTPX, Requests, Scrapy, or fetchkit request/response."""
        for name in ("get_full_url", "final_url", "url"):
            candidate = getattr(value, name, None)
            if callable(candidate):
                candidate = candidate()
            if candidate is not None and candidate is not value:
                return cls.from_value(candidate)
        raise TypeError("request or response must expose get_full_url(), .url, or .final_url")

    @classmethod
    def from_domain_parts(
        cls,
        parts: DomainParts,
        *,
        scheme: str = "https",
        port: int | None = None,
        path: str = "/",
    ) -> Self:
        """Build a URL from public-suffix-aware domain components."""
        if not parts.host:
            raise ValueError("domain parts must contain a host")
        if not path.startswith("/"):
            path = f"/{path}"
        netloc = f"{parts.host}:{port}" if port is not None else parts.host
        return cls(urlunsplit((scheme, netloc, path, "", "")))

    @classmethod
    def from_tldextract(
        cls,
        value: SupportsDomainParts,
        *,
        scheme: str = "https",
        port: int | None = None,
        path: str = "/",
    ) -> Self:
        """Build a URL from a ``tldextract.ExtractResult`` or compatible value."""
        return cls.from_domain_parts(
            DomainParts.from_tldextract(value),
            scheme=scheme,
            port=port,
            path=path,
        )

    @computed_field
    @property
    def scheme(self) -> str:
        """Return the URL scheme (e.g. ``'https'``).

        Returns:
            The scheme component of the URL.

        Examples:
            ::

                >>> URL("https://example.com").scheme
                'https'
        """
        return self.root.scheme

    @computed_field
    @property
    def host(self) -> str | None:
        """Return the hostname.

        Returns:
            The host if present, otherwise ``None``.

        Examples:
            ::

                >>> URL("https://example.com").host
                'example.com'
        """
        return self.root.host

    @computed_field
    @property
    def port(self) -> int | None:
        """Return the explicit port number.

        Returns:
            The explicit port if present, otherwise ``None``.

        Examples:
            ::

                >>> URL("https://example.com:9443").port
                9443
        """
        return self.root.port

    @computed_field
    @property
    def path(self) -> str | None:
        """Return the path component.

        Returns:
            The path if present, otherwise ``None``.

        Examples:
            ::

                >>> URL("https://example.com/a/b").path
                '/a/b'
        """
        return self.root.path

    @computed_field
    @property
    def path_segments(self) -> list[str]:
        """Return non-empty path segments.

        Returns:
            A list of non-empty path segments split on ``/``.

        Examples:
            ::

                >>> URL("https://example.com/a/b/").path_segments
                ['a', 'b']
        """
        return [segment for segment in (self.root.path or "").split("/") if segment]

    @computed_field
    @property
    def query(self) -> str | None:
        """Return the raw query string.

        Returns:
            The raw query string if present, otherwise ``None``.

        Examples:
            ::

                >>> URL("https://example.com?a=1&b=2").query
                'a=1&b=2'
        """
        return self.root.query

    @computed_field
    @property
    def query_params(self) -> dict[str, list[str]]:
        """Return parsed query parameters.

        Returns:
            Parsed query parameters as a dict mapping keys to lists of values,
            preserving blank values.

        Examples:
            ::

                >>> URL("https://example.com?a=1&a=2&b=").query_params
                {'a': ['1', '2'], 'b': ['']}
        """
        return parse_qs(self.root.query or "", keep_blank_values=True)

    @computed_field
    @property
    def fragment(self) -> str | None:
        """Return the URL fragment without the leading hash."""
        return self.root.fragment

    @computed_field
    @property
    def origin(self) -> str:
        """Return ``scheme://host[:port]`` with no credentials, path, or query."""
        host = self.root.host or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        default_port = 443 if self.root.scheme == "https" else 80
        port = f":{self.root.port}" if self.root.port and self.root.port != default_port else ""
        return f"{self.root.scheme}://{host}{port}"

    def unicode_string(self) -> str:
        """Return the normalized URL string.

        Returns:
            The normalized URL as a Unicode string.

        Examples:
            ::

                >>> URL("https://example.com").unicode_string()
                'https://example.com/'
        """
        return str(self.root)

    def split(self) -> SplitResult:
        """Return the standard-library ``SplitResult`` adapter."""
        return urlsplit(self.unicode_string())

    def to_urllib(self) -> SplitResult:
        """Return the standard-library ``SplitResult`` representation."""
        return self.split()

    @overload
    def to_pydantic(self) -> HttpUrl: ...

    @overload
    def to_pydantic(self, url_type: type[_PydanticURL]) -> _PydanticURL: ...

    def to_pydantic(self, url_type: type[AnyUrl] = HttpUrl) -> AnyUrl:
        """Validate this URL as a selected Pydantic URL type."""
        if not isinstance(url_type, type) or not issubclass(url_type, AnyUrl):
            raise TypeError("url_type must be a Pydantic AnyUrl subclass")
        return TypeAdapter(url_type).validate_python(self.unicode_string())

    def to_httpx(self) -> httpx.URL:
        """Return the equivalent :class:`httpx.URL`."""
        return httpx.URL(self.unicode_string())

    def join(
        self,
        value: URLInput,
        *,
        adapters: URLAdapterResolver | None = None,
    ) -> URL:
        """Resolve an absolute or relative URL against this URL."""
        return URL.from_value(value, base=self, adapters=adapters)

    def with_path(self, path: str, *, keep_query: bool = True) -> URL:
        """Return a copy with a replaced absolute path."""
        if not path.startswith("/"):
            path = f"/{path}"
        parts = self.split()
        return URL(
            urlunsplit(
                (
                    parts.scheme,
                    parts.netloc,
                    path,
                    parts.query if keep_query else "",
                    parts.fragment,
                )
            )
        )

    def with_query(
        self,
        values: Mapping[str, QueryValue],
        *,
        merge: bool = False,
    ) -> URL:
        """Return a copy with encoded query values, optionally merging existing ones."""
        pairs: list[tuple[str, QueryScalar]] = (
            [(name, value) for name, value in parse_qsl(self.query or "", keep_blank_values=True)]
            if merge
            else []
        )
        replaced = set(values)
        if merge:
            pairs = [(name, value) for name, value in pairs if name not in replaced]
        for name, value in values.items():
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
                pairs.extend((name, "" if item is None else item) for item in value)
            else:
                pairs.append((name, "" if value is None else value))
        parts = self.split()
        return URL(
            urlunsplit(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    urlencode(pairs, doseq=True),
                    parts.fragment,
                )
            )
        )

    def add_query(self, **values: QueryValue) -> URL:
        """Merge keyword query values into the URL."""
        return self.with_query(values, merge=True)

    def without_query(self, *names: str) -> URL:
        """Remove named query parameters, or the complete query when none are given."""
        parts = self.split()
        query = (
            urlencode(
                [
                    (name, value)
                    for name, value in parse_qsl(parts.query, keep_blank_values=True)
                    if name not in set(names)
                ],
                doseq=True,
            )
            if names
            else ""
        )
        return URL(urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment)))

    def with_fragment(self, fragment: str | None) -> URL:
        """Return a copy with a replaced or removed fragment."""
        parts = self.split()
        return URL(
            urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, fragment or ""))
        )

    def canonicalize(self, *, keep_fragment: bool = False) -> URL:
        """Canonicalize with w3lib using the same rules commonly used by Scrapy."""
        try:
            from w3lib.url import canonicalize_url
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "URL canonicalization requires `pip install 'fetchkit[url-tools]'`"
            ) from exc
        return URL(canonicalize_url(self.unicode_string(), keep_fragments=keep_fragment))

    def domain_parts(self, *, include_private: bool = False) -> DomainParts:
        """Return public-suffix-aware domain parts without performing network updates."""
        extracted = _tld_extractor()(self.host or "", include_psl_private_domains=include_private)
        return DomainParts(
            subdomain=extracted.subdomain,
            domain=extracted.domain,
            suffix=extracted.suffix,
            is_private=bool(getattr(extracted, "is_private", False)),
        )

    def to_yarl(self) -> yarl.URL:
        """Return a ``yarl.URL`` adapter without making yarl a hard API dependency."""
        try:
            import yarl
        except ImportError as exc:  # pragma: no cover - aiohttp normally provides yarl
            raise ImportError(
                "yarl conversion requires `pip install 'fetchkit[url-tools]'`"
            ) from exc
        return yarl.URL(self.unicode_string())

    def fingerprint(self, *, canonical: bool = True) -> str:
        """Return a stable SHA-256 URL fingerprint for deduplication keys."""
        value = self.canonicalize().unicode_string() if canonical else self.unicode_string()
        return hashlib.sha256(value.encode()).hexdigest()

    def __str__(self) -> str:
        """Return the normalized URL string.

        Returns:
            The normalized URL as a Unicode string.

        Examples:
            ::

                >>> str(URL("https://example.com"))
                'https://example.com/'
        """
        return str(self.root)


if TYPE_CHECKING:
    type URLInput = (
        URL
        | str
        | bytes
        | bytearray
        | memoryview
        | AnyUrl
        | httpx.URL
        | yarl.URL
        | UrllibURL
        | SupportsGetURL
        | SupportsGetFullURL
        | SupportsToText
        | SupportsUnsplit
        | SupportsURL
        | SupportsFinalURL
    )
else:
    type URLInput = (
        URL
        | str
        | bytes
        | bytearray
        | memoryview
        | AnyUrl
        | httpx.URL
        | UrllibURL
        | SupportsGetURL
        | SupportsGetFullURL
        | SupportsToText
        | SupportsUnsplit
        | SupportsURL
        | SupportsFinalURL
    )


__all__ = [
    "DomainParts",
    "QueryScalar",
    "QueryValue",
    "SupportsFinalURL",
    "SupportsDomainParts",
    "SupportsGetFullURL",
    "SupportsGetURL",
    "SupportsToText",
    "SupportsUnsplit",
    "SupportsURL",
    "URL",
    "URLAdapterResolver",
    "URLInput",
    "UrllibURL",
]
