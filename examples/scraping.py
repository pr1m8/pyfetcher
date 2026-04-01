"""Scraping examples for pyfetcher.

Demonstrates CSS selectors, link extraction, form parsing, and content extraction.
"""

from __future__ import annotations

from pyfetcher.scrape.content import extract_readable_text
from pyfetcher.scrape.forms import extract_forms
from pyfetcher.scrape.links import extract_links
from pyfetcher.scrape.robots import is_allowed, parse_robots_txt
from pyfetcher.scrape.selectors import extract_attrs, extract_table, extract_text
from pyfetcher.scrape.sitemap import parse_sitemap

SAMPLE_HTML = """
<html>
<head><title>Example Shop</title></head>
<body>
    <nav><a href="/">Home</a> | <a href="/products">Products</a></nav>
    <h1>Welcome to Example Shop</h1>
    <p>Find the best deals on electronics.</p>

    <div class="products">
        <div class="product">
            <h2>Laptop Pro</h2>
            <span class="price">$999</span>
            <a href="/products/laptop-pro">View Details</a>
        </div>
        <div class="product">
            <h2>Phone Ultra</h2>
            <span class="price">$599</span>
            <a href="/products/phone-ultra">View Details</a>
        </div>
    </div>

    <table class="specs">
        <tr><th>Model</th><th>RAM</th><th>Storage</th></tr>
        <tr><td>Laptop Pro</td><td>16GB</td><td>512GB</td></tr>
        <tr><td>Phone Ultra</td><td>8GB</td><td>256GB</td></tr>
    </table>

    <form action="/search" method="GET">
        <input type="text" name="q" placeholder="Search..." />
        <select name="category">
            <option value="all">All</option>
            <option value="laptops" selected>Laptops</option>
            <option value="phones">Phones</option>
        </select>
        <button type="submit">Search</button>
    </form>

    <a href="https://external-reviews.com">Read Reviews</a>
    <script>console.log('tracking');</script>
    <footer>Copyright 2024</footer>
</body>
</html>
"""


def css_selector_examples() -> None:
    """Extract data using CSS selectors."""
    print("=== CSS Selectors ===")
    titles = extract_text(SAMPLE_HTML, "h2")
    print(f"Product titles: {titles}")

    prices = extract_text(SAMPLE_HTML, ".price")
    print(f"Prices: {prices}")

    links = extract_attrs(SAMPLE_HTML, ".product a", attrs=["href"])
    print(f"Product links: {links}")


def table_extraction() -> None:
    """Extract data from HTML tables."""
    print("\n=== Table Extraction ===")
    rows = extract_table(SAMPLE_HTML, "table.specs")
    for row in rows:
        print(f"  {row}")


def link_extraction() -> None:
    """Extract and classify links."""
    print("\n=== Link Extraction ===")
    links = extract_links(SAMPLE_HTML, base_url="https://example-shop.com")
    for link in links:
        kind = "EXT" if link.is_external else "INT"
        print(f"  [{kind}] {link.url} - {link.text!r}")

    print("\n  Internal only:")
    internal = extract_links(
        SAMPLE_HTML, base_url="https://example-shop.com", same_domain_only=True
    )
    for link in internal:
        print(f"    {link.url}")


def form_parsing() -> None:
    """Parse HTML forms."""
    print("\n=== Form Parsing ===")
    forms = extract_forms(SAMPLE_HTML, base_url="https://example-shop.com")
    for form in forms:
        print(f"  [{form.method}] {form.action}")
        for field in form.fields:
            extra = f" options={field.options}" if field.options else ""
            print(f"    {field.name} ({field.type}) = {field.value!r}{extra}")
        print(f"  Submission dict: {form.to_dict()}")


def content_extraction() -> None:
    """Extract readable text content."""
    print("\n=== Content Extraction ===")
    text = extract_readable_text(SAMPLE_HTML)
    print(f"  Readable text:\n{text}")


def robots_example() -> None:
    """Parse and check robots.txt rules."""
    print("\n=== Robots.txt ===")
    robots_txt = """
User-agent: *
Disallow: /admin
Disallow: /api/internal
Allow: /api/public
Crawl-delay: 2

User-agent: Googlebot
Allow: /

Sitemap: https://example.com/sitemap.xml
"""
    rules = parse_robots_txt(robots_txt)
    paths = ["/", "/products", "/admin", "/api/internal", "/api/public"]
    for path in paths:
        allowed = is_allowed(rules, path)
        status = "ALLOWED" if allowed else "BLOCKED"
        print(f"  {status}: {path}")

    print(f"  Sitemaps: {rules.sitemaps}")
    print(f"  Crawl delay: {rules.crawl_delays.get('*', 'N/A')}s")


def sitemap_example() -> None:
    """Parse an XML sitemap."""
    print("\n=== Sitemap Parsing ===")
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://example.com/</loc>
            <lastmod>2024-01-15</lastmod>
            <changefreq>daily</changefreq>
            <priority>1.0</priority>
        </url>
        <url>
            <loc>https://example.com/products</loc>
            <lastmod>2024-01-14</lastmod>
            <priority>0.8</priority>
        </url>
    </urlset>"""
    entries = parse_sitemap(sitemap_xml)
    for entry in entries:
        print(f"  {entry.loc} (modified: {entry.lastmod}, priority: {entry.priority})")


if __name__ == "__main__":
    css_selector_examples()
    table_extraction()
    link_extraction()
    form_parsing()
    content_extraction()
    robots_example()
    sitemap_example()
