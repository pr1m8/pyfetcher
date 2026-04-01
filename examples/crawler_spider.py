"""Custom spider example for pyfetcher.

Demonstrates creating a spider with URL routing and custom handlers.
"""

from __future__ import annotations

from pyfetcher.contracts.response import FetchResponse
from pyfetcher.crawler.spider import Spider, SpiderResult
from pyfetcher.scrape.links import extract_links
from pyfetcher.scrape.selectors import extract_text


def create_spider() -> Spider:
    """Create a spider with custom route handlers."""
    spider = Spider(name="example-spider")

    async def handle_blog_post(url: str, response: FetchResponse) -> SpiderResult:
        """Handle blog post pages -- extract title and links."""
        html = response.text or ""
        titles = extract_text(html, "h1")
        links = extract_links(html, base_url=url, same_domain_only=True)
        return SpiderResult(
            discovered_urls=[l.url for l in links],
            items=[{"url": url, "title": titles[0] if titles else None, "type": "blog_post"}],
        )

    async def handle_listing(url: str, response: FetchResponse) -> SpiderResult:
        """Handle listing/index pages -- just follow links."""
        html = response.text or ""
        links = extract_links(html, base_url=url, same_domain_only=True)
        return SpiderResult(discovered_urls=[l.url for l in links])

    async def default_handler(url: str, response: FetchResponse) -> SpiderResult:
        """Default handler for unmatched URLs."""
        html = response.text or ""
        links = extract_links(html, base_url=url, same_domain_only=True)
        return SpiderResult(discovered_urls=[l.url for l in links[:10]])

    spider.router.add(r"/blog/\d{4}/", handle_blog_post)
    spider.router.add(r"/blog/?$", handle_listing)
    spider.router.add(r"/archive", handle_listing)
    spider.router.default(default_handler)

    return spider


def demo() -> None:
    """Show how the spider routes URLs."""
    spider = create_spider()

    urls = [
        "https://example.com/blog/2024/my-post",
        "https://example.com/blog/",
        "https://example.com/archive",
        "https://example.com/about",
        "https://example.com/unknown-page",
    ]

    print("=== Spider URL Routing ===")
    for url in urls:
        handler = spider.router.resolve(url)
        name = handler.__name__ if handler else "None"
        print(f"  {url} -> {name}")


if __name__ == "__main__":
    demo()
