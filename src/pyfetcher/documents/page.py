"""Runtime page-document adapter with lazy Parsel selectors.

``PageDocument`` represents one fetched document. It deliberately stays
separate from serializable resource models, database rows, job definitions,
and user-defined extracted item models.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol

from pyfetcher.contracts import URL

if TYPE_CHECKING:
    from pyfetcher.documents.selectors import Selection


class PageRule[ResultT](Protocol):
    """Rule that can extract a typed value from a page document."""

    def apply(self, root: PageDocument) -> ResultT: ...


_CHARSET_RE = re.compile(r"charset\s*=\s*['\"]?([^\s;'\"]+)", re.IGNORECASE)


def _require_parsel() -> Any:
    try:
        import parsel
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "page CSS/XPath selectors require `pip install 'fetchkit[selectors]'`"
        ) from exc
    return parsel


def _headers(value: object) -> dict[str, str]:
    to_unicode_dict = getattr(value, "to_unicode_dict", None)
    if callable(to_unicode_dict):
        return dict(to_unicode_dict())
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        name = key.decode(errors="replace") if isinstance(key, bytes) else str(key)
        if isinstance(item, (list, tuple)):
            item = ", ".join(
                part.decode(errors="replace") if isinstance(part, bytes) else str(part)
                for part in item
            )
        normalized[name] = item.decode(errors="replace") if isinstance(item, bytes) else str(item)
    return normalized


def _content_type(headers: Mapping[str, str]) -> str | None:
    return next(
        (value for key, value in headers.items() if key.lower() == "content-type"),
        None,
    )


class PageDocument:
    """Fetched HTML/XML plus a cached selector tree and URL context."""

    def __init__(
        self,
        content: str | bytes | bytearray | memoryview,
        *,
        url: str | URL | None = None,
        status_code: int | None = None,
        headers: Mapping[str, str] | None = None,
        encoding: str | None = None,
        document_type: str = "html",
        selector: object | None = None,
    ) -> None:
        if document_type not in {"html", "xml"}:
            raise ValueError("document_type must be 'html' or 'xml'")
        self.url = URL(url) if url is not None else None
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.media_type = _content_type(self.headers)
        content_encoding = None
        if self.media_type:
            match = _CHARSET_RE.search(self.media_type)
            content_encoding = match.group(1) if match else None
        self.encoding = encoding or content_encoding or "utf-8"
        if isinstance(content, str):
            self._text = content
            self.body = content.encode(self.encoding)
        else:
            self.body = bytes(content)
            self._text = None
        self.document_type = document_type
        self._selector = selector
        self._base_url: URL | None | object = _UNSET

    @classmethod
    def from_response(cls, response: object) -> PageDocument:
        """Adapt a buffered fetchkit, Scrapy, or compatible response."""
        headers = _headers(getattr(response, "headers", {}))
        body = getattr(response, "body", None)
        text = getattr(response, "text", None)
        if not isinstance(body, (bytes, bytearray, memoryview)):
            if not isinstance(text, str):
                raise TypeError("page response requires a buffered body or decoded text")
            content: str | bytes = text
        else:
            content = bytes(body)
        url = getattr(response, "final_url", None) or getattr(response, "url", None)
        status = getattr(response, "status_code", None)
        if status is None:
            status = getattr(response, "status", None)
        media_type = _content_type(headers) or str(getattr(response, "content_type", "") or "")
        document_type = "xml" if "xml" in media_type.lower() else "html"
        native_selector = getattr(response, "selector", None)
        if native_selector is not None and not all(
            hasattr(native_selector, method) for method in ("css", "xpath")
        ):
            native_selector = None
        return cls(
            content,
            url=str(url) if url is not None else None,
            status_code=int(status) if status is not None else None,
            headers=headers,
            encoding=getattr(response, "encoding", None),
            document_type=document_type,
            selector=native_selector,
        )

    @classmethod
    def from_stream(
        cls,
        source: object,
        *,
        url: str | URL | None = None,
        media_type: str | None = None,
        encoding: str | None = None,
        max_bytes: int | None = None,
    ) -> PageDocument:
        """Buffer a synchronous common byte source into a page document."""
        from pyfetcher.streams import adapt_byte_stream

        stream = adapt_byte_stream(source, media_type=media_type)
        resolved_type = media_type or stream.info.media_type
        return cls(
            stream.read(max_bytes=max_bytes),
            url=url,
            headers={"content-type": resolved_type} if resolved_type else None,
            encoding=encoding,
            document_type=("xml" if resolved_type and "xml" in resolved_type.lower() else "html"),
        )

    @classmethod
    async def afrom_stream(
        cls,
        source: object,
        *,
        url: str | URL | None = None,
        media_type: str | None = None,
        encoding: str | None = None,
        max_bytes: int | None = None,
    ) -> PageDocument:
        """Buffer a synchronous or asynchronous common byte source into a document."""
        from pyfetcher.streams import adapt_byte_stream

        stream = adapt_byte_stream(source, media_type=media_type)
        resolved_type = media_type or stream.info.media_type
        return cls(
            await stream.aread(max_bytes=max_bytes),
            url=url,
            headers={"content-type": resolved_type} if resolved_type else None,
            encoding=encoding,
            document_type=("xml" if resolved_type and "xml" in resolved_type.lower() else "html"),
        )

    @property
    def text(self) -> str:
        """Return decoded document text, caching the result."""
        if self._text is None:
            self._text = self.body.decode(self.encoding, errors="replace")
        return self._text

    @property
    def selector(self) -> object:
        """Return the cached Parsel or Scrapy selector tree."""
        if self._selector is None:
            parsel = _require_parsel()
            self._selector = parsel.Selector(
                body=self.body,
                encoding=self.encoding,
                type=self.document_type,
                base_url=str(self.url) if self.url is not None else None,
            )
        return self._selector

    @property
    def base_url(self) -> URL | None:
        """Return the first HTML base URL, falling back to the response URL."""
        if self._base_url is _UNSET:
            raw = self.selector.css("base[href]::attr(href)").get()  # type: ignore[union-attr]
            if raw:
                try:
                    self._base_url = self.url.join(raw) if self.url else URL(raw)
                except (TypeError, ValueError):
                    self._base_url = self.url
            else:
                self._base_url = self.url
        return self._base_url if isinstance(self._base_url, URL) else None

    def css(self, query: str) -> Selection:
        """Select nodes with CSS and return a chainable ``Selection``."""
        from pyfetcher.documents.selectors import Selection

        return Selection(self.selector.css(query), self)  # type: ignore[union-attr]

    def xpath(
        self,
        query: str,
        namespaces: Mapping[str, str] | None = None,
        **variables: object,
    ) -> Selection:
        """Select nodes with XPath and return a chainable ``Selection``."""
        from pyfetcher.documents.selectors import Selection

        selected = self.selector.xpath(  # type: ignore[union-attr]
            query,
            namespaces=namespaces,
            **variables,
        )
        return Selection(selected, self)

    def resolve_url(self, value: str | URL | object) -> URL:
        """Resolve a URL-like value against the document URL."""
        if self.base_url is not None:
            return self.base_url.join(value)
        try:
            return value if isinstance(value, URL) else URL(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("relative URL extraction requires a document URL") from exc

    def select[ResultT](self, rule: PageRule[ResultT]) -> ResultT:
        """Apply a typed rule without coupling the document to its model."""
        return rule.apply(self)


_UNSET = object()

__all__ = ["PageDocument", "PageRule"]
