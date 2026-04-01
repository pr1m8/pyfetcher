"""Integration tests for pyfetcher MCP server tools.

Uses unittest.mock.patch on pyfetcher.mcp.server._fetch_sync to avoid
real HTTP requests. Tests each tool function directly (not through the
MCP protocol layer -- see test_mcp_e2e.py for that).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from pyfetcher.contracts.response import FetchResponse
from pyfetcher.mcp.models import (
    ArticleResult,
    DownloadResult,
    FetchResult,
    FormsResult,
    HeadersResult,
    LinksResult,
    MetadataResult,
    ProfileInfo,
    RobotsResult,
    ScrapeResult,
    SitemapResult,
    TableResult,
)
from pyfetcher.mcp.server import (
    check_robots,
    convert_html,
    download_file,
    extract_article,
    fetch_multiple,
    fetch_url,
    generate_headers,
    list_profiles,
    parse_sitemap,
    random_user_agent,
    scrape_css,
    scrape_forms,
    scrape_links,
    scrape_metadata,
    scrape_table,
    scrape_text,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    *,
    url: str = "https://example.com/",
    text: str = "<html><body>Hello</body></html>",
    status_code: int = 200,
    content_type: str = "text/html",
) -> FetchResponse:
    """Create a FetchResponse for mocking."""
    return FetchResponse(
        request_url=url,
        final_url=url,
        status_code=status_code,
        headers={"content-type": content_type},
        content_type=content_type,
        text=text,
        body=text.encode(),
        backend="httpx",
        elapsed_ms=42.0,
    )


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <meta name="description" content="A test page" />
    <meta property="og:title" content="OG Test" />
    <meta property="og:description" content="OG Description" />
    <meta property="og:image" content="https://example.com/image.png" />
    <meta property="og:type" content="website" />
    <link rel="canonical" href="https://example.com/canonical" />
    <link rel="icon" href="/favicon.ico" />
</head>
<body>
    <nav><a href="/">Home</a></nav>
    <h1>Main Title</h1>
    <p>First paragraph.</p>
    <p>Second paragraph.</p>
    <div class="content">
        <a href="/about">About</a>
        <a href="https://external.com">External</a>
    </div>
    <form action="/search" method="GET">
        <input type="text" name="q" value="" />
        <input type="hidden" name="lang" value="en" />
        <button type="submit">Search</button>
    </form>
    <table>
        <tr><th>Name</th><th>Age</th></tr>
        <tr><td>Alice</td><td>30</td></tr>
        <tr><td>Bob</td><td>25</td></tr>
    </table>
    <article>
        <h2>Article Title</h2>
        <p>Article body content goes here with enough text to be meaningful.</p>
    </article>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Fetching tools
# ---------------------------------------------------------------------------


class TestFetchUrl:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_fetch_url(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response()
        result = fetch_url("https://example.com")

        assert isinstance(result, FetchResult)
        assert result.url == "https://example.com/"
        assert result.final_url == "https://example.com/"
        assert result.status_code == 200
        assert result.ok is True
        assert result.content_type == "text/html"
        assert result.backend == "httpx"
        assert result.elapsed_ms == 42.0
        mock_fetch.assert_called_once_with(
            "https://example.com", backend="httpx", profile="chrome_win", timeout=30.0
        )

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_fetch_url_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = ConnectionError("Connection refused")
        with pytest.raises(ToolError, match="Failed to fetch"):
            fetch_url("https://badurl.example.com")

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_fetch_url_custom_params(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response()
        result = fetch_url(
            "https://example.com", backend="curl_cffi", profile="firefox_win", timeout=10
        )
        assert isinstance(result, FetchResult)
        mock_fetch.assert_called_once_with(
            "https://example.com", backend="curl_cffi", profile="firefox_win", timeout=10.0
        )


class TestFetchMultiple:
    @patch("pyfetcher.fetch.service.FetchService.afetch_many")
    @patch("pyfetcher.fetch.service.FetchService.aclose")
    def test_fetch_multiple(self, mock_aclose: MagicMock, mock_afetch: MagicMock) -> None:
        """Test fetch_multiple by mocking the async fetch_many method."""
        from pyfetcher.contracts.response import (
            BatchFetchResponse,
            BatchItemResponse,
            FetchResponse,
        )

        resp = FetchResponse(
            request_url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            headers={"content-type": "text/html"},
            content_type="text/html",
            text="<html>Hello</html>",
            backend="httpx",
            elapsed_ms=10.0,
        )
        batch_resp = BatchFetchResponse(
            items=[BatchItemResponse(request_url="https://example.com/", ok=True, response=resp)]
        )

        async def fake_afetch_many(batch):
            return batch_resp

        mock_afetch.side_effect = fake_afetch_many
        # mock_aclose is already an AsyncMock from @patch on an async method

        results = fetch_multiple(["https://example.com/"])
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].status_code == 200
        assert results[0].ok is True


# ---------------------------------------------------------------------------
# Scraping tools
# ---------------------------------------------------------------------------


class TestScrapeCss:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_css(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(text=SAMPLE_HTML)
        result = scrape_css("https://example.com", "h1")

        assert isinstance(result, ScrapeResult)
        assert result.url == "https://example.com"
        assert result.selector == "h1"
        assert result.count == 1
        assert "Main Title" in result.elements[0]

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_css_multiple(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(text=SAMPLE_HTML)
        result = scrape_css("https://example.com", "p")
        assert result.count >= 2

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_css_no_match(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(text="<html><body></body></html>")
        result = scrape_css("https://example.com", "h1")
        assert result.count == 0
        assert result.elements == []

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_css_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = ConnectionError("fail")
        with pytest.raises(ToolError, match="Scrape failed"):
            scrape_css("https://example.com", "h1")


class TestScrapeLinks:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_links(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(
            url="https://example.com/",
            text=SAMPLE_HTML,
        )
        result = scrape_links("https://example.com")

        assert isinstance(result, LinksResult)
        assert result.url == "https://example.com"
        assert result.total > 0
        # Should detect internal and external links
        assert result.internal >= 1
        assert result.external >= 1
        # Verify LinkInfo objects
        urls = [lnk.url for lnk in result.links]
        # The external link should be there
        assert any("external.com" in u for u in urls)

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_links_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = Exception("boom")
        with pytest.raises(ToolError, match="Link extraction failed"):
            scrape_links("https://example.com")


class TestScrapeText:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_text(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(text=SAMPLE_HTML)
        result = scrape_text("https://example.com")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain visible text from the page
        assert "Main Title" in result or "First paragraph" in result

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_text_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = Exception("fail")
        with pytest.raises(ToolError, match="Text extraction failed"):
            scrape_text("https://example.com")


class TestScrapeMetadata:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_metadata(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(
            url="https://example.com/",
            text=SAMPLE_HTML,
        )
        result = scrape_metadata("https://example.com")

        assert isinstance(result, MetadataResult)
        assert result.url == "https://example.com"
        assert result.title == "Test Page"
        assert result.description == "A test page"
        assert result.og_title == "OG Test"
        assert result.og_description == "OG Description"
        assert result.og_image == "https://example.com/image.png"
        assert result.og_type == "website"

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_metadata_minimal(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(text="<html><head></head><body></body></html>")
        result = scrape_metadata("https://example.com")
        assert isinstance(result, MetadataResult)
        assert result.title is None or result.title == ""

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_metadata_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = Exception("fail")
        with pytest.raises(ToolError, match="Metadata extraction failed"):
            scrape_metadata("https://example.com")


class TestScrapeForms:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_forms(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(
            url="https://example.com/",
            text=SAMPLE_HTML,
        )
        result = scrape_forms("https://example.com")

        assert isinstance(result, FormsResult)
        assert result.url == "https://example.com"
        assert result.count >= 1
        # Check the search form
        search_form = next((f for f in result.forms if "/search" in f.action), None)
        assert search_form is not None
        assert search_form.method.upper() == "GET"

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_forms_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = Exception("fail")
        with pytest.raises(ToolError, match="Form extraction failed"):
            scrape_forms("https://example.com")


class TestScrapeTable:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_table(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(text=SAMPLE_HTML)
        result = scrape_table("https://example.com")

        assert isinstance(result, TableResult)
        assert result.url == "https://example.com"
        assert result.selector == "table"
        assert result.row_count >= 2
        # Header row + data rows
        assert result.rows[0] == ["Name", "Age"]
        assert result.rows[1] == ["Alice", "30"]

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_table_custom_selector(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(
            text='<html><body><table id="data"><tr><td>A</td></tr></table></body></html>'
        )
        result = scrape_table("https://example.com", selector="table#data")
        assert result.selector == "table#data"
        assert result.row_count >= 1

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_scrape_table_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = Exception("fail")
        with pytest.raises(ToolError, match="Table extraction failed"):
            scrape_table("https://example.com")


# ---------------------------------------------------------------------------
# Robots & Sitemap
# ---------------------------------------------------------------------------


ROBOTS_TXT = """User-agent: *
Allow: /
Disallow: /admin/

Sitemap: https://example.com/sitemap.xml
"""

SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/</loc>
    <lastmod>2024-01-01</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://example.com/about</loc>
    <lastmod>2024-02-01</lastmod>
  </url>
</urlset>
"""


class TestCheckRobots:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_check_robots(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(
            url="https://example.com/robots.txt",
            text=ROBOTS_TXT,
            content_type="text/plain",
        )
        result = check_robots("https://example.com", path="/")

        assert isinstance(result, RobotsResult)
        assert result.url == "https://example.com"
        assert result.path == "/"
        assert result.allowed is True
        assert "https://example.com/sitemap.xml" in result.sitemaps

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_check_robots_disallowed(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(
            url="https://example.com/robots.txt",
            text=ROBOTS_TXT,
            content_type="text/plain",
        )
        result = check_robots("https://example.com", path="/admin/secret")
        assert result.allowed is False

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_check_robots_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = Exception("timeout")
        with pytest.raises(ToolError, match="Robots check failed"):
            check_robots("https://example.com")


class TestParseSitemap:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_parse_sitemap(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(
            url="https://example.com/sitemap.xml",
            text=SITEMAP_XML,
            content_type="application/xml",
        )
        result = parse_sitemap("https://example.com/sitemap.xml")

        assert isinstance(result, SitemapResult)
        assert result.url == "https://example.com/sitemap.xml"
        assert result.count == 2
        assert len(result.entries) == 2
        locs = [e["loc"] for e in result.entries]
        assert "https://example.com/" in locs
        assert "https://example.com/about" in locs

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_parse_sitemap_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = Exception("fail")
        with pytest.raises(ToolError, match="Sitemap parsing failed"):
            parse_sitemap("https://example.com/sitemap.xml")


# ---------------------------------------------------------------------------
# Headers & Profiles
# ---------------------------------------------------------------------------


class TestGenerateHeaders:
    def test_generate_headers(self) -> None:
        result = generate_headers()
        assert isinstance(result, HeadersResult)
        assert result.profile == "chrome_win"
        assert "user-agent" in result.headers
        assert "Mozilla" in result.headers["user-agent"]

    def test_generate_headers_firefox(self) -> None:
        result = generate_headers(profile="firefox_win")
        assert result.profile == "firefox_win"
        assert "Firefox" in result.headers["user-agent"]

    def test_generate_headers_all_profiles(self) -> None:
        """Verify headers can be generated for every known profile."""
        from pyfetcher.headers.profiles import list_profiles as _list

        for name in _list():
            result = generate_headers(profile=name)
            assert result.profile == name
            assert "user-agent" in result.headers


class TestListProfiles:
    def test_list_profiles(self) -> None:
        result = list_profiles()
        assert isinstance(result, list)
        assert len(result) >= 11
        assert all(isinstance(p, ProfileInfo) for p in result)

        names = [p.name for p in result]
        assert "chrome_win" in names
        assert "firefox_mac" in names
        assert "safari_mac" in names

    def test_profile_info_fields(self) -> None:
        result = list_profiles()
        chrome = next(p for p in result if p.name == "chrome_win")
        assert chrome.browser == "chrome"
        assert chrome.platform == "Windows"
        assert chrome.mobile is False


class TestRandomUserAgent:
    def test_random_user_agent(self) -> None:
        result = random_user_agent()
        assert isinstance(result, str)
        assert "Mozilla" in result
        assert len(result) > 20

    def test_random_user_agent_filtered(self) -> None:
        result = random_user_agent(browser="chrome")
        assert isinstance(result, str)
        assert "Chrome" in result


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------


class TestExtractArticle:
    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_extract_article(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = _make_response(
            url="https://example.com/article",
            text=SAMPLE_HTML,
        )
        result = extract_article("https://example.com/article")

        assert isinstance(result, ArticleResult)
        assert result.url == "https://example.com/article"
        assert result.title == "Test Page"
        # text should be extracted (via either extractor or fallback)
        assert result.text is not None
        assert len(result.text) > 0

    @patch("pyfetcher.mcp.server._fetch_sync")
    def test_extract_article_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = ConnectionError("fail")
        with pytest.raises(ToolError, match="Article extraction failed"):
            extract_article("https://example.com/article")


class TestConvertHtml:
    def test_convert_html_plaintext(self) -> None:
        html = "<html><body><h1>Title</h1><p>Hello world</p></body></html>"
        result = convert_html(html, format="plaintext")
        assert isinstance(result, str)
        assert "Hello world" in result

    def test_convert_html_markdown(self) -> None:
        html = "<html><body><h1>Title</h1><p>Hello world</p></body></html>"
        try:
            result = convert_html(html, format="markdown")
            assert isinstance(result, str)
            # Markdown should contain text from the HTML
            assert "Hello world" in result or "Title" in result
        except ToolError as exc:
            # markdownify may not be installed
            assert "Install" in str(exc)

    def test_convert_html_invalid_format(self) -> None:
        with pytest.raises(ToolError, match="Unknown format"):
            convert_html("<p>test</p>", format="pdf")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


class TestDownloadFile:
    @patch("pyfetcher.download.service.DownloadService.adownload_to_path")
    def test_download_file(self, mock_dl: MagicMock) -> None:
        import tempfile
        from pathlib import Path

        # Create a temp file to simulate downloaded content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"file content here")
            tmp_path = Path(f.name)

        try:
            # Mock the async download to return the temp path
            async def fake_download(req, dest):
                return tmp_path

            mock_dl.side_effect = fake_download

            result = download_file("https://example.com/file.txt", str(tmp_path))
            assert isinstance(result, DownloadResult)
            assert result.url == "https://example.com/file.txt"
            assert result.path == str(tmp_path)
            assert result.size_bytes == 17  # len("file content here")
            assert result.checksum_sha256 is not None
            assert len(result.checksum_sha256) == 64
        finally:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class TestResources:
    def test_resource_profiles(self) -> None:
        from pyfetcher.mcp.server import resource_profiles

        result = resource_profiles()
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) >= 11
        names = [p["name"] for p in data]
        assert "chrome_win" in names

    def test_resource_backends(self) -> None:
        from pyfetcher.mcp.server import resource_backends

        result = resource_backends()
        data = json.loads(result)
        assert isinstance(data, list)
        backend_names = [b["name"] for b in data]
        assert "httpx" in backend_names
        assert "aiohttp" in backend_names

    def test_resource_version(self) -> None:
        from pyfetcher.mcp.server import resource_version

        result = resource_version()
        data = json.loads(result)
        assert data["name"] == "fetchkit"
        assert data["import_name"] == "pyfetcher"
        assert data["version"] == "0.2.0"
        assert data["tools"] == 16
        assert data["resources"] == 4
        assert data["prompts"] == 4

    def test_resource_profile_headers(self) -> None:
        from pyfetcher.mcp.server import resource_profile_headers

        result = resource_profile_headers("chrome_win")
        data = json.loads(result)
        assert "user-agent" in data
        assert "Mozilla" in data["user-agent"]

    def test_resource_profile_headers_safari(self) -> None:
        from pyfetcher.mcp.server import resource_profile_headers

        result = resource_profile_headers("safari_mac")
        data = json.loads(result)
        assert "user-agent" in data
        assert "Safari" in data["user-agent"]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


class TestPrompts:
    def test_web_research_prompt(self) -> None:
        from pyfetcher.mcp.server import web_research

        result = web_research("Python web scraping")
        assert isinstance(result, str)
        assert "Python web scraping" in result
        assert "fetch_url" in result

    def test_site_audit_prompt(self) -> None:
        from pyfetcher.mcp.server import site_audit

        result = site_audit("https://example.com")
        assert isinstance(result, str)
        assert "https://example.com" in result
        assert "check_robots" in result

    def test_scrape_guide_prompt(self) -> None:
        from pyfetcher.mcp.server import scrape_guide

        result = scrape_guide("https://example.com", "product prices")
        assert isinstance(result, str)
        assert "https://example.com" in result
        assert "product prices" in result
        assert "scrape_css" in result

    def test_compare_pages_prompt(self) -> None:
        from pyfetcher.mcp.server import compare_pages

        result = compare_pages("https://page1.com", "https://page2.com")
        assert isinstance(result, str)
        assert "https://page1.com" in result
        assert "https://page2.com" in result
        assert "scrape_metadata" in result
