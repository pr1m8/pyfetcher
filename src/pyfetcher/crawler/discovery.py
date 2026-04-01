"""URL discovery (sitemaps + seeds) for :mod:`pyfetcher.crawler`.

Purpose:
    Discover URLs from sitemaps, robots.txt sitemap directives,
    and seed URL lists for populating the crawl frontier.
"""

from __future__ import annotations

from pyfetcher.scrape.robots import parse_robots_txt
from pyfetcher.scrape.sitemap import parse_sitemap


def discover_sitemaps_from_robots(robots_txt: str) -> list[str]:
    """Extract sitemap URLs from robots.txt content.

    Args:
        robots_txt: Raw robots.txt content.

    Returns:
        A list of sitemap URLs.
    """
    rules = parse_robots_txt(robots_txt)
    return list(rules.sitemaps)


def discover_urls_from_sitemap(sitemap_xml: str) -> list[str]:
    """Extract URLs from a sitemap XML document.

    Handles both URL sitemaps and sitemap index files.
    For index files, returns the child sitemap URLs (not final page URLs).

    Args:
        sitemap_xml: Raw sitemap XML content.

    Returns:
        A list of discovered URLs.
    """
    entries = parse_sitemap(sitemap_xml)
    return [e.loc for e in entries]


def build_seed_urls(
    *,
    urls: list[str] | None = None,
    robots_txt: str | None = None,
    sitemap_xml: str | None = None,
) -> list[str]:
    """Build a combined list of seed URLs from multiple sources.

    Args:
        urls: Explicit seed URLs.
        robots_txt: robots.txt content (extracts sitemap URLs).
        sitemap_xml: Sitemap XML content (extracts page URLs).

    Returns:
        A deduplicated list of seed URLs.
    """
    result: list[str] = []
    seen: set[str] = set()

    for url in urls or []:
        if url not in seen:
            result.append(url)
            seen.add(url)

    if robots_txt:
        for url in discover_sitemaps_from_robots(robots_txt):
            if url not in seen:
                result.append(url)
                seen.add(url)

    if sitemap_xml:
        for url in discover_urls_from_sitemap(sitemap_xml):
            if url not in seen:
                result.append(url)
                seen.add(url)

    return result
