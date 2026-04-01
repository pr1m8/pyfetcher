"""Basic HTML metadata extraction for :mod:`pyfetcher`.

Purpose:
    Provide lightweight HTML parsing for titles, descriptions, canonical links,
    and icon links using BeautifulSoup.

Design:
    - Parsing uses :mod:`bs4` for readability and robustness.
    - This module intentionally handles only the most common HTML-level fields.
    - Open Graph extraction is delegated to :mod:`pyfetcher.metadata.opengraph`.

Examples:
    ::

        >>> html = "<html><head><title>Example</title></head></html>"
        >>> extract_basic_html_metadata(html).title
        'Example'
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from pyfetcher.metadata.models import FaviconLink, PageMetadata


def extract_basic_html_metadata(html: str, *, base_url: str | None = None) -> PageMetadata:
    """Extract basic HTML page metadata.

    Parses the ``<title>``, ``<meta name="description">``,
    ``<link rel="canonical">``, and favicon ``<link>`` elements from the
    given HTML string. Relative URLs are resolved against ``base_url``
    when provided.

    Args:
        html: Raw HTML string to parse.
        base_url: Optional base URL for resolving relative link hrefs.

    Returns:
        A :class:`~pyfetcher.metadata.models.PageMetadata` populated with
        the extracted fields.

    Examples:
        ::

            >>> html = (
            ...     "<html><head><title>Example</title>"
            ...     "<meta name='description' content='Desc' />"
            ...     "<link rel='icon' href='/favicon.ico' />"
            ...     "</head></html>"
            ... )
            >>> meta = extract_basic_html_metadata(html, base_url="https://example.com")
            >>> meta.title
            'Example'
    """
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None

    description_tag = soup.find("meta", attrs={"name": "description"})
    description = (
        description_tag.get("content", "").strip()
        if description_tag and description_tag.get("content")
        else None
    )

    canonical_url: str | None = None
    for tag in soup.find_all("link"):
        rel_values = tag.get("rel", [])
        rel_text = (
            " ".join(rel_values).lower()
            if isinstance(rel_values, list)
            else str(rel_values).lower()
        )
        if "canonical" in rel_text and tag.get("href"):
            canonical_url = urljoin(base_url or "", tag["href"])
            break

    favicons: list[FaviconLink] = []
    for tag in soup.find_all("link"):
        rel_values = tag.get("rel", [])
        rel_text = (
            " ".join(rel_values).lower()
            if isinstance(rel_values, list)
            else str(rel_values).lower()
        )
        if any(token in rel_text for token in ("icon", "apple-touch-icon", "mask-icon")):
            href = tag.get("href")
            if not href:
                continue
            favicons.append(
                FaviconLink(
                    href=urljoin(base_url or "", href),
                    rel=rel_text,
                    sizes=tag.get("sizes"),
                    mime_type=tag.get("type"),
                )
            )

    return PageMetadata(
        title=title,
        description=description,
        canonical_url=canonical_url,
        favicons=favicons,
    )
