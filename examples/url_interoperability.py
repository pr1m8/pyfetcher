"""Example: normalize and convert URL values without network access.

Run with:
    python examples/url_interoperability.py
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.request import Request

import httpx
from pydantic import AnyHttpUrl

from pyfetcher import URL, URLAdapterRegistry, URLRule, apply_url_rules


@dataclass(frozen=True)
class AssetLocation:
    """Example application-specific URL representation."""

    value: str


def main() -> None:
    """Show the core, structural, and optional URL adapters."""
    sources = [
        URL.from_urllib(urlsplit("https://example.com/gallery/1")),
        URL.from_pydantic(AnyHttpUrl("https://example.com/gallery/2")),
        URL.from_httpx(httpx.URL("https://example.com/gallery/3")),
        URL.from_request(Request("https://example.com/gallery/4")),
    ]
    base = URL("https://example.com/gallery/4/page/2")
    sources.append(URL.from_value("../cover.webp", base=base))

    adapters = URLAdapterRegistry()
    adapters.register_type(AssetLocation, lambda value: value.value)
    sources.append(
        URL.from_value(
            AssetLocation("images/5.webp"),
            base="https://cdn.example.com/",
            adapters=adapters,
        )
    )

    for url in sources:
        print(url, url.to_urllib().hostname, type(url.to_pydantic()).__name__)

    normalized = apply_url_rules(
        "https://img.example.com/images/1.jpg?utm_source=example",
        (
            lambda url: url.without_query("utm_source"),
            URLRule(
                "large-image",
                hosts=("example.com",),
                path_pattern=r"^/images/",
                transform=lambda url: url.add_query(size="large"),
            ),
        ),
    )
    print("rule result:", normalized)

    try:
        import tldextract
        import yarl
    except ImportError:
        print("Install fetchkit[url-tools] for yarl, w3lib, and tldextract helpers.")
        return

    yarl_value = yarl.URL("https://images.cdn.example.co.uk/a?b=2&a=1")
    url = URL.from_yarl(yarl_value)
    parts = url.domain_parts()
    rebuilt = URL.from_tldextract(tldextract.extract(parts.host), path="media/1.webp")
    print(url.canonicalize(), parts.registered_domain, rebuilt)


if __name__ == "__main__":
    main()
