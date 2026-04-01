"""Sitemap parser for :mod:`pyfetcher`.

Purpose:
    Parse XML sitemaps (both sitemap index files and URL set files) and
    extract URL entries with their metadata.

Examples:
    ::

        >>> xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>'
        >>> entries = parse_sitemap(xml)
        >>> entries[0].loc
        'https://example.com/'
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree  # nosec B405

from defusedxml.ElementTree import fromstring as _safe_fromstring

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


@dataclass(frozen=True, slots=True)
class SitemapEntry:
    """A single URL entry from a sitemap.

    Args:
        loc: The URL location.
        lastmod: The last modification date string, if present.
        changefreq: The change frequency hint, if present.
        priority: The priority value as a string, if present.
        is_sitemap: Whether this entry is a sitemap index reference.

    Examples:
        ::

            >>> entry = SitemapEntry(loc="https://example.com/")
            >>> entry.loc
            'https://example.com/'
    """

    loc: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: str | None = None
    is_sitemap: bool = False


def parse_sitemap(xml_content: str) -> list[SitemapEntry]:
    """Parse an XML sitemap or sitemap index.

    Handles both ``<urlset>`` (URL sitemaps) and ``<sitemapindex>``
    (sitemap index files). Returns a flat list of entries with the
    ``is_sitemap`` flag set for index entries.

    Args:
        xml_content: Raw XML string content of the sitemap.

    Returns:
        A list of :class:`SitemapEntry` objects.

    Examples:
        ::

            >>> xml = (
            ...     '<?xml version="1.0"?>'
            ...     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            ...     '<url><loc>https://example.com/</loc><priority>1.0</priority></url>'
            ...     '</urlset>'
            ... )
            >>> entries = parse_sitemap(xml)
            >>> entries[0].priority
            '1.0'
    """
    root = _safe_fromstring(xml_content)
    entries: list[SitemapEntry] = []

    # Handle <urlset> (standard sitemap)
    for url_elem in root.findall(f"{{{SITEMAP_NS}}}url"):
        loc_elem = url_elem.find(f"{{{SITEMAP_NS}}}loc")
        if loc_elem is None or not loc_elem.text:
            continue
        entries.append(
            SitemapEntry(
                loc=loc_elem.text.strip(),
                lastmod=_get_text(url_elem, "lastmod"),
                changefreq=_get_text(url_elem, "changefreq"),
                priority=_get_text(url_elem, "priority"),
                is_sitemap=False,
            )
        )

    # Handle <sitemapindex> (sitemap index)
    for sitemap_elem in root.findall(f"{{{SITEMAP_NS}}}sitemap"):
        loc_elem = sitemap_elem.find(f"{{{SITEMAP_NS}}}loc")
        if loc_elem is None or not loc_elem.text:
            continue
        entries.append(
            SitemapEntry(
                loc=loc_elem.text.strip(),
                lastmod=_get_text(sitemap_elem, "lastmod"),
                is_sitemap=True,
            )
        )

    return entries


def _get_text(parent: ElementTree.Element, tag: str) -> str | None:
    """Get text content of a child element.

    Args:
        parent: The parent XML element.
        tag: The child tag name (without namespace prefix).

    Returns:
        The stripped text content, or ``None`` if the element doesn't exist.
    """
    elem = parent.find(f"{{{SITEMAP_NS}}}{tag}")
    return elem.text.strip() if elem is not None and elem.text else None
