"""Tests for pyfetcher.crawler modules: dedup, spider, politeness, feeds, discovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# dedup.py tests
# ---------------------------------------------------------------------------
from pyfetcher.crawler.dedup import normalize_url, url_hash


class TestNormalizeUrl:
    def test_normalize_url_lowercase_host(self):
        result = normalize_url("https://EXAMPLE.COM/path")
        assert "example.com" in result

    def test_normalize_url_strips_fragment(self):
        result = normalize_url("https://example.com/page#section")
        assert "#" not in result
        assert "section" not in result

    def test_normalize_url_sorts_query_params(self):
        result = normalize_url("https://example.com/page?z=1&a=2")
        assert result.index("a=2") < result.index("z=1")

    def test_normalize_url_strips_default_port(self):
        result = normalize_url("https://example.com:443/path")
        assert ":443" not in result

    def test_normalize_url_strips_default_port_http(self):
        result = normalize_url("http://example.com:80/path")
        assert ":80" not in result

    def test_normalize_url_keeps_non_default_port(self):
        result = normalize_url("https://example.com:8080/path")
        assert ":8080" in result

    def test_normalize_url_trailing_slash(self):
        result = normalize_url("https://example.com/path/")
        assert result.endswith("/path") or result.endswith("/path?") is False
        assert not result.rstrip("?").endswith("/path/")

    def test_normalize_url_root_path_preserved(self):
        result = normalize_url("https://example.com/")
        assert result.endswith("/")

    def test_normalize_url_lowercase_scheme(self):
        result = normalize_url("HTTPS://example.com/page")
        assert result.startswith("https://")


class TestUrlHash:
    def test_url_hash_deterministic(self):
        h1 = url_hash("https://example.com/page")
        h2 = url_hash("https://example.com/page")
        assert h1 == h2

    def test_url_hash_different_urls(self):
        h1 = url_hash("https://example.com/page1")
        h2 = url_hash("https://example.com/page2")
        assert h1 != h2

    def test_url_hash_returns_int(self):
        result = url_hash("https://example.com/")
        assert isinstance(result, int)

    def test_url_hash_is_64_bit(self):
        """Hash should fit in a signed 64-bit integer."""
        result = url_hash("https://example.com/")
        assert -(2**63) <= result <= 2**63 - 1


# ---------------------------------------------------------------------------
# spider.py tests
# ---------------------------------------------------------------------------
from pyfetcher.crawler.spider import Router, Spider, SpiderResult


class TestSpiderResult:
    def test_spider_result_dataclass_defaults(self):
        result = SpiderResult()
        assert result.discovered_urls == []
        assert result.items == []
        assert result.media_urls == []

    def test_spider_result_dataclass_custom(self):
        result = SpiderResult(
            discovered_urls=["https://a.com"],
            items=[{"title": "Test"}],
            media_urls=["https://cdn.com/img.png"],
        )
        assert len(result.discovered_urls) == 1
        assert len(result.items) == 1
        assert len(result.media_urls) == 1


class TestRouter:
    def test_router_add_and_resolve(self):
        router = Router()
        handler = AsyncMock()
        router.add(r"example\.com/articles/", handler)
        resolved = router.resolve("https://example.com/articles/123")
        assert resolved is handler

    def test_router_no_match_returns_none(self):
        router = Router()
        handler = AsyncMock()
        router.add(r"example\.com/articles/", handler)
        resolved = router.resolve("https://other.com/page")
        assert resolved is None

    def test_router_default_handler(self):
        router = Router()
        default_handler = AsyncMock()
        router.default(default_handler)
        resolved = router.resolve("https://anything.com/anything")
        assert resolved is default_handler

    def test_router_specific_takes_precedence_over_default(self):
        router = Router()
        specific = AsyncMock()
        fallback = AsyncMock()
        router.add(r"/articles/", specific)
        router.default(fallback)
        resolved = router.resolve("https://example.com/articles/1")
        assert resolved is specific

    def test_router_first_match_wins(self):
        router = Router()
        first = AsyncMock()
        second = AsyncMock()
        router.add(r"/page", first)
        router.add(r"/page", second)
        resolved = router.resolve("https://example.com/page")
        assert resolved is first


class TestSpider:
    @pytest.mark.asyncio
    async def test_spider_handle_routes_to_handler(self):
        spider = Spider(name="test")
        mock_handler = AsyncMock(return_value=SpiderResult(discovered_urls=["https://found.com"]))
        spider.router.add(r"example\.com", mock_handler)

        mock_response = MagicMock()
        result = await spider.handle("https://example.com/page", mock_response)

        mock_handler.assert_called_once_with("https://example.com/page", mock_response)
        assert result.discovered_urls == ["https://found.com"]

    @pytest.mark.asyncio
    async def test_spider_handle_no_handler_returns_empty(self):
        spider = Spider(name="test")
        mock_response = MagicMock()
        result = await spider.handle("https://unknown.com/page", mock_response)
        assert result.discovered_urls == []
        assert result.items == []
        assert result.media_urls == []

    def test_spider_name(self):
        spider = Spider(name="my-spider")
        assert spider.name == "my-spider"


# ---------------------------------------------------------------------------
# politeness.py tests
# ---------------------------------------------------------------------------
from pyfetcher.crawler.politeness import PolitenessEnforcer


class TestPolitenessEnforcer:
    def test_extract_hostname(self):
        enforcer = PolitenessEnforcer()
        hostname = enforcer.extract_hostname("https://example.com:8080/path")
        assert hostname == "example.com:8080"

    def test_extract_hostname_standard_port(self):
        enforcer = PolitenessEnforcer()
        hostname = enforcer.extract_hostname("https://example.com/path")
        assert hostname == "example.com"

    def test_check_robots_allowed(self):
        enforcer = PolitenessEnforcer()
        robots = "User-agent: *\nDisallow: /admin\nAllow: /public"
        assert enforcer.check_robots(robots, "/public") is True

    def test_check_robots_disallowed(self):
        enforcer = PolitenessEnforcer()
        robots = "User-agent: *\nDisallow: /admin"
        assert enforcer.check_robots(robots, "/admin/settings") is False

    def test_check_robots_none_allows_all(self):
        enforcer = PolitenessEnforcer()
        assert enforcer.check_robots(None, "/anything") is True

    def test_get_crawl_delay_from_robots(self):
        enforcer = PolitenessEnforcer()
        robots = "User-agent: *\nCrawl-delay: 5"
        delay = enforcer.get_crawl_delay(robots)
        assert delay == 5.0

    def test_get_crawl_delay_default(self):
        enforcer = PolitenessEnforcer(default_delay_seconds=2.0)
        delay = enforcer.get_crawl_delay(None)
        assert delay == 2.0

    def test_get_crawl_delay_robots_without_directive(self):
        enforcer = PolitenessEnforcer(default_delay_seconds=3.0)
        robots = "User-agent: *\nDisallow: /private"
        delay = enforcer.get_crawl_delay(robots)
        assert delay == 3.0


# ---------------------------------------------------------------------------
# feeds.py tests
# ---------------------------------------------------------------------------
from pyfetcher.crawler.feeds import (
    FeedEntry,
    FeedPollResult,
    calculate_poll_interval,
    compute_entry_hash,
)


class TestFeedEntryHash:
    def test_compute_entry_hash_deterministic(self):
        entry = FeedEntry(url="https://example.com/post/1", title="Post 1")
        h1 = compute_entry_hash(entry)
        h2 = compute_entry_hash(entry)
        assert h1 == h2

    def test_compute_entry_hash_different_entries(self):
        e1 = FeedEntry(url="https://example.com/post/1", title="Post 1")
        e2 = FeedEntry(url="https://example.com/post/2", title="Post 2")
        assert compute_entry_hash(e1) != compute_entry_hash(e2)

    def test_compute_entry_hash_returns_string(self):
        entry = FeedEntry(url="https://example.com/post/1")
        result = compute_entry_hash(entry)
        assert isinstance(result, str)
        assert len(result) == 16  # sha256 hex truncated to 16 chars


class TestCalculatePollInterval:
    def test_calculate_poll_interval_many_entries(self):
        """5+ entries should halve the interval."""
        result = calculate_poll_interval(5, current_interval=60)
        assert result == 30

    def test_calculate_poll_interval_some_entries(self):
        """1-4 entries should keep the interval."""
        result = calculate_poll_interval(3, current_interval=60)
        assert result == 60

    def test_calculate_poll_interval_no_entries(self):
        """0 entries should double the interval."""
        result = calculate_poll_interval(0, current_interval=60)
        assert result == 120

    def test_calculate_poll_interval_bounds_min(self):
        """Should not go below min_interval."""
        result = calculate_poll_interval(10, current_interval=10, min_interval=10)
        assert result == 10

    def test_calculate_poll_interval_bounds_max(self):
        """Should not exceed max_interval."""
        result = calculate_poll_interval(0, current_interval=1000, max_interval=1440)
        assert result == 1440

    def test_calculate_poll_interval_no_entries_at_max(self):
        """Already at max should stay at max."""
        result = calculate_poll_interval(0, current_interval=1440, max_interval=1440)
        assert result == 1440


class TestFeedDataclasses:
    def test_feed_entry_frozen(self):
        entry = FeedEntry(url="https://example.com", title="Test")
        with pytest.raises(AttributeError):
            entry.url = "changed"

    def test_feed_poll_result_defaults(self):
        result = FeedPollResult()
        assert result.new_entries == []
        assert result.latest_entry_hash is None
        assert result.suggested_interval_minutes == 60


# ---------------------------------------------------------------------------
# discovery.py tests
# ---------------------------------------------------------------------------
from pyfetcher.crawler.discovery import (
    build_seed_urls,
    discover_sitemaps_from_robots,
    discover_urls_from_sitemap,
)


class TestDiscovery:
    def test_discover_sitemaps_from_robots(self):
        robots_txt = (
            "User-agent: *\n"
            "Disallow: /private\n"
            "Sitemap: https://example.com/sitemap.xml\n"
            "Sitemap: https://example.com/sitemap2.xml\n"
        )
        sitemaps = discover_sitemaps_from_robots(robots_txt)
        assert len(sitemaps) == 2
        assert "https://example.com/sitemap.xml" in sitemaps
        assert "https://example.com/sitemap2.xml" in sitemaps

    def test_discover_sitemaps_from_robots_no_sitemaps(self):
        robots_txt = "User-agent: *\nDisallow: /private\n"
        sitemaps = discover_sitemaps_from_robots(robots_txt)
        assert sitemaps == []

    def test_discover_urls_from_sitemap(self):
        sitemap_xml = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/page1</loc></url>"
            "<url><loc>https://example.com/page2</loc></url>"
            "</urlset>"
        )
        urls = discover_urls_from_sitemap(sitemap_xml)
        assert len(urls) == 2
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls

    def test_discover_urls_from_sitemap_index(self):
        sitemap_xml = (
            '<?xml version="1.0"?>'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>"
            "<sitemap><loc>https://example.com/sitemap2.xml</loc></sitemap>"
            "</sitemapindex>"
        )
        urls = discover_urls_from_sitemap(sitemap_xml)
        assert len(urls) == 2

    def test_build_seed_urls_deduplicates(self):
        urls = build_seed_urls(
            urls=["https://example.com/a", "https://example.com/a", "https://example.com/b"]
        )
        assert len(urls) == 2
        assert urls[0] == "https://example.com/a"
        assert urls[1] == "https://example.com/b"

    def test_build_seed_urls_combined(self):
        robots_txt = "User-agent: *\nSitemap: https://example.com/sitemap.xml\n"
        sitemap_xml = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/page1</loc></url>"
            "</urlset>"
        )
        urls = build_seed_urls(
            urls=["https://example.com/seed"],
            robots_txt=robots_txt,
            sitemap_xml=sitemap_xml,
        )
        assert "https://example.com/seed" in urls
        assert "https://example.com/sitemap.xml" in urls
        assert "https://example.com/page1" in urls
        assert len(urls) == 3

    def test_build_seed_urls_empty(self):
        urls = build_seed_urls()
        assert urls == []

    def test_build_seed_urls_dedup_across_sources(self):
        """URL appearing in both explicit list and sitemap should appear once."""
        sitemap_xml = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/shared</loc></url>"
            "</urlset>"
        )
        urls = build_seed_urls(
            urls=["https://example.com/shared"],
            sitemap_xml=sitemap_xml,
        )
        assert urls.count("https://example.com/shared") == 1
