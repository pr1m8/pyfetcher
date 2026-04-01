"""Metadata extraction examples for pyfetcher.

Demonstrates HTML metadata, Open Graph, and structured data extraction.
"""

from __future__ import annotations

from pyfetcher.metadata.html import extract_basic_html_metadata
from pyfetcher.metadata.opengraph import extract_open_graph_metadata

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>My Blog Post - Example Site</title>
    <meta name="description" content="A detailed guide to web scraping with Python." />
    <link rel="canonical" href="https://example.com/blog/web-scraping" />
    <link rel="icon" href="/favicon.ico" type="image/x-icon" />
    <link rel="apple-touch-icon" href="/apple-icon.png" sizes="180x180" />

    <meta property="og:title" content="Web Scraping with Python" />
    <meta property="og:description" content="Learn how to scrape the web effectively." />
    <meta property="og:image" content="https://example.com/images/scraping-og.png" />
    <meta property="og:url" content="https://example.com/blog/web-scraping" />
    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="Example Site" />
</head>
<body>
    <h1>Web Scraping with Python</h1>
    <p>Content here...</p>
</body>
</html>
"""


def basic_html_metadata() -> None:
    """Extract basic HTML metadata (title, description, canonical, favicons)."""
    print("=== Basic HTML Metadata ===")
    meta = extract_basic_html_metadata(SAMPLE_HTML, base_url="https://example.com")
    print(f"  Title: {meta.title}")
    print(f"  Description: {meta.description}")
    print(f"  Canonical URL: {meta.canonical_url}")
    print(f"  Favicons ({len(meta.favicons)}):")
    for fav in meta.favicons:
        print(f"    {fav.rel}: {fav.href} (sizes={fav.sizes}, type={fav.mime_type})")


def open_graph_metadata() -> None:
    """Extract Open Graph metadata."""
    print("\n=== Open Graph Metadata ===")
    og = extract_open_graph_metadata(SAMPLE_HTML)
    if og:
        print(f"  Title: {og.title}")
        print(f"  Description: {og.description}")
        print(f"  Image: {og.image}")
        print(f"  URL: {og.url}")
        print(f"  Type: {og.type}")
        print(f"  Site Name: {og.site_name}")
    else:
        print("  No Open Graph metadata found.")


def no_og_example() -> None:
    """Show behavior when no OG tags exist."""
    print("\n=== No OG Tags ===")
    html = "<html><head><title>Simple Page</title></head></html>"
    og = extract_open_graph_metadata(html)
    print(f"  Result: {og}")  # None


def combined_metadata() -> None:
    """Show all metadata fields from PageMetadata model."""
    print("\n=== Combined PageMetadata ===")
    meta = extract_basic_html_metadata(SAMPLE_HTML, base_url="https://example.com")
    og = extract_open_graph_metadata(SAMPLE_HTML)
    combined = meta.model_copy(update={"open_graph": og})
    print(f"  Title: {combined.title}")
    print(f"  OG Title: {combined.open_graph.title if combined.open_graph else 'N/A'}")
    print(f"  OG Image: {combined.open_graph.image if combined.open_graph else 'N/A'}")
    print(f"  Favicons: {len(combined.favicons)}")


if __name__ == "__main__":
    basic_html_metadata()
    open_graph_metadata()
    no_og_example()
    combined_metadata()
