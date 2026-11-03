"""Interoperability tests for the public URL value object."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urldefrag, urlparse, urlsplit
from urllib.request import Request

import httpx
import pytest
from pydantic import AnyHttpUrl, AnyUrl, HttpUrl, ValidationError

from pyfetcher import (
    URL,
    DomainParts,
    URLAdapter,
    URLAdapterRegistry,
    URLRule,
    apply_url_rules,
)


@dataclass(frozen=True)
class BespokeURL:
    """Application-owned URL value requiring an explicit adapter."""

    location: str


class TextURL:
    """Small stand-in for URL libraries exposing ``to_text``."""

    def to_text(self) -> str:
        return "https://example.com/from-text"


class UnsplitURL:
    """Small stand-in for RFC 3986 libraries exposing ``unsplit``."""

    def unsplit(self) -> str:
        return "https://example.com/from-unsplit"


class URLContainer:
    """Small stand-in for Requests/Scrapy request and response objects."""

    def __init__(self, url: object) -> None:
        self.url = url


class FinalURLContainer:
    """Small stand-in for fetchkit-style responses."""

    def __init__(self, final_url: object) -> None:
        self.final_url = final_url


def test_from_value_accepts_text_bytes_protocols_and_relative_values() -> None:
    base = URL("https://example.com/gallery/page/2")

    assert URL.from_value(b"https://example.com/bytes").path == "/bytes"
    assert URL.from_value(bytearray(b"https://example.com/bytearray")).path == "/bytearray"
    assert URL.from_value(memoryview(b"https://example.com/view")).path == "/view"
    assert URL.from_value(TextURL()).path == "/from-text"
    assert URL.from_value(UnsplitURL()).path == "/from-unsplit"
    assert URL.from_value("../image.webp", base=base) == URL(
        "https://example.com/gallery/image.webp"
    )
    assert base.join(URLContainer("../next")) == URL("https://example.com/gallery/next")


@pytest.mark.parametrize(
    "value",
    [
        urlparse("https://example.com/parsed;v=1?q=2#part"),
        urlsplit("https://example.com/split?q=2#part"),
        urldefrag("https://example.com/defrag#part"),
        urlparse(b"https://example.com/parsed-bytes?q=2"),
        urlsplit(b"https://example.com/split-bytes?q=2"),
        urldefrag(b"https://example.com/defrag-bytes#part"),
    ],
)
def test_urllib_parse_results_round_trip(value: object) -> None:
    url = URL.from_urllib(value)  # type: ignore[arg-type]

    assert url.scheme == "https"
    assert URL.from_urllib(url.to_urllib()) == url


def test_urllib_request_and_request_response_attributes_are_supported() -> None:
    request = Request("https://example.com/urllib-request")
    httpx_request = httpx.Request("GET", "https://example.com/httpx-request")

    assert URL.from_request(request).path == "/urllib-request"
    assert URL.from_request(httpx_request).path == "/httpx-request"
    assert URL(URLContainer("https://example.com/scrapy-style")).path == "/scrapy-style"
    assert URL.from_request(FinalURLContainer("https://example.com/final")).path == "/final"


def test_pydantic_adapters_keep_http_scheme_validation() -> None:
    pydantic_url = AnyHttpUrl("https://example.com/pydantic")
    url = URL.from_pydantic(pydantic_url)

    assert url.path == "/pydantic"
    assert isinstance(url.to_pydantic(), HttpUrl)
    assert isinstance(url.to_pydantic(AnyHttpUrl), AnyHttpUrl)
    assert isinstance(url.to_pydantic(AnyUrl), AnyUrl)

    with pytest.raises(ValidationError, match="URL scheme"):
        URL.from_pydantic(AnyUrl("ftp://example.com/archive"))


def test_httpx_and_yarl_round_trip() -> None:
    httpx_url = httpx.URL("https://example.com/httpx?q=1")
    assert URL.from_httpx(httpx_url).to_httpx() == httpx_url

    yarl = pytest.importorskip("yarl")
    yarl_url = yarl.URL("https://example.com/yarl?q=1")
    assert URL.from_yarl(yarl_url).to_yarl() == yarl_url


def test_domain_parts_can_reassemble_a_host_and_url() -> None:
    tldextract = pytest.importorskip("tldextract")
    source = URL("https://images.cdn.example.co.uk/gallery")
    parts = source.domain_parts()

    assert parts == DomainParts(subdomain="images.cdn", domain="example", suffix="co.uk")
    assert parts.registered_domain == "example.co.uk"
    assert parts.host == "images.cdn.example.co.uk"
    assert URL.from_domain_parts(parts, port=8443, path="items").unicode_string() == (
        "https://images.cdn.example.co.uk:8443/items"
    )
    extracted = tldextract.extract("assets.example.org")
    assert DomainParts.from_tldextract(extracted).host == "assets.example.org"
    assert URL.from_tldextract(extracted, path="images/1.webp") == URL(
        "https://assets.example.org/images/1.webp"
    )


def test_explicit_adapters_reject_wrong_input_shapes() -> None:
    with pytest.raises(TypeError, match="cannot adapt object"):
        URL.from_value(object())
    with pytest.raises(TypeError, match="urllib.parse result"):
        URL.from_urllib("https://example.com")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="httpx.URL"):
        URL.from_httpx("https://example.com")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must expose"):
        URL.from_request(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Pydantic AnyUrl subclass"):
        URL("https://example.com").to_pydantic(str)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="contain a host"):
        URL.from_domain_parts(DomainParts())


def test_bespoke_url_adapter_registry_is_ordered_and_explicit() -> None:
    registry = URLAdapterRegistry()
    adapter = registry.register_type(BespokeURL, lambda value: value.location, name="bespoke")

    assert adapter.name == "bespoke"
    assert URL.from_value(
        BespokeURL("items/3"),
        base="https://api.example.com/v1/",
        adapters=registry,
    ) == URL("https://api.example.com/v1/items/3")
    assert registry.copy().adapters == (adapter,)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(adapter)
    with pytest.raises(TypeError, match="returned its input unchanged"):
        URL.from_value(
            BespokeURL("https://example.com"),
            adapters=URLAdapterRegistry(
                [
                    URLAdapter(
                        "broken", lambda value: isinstance(value, BespokeURL), lambda value: value
                    )
                ]
            ),
        )


def test_url_rules_mix_declarative_selection_and_custom_functions() -> None:
    def remove_tracking(url: URL) -> URL:
        return url.without_query("utm_source")

    images = URLRule(
        "large-images",
        schemes=("HTTPS",),
        hosts=("example.com",),
        path_pattern=r"^/images/",
        predicate=lambda url: url.query_params.get("size") != ["large"],
        transform=lambda url: url.add_query(size="large"),
    )
    unrelated = URLRule(
        "other-site",
        hosts=("other.example",),
        transform=lambda url: url.with_path("wrong"),
    )

    result = apply_url_rules(
        "https://cdn.example.com/images/1.webp?utm_source=test",
        (remove_tracking, unrelated, images),
    )

    assert result == URL("https://cdn.example.com/images/1.webp?size=large")
