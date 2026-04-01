"""Link extraction for :mod:`pyfetcher`.

Purpose:
    Harvest and normalize links from HTML documents, supporting filtering
    by domain, scheme, and link attributes.

Examples:
    ::

        >>> html = '<a href="https://example.com">Example</a>'
        >>> links = extract_links(html, base_url="https://example.com")
        >>> links[0].url
        'https://example.com'
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True, slots=True)
class LinkInfo:
    """Extracted link information.

    Args:
        url: The resolved absolute URL.
        text: The link's visible text content.
        rel: The ``rel`` attribute value, if present.
        is_external: Whether the link points to a different domain.

    Examples:
        ::

            >>> link = LinkInfo(
            ...     url="https://example.com", text="Example",
            ...     rel=None, is_external=False,
            ... )
            >>> link.url
            'https://example.com'
    """

    url: str
    text: str
    rel: str | None
    is_external: bool


def extract_links(
    html: str,
    *,
    base_url: str | None = None,
    same_domain_only: bool = False,
    include_fragments: bool = False,
) -> list[LinkInfo]:
    """Extract and normalize links from HTML.

    Parses all ``<a>`` tags with ``href`` attributes and resolves relative
    URLs against ``base_url``. Optionally filters to same-domain links
    only and controls whether fragment-only links are included.

    Args:
        html: Raw HTML string to parse.
        base_url: Base URL for resolving relative hrefs. Required for
            accurate ``is_external`` detection and relative URL resolution.
        same_domain_only: If ``True``, only return links pointing to the
            same domain as ``base_url``.
        include_fragments: If ``True``, include fragment-only links
            (e.g. ``#section``). Defaults to ``False``.

    Returns:
        A list of :class:`LinkInfo` objects for each extracted link.

    Examples:
        ::

            >>> html = '<a href="/about">About</a><a href="https://other.com">Other</a>'
            >>> links = extract_links(html, base_url="https://example.com")
            >>> len(links)
            2
            >>> links = extract_links(html, base_url="https://example.com", same_domain_only=True)
            >>> len(links)
            1
    """
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc if base_url else ""
    results: list[LinkInfo] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()

        if not href or href.startswith(("javascript:", "mailto:", "tel:")):
            continue

        if href.startswith("#") and not include_fragments:
            continue

        resolved = urljoin(base_url or "", href)
        parsed = urlparse(resolved)

        if parsed.scheme not in ("http", "https"):
            continue

        link_domain = parsed.netloc
        is_external = link_domain != base_domain if base_domain else True

        if same_domain_only and is_external:
            continue

        rel_values = anchor.get("rel", [])
        rel_text = " ".join(rel_values) if isinstance(rel_values, list) else str(rel_values)

        results.append(
            LinkInfo(
                url=resolved,
                text=anchor.get_text(strip=True),
                rel=rel_text or None,
                is_external=is_external,
            )
        )

    return results
