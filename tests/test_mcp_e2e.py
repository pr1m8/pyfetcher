"""End-to-end tests for pyfetcher MCP server.

Uses FastMCP's built-in testing API (mcp.call_tool, mcp.read_resource,
mcp.get_prompt) to exercise tools through the full MCP protocol stack.
Network-dependent tools mock _fetch_sync; header/profile tools run live.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from pyfetcher.contracts.response import FetchResponse
from pyfetcher.mcp.server import mcp

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
  </url>
</urlset>
"""


# ---------------------------------------------------------------------------
# E2E: Headers & Profiles (no mocking needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_generate_headers() -> None:
    """E2E: call generate_headers through MCP protocol."""
    result = await mcp.call_tool("generate_headers", {"profile": "chrome_win"})
    assert len(result.content) > 0
    data = json.loads(result.content[0].text)
    assert data["profile"] == "chrome_win"
    assert "headers" in data
    assert "user-agent" in data["headers"]
    assert "Mozilla" in data["headers"]["user-agent"]


@pytest.mark.asyncio
async def test_e2e_generate_headers_firefox() -> None:
    """E2E: generate_headers with firefox profile."""
    result = await mcp.call_tool("generate_headers", {"profile": "firefox_win"})
    data = json.loads(result.content[0].text)
    assert data["profile"] == "firefox_win"
    assert "Firefox" in data["headers"]["user-agent"]


@pytest.mark.asyncio
async def test_e2e_list_profiles() -> None:
    """E2E: list_profiles returns all browser profiles."""
    result = await mcp.call_tool("list_profiles", {})
    assert len(result.content) > 0
    data = json.loads(result.content[0].text)
    assert len(data) >= 11
    assert any(p["name"] == "chrome_win" for p in data)
    assert any(p["name"] == "safari_mac" for p in data)
    assert any(p["name"] == "firefox_linux" for p in data)


@pytest.mark.asyncio
async def test_e2e_random_user_agent() -> None:
    """E2E: random_user_agent returns a UA string."""
    result = await mcp.call_tool("random_user_agent", {})
    assert len(result.content) > 0
    ua = result.content[0].text
    # FastMCP wraps string returns in JSON quotes
    if ua.startswith('"'):
        ua = json.loads(ua)
    assert "Mozilla" in ua


@pytest.mark.asyncio
async def test_e2e_random_user_agent_chrome() -> None:
    """E2E: random_user_agent filtered by browser."""
    result = await mcp.call_tool("random_user_agent", {"browser": "chrome"})
    ua = result.content[0].text
    if ua.startswith('"'):
        ua = json.loads(ua)
    assert "Chrome" in ua


# ---------------------------------------------------------------------------
# E2E: Fetching tools (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_fetch_url() -> None:
    """E2E: fetch_url through MCP protocol with mocked network."""
    mock_response = _make_response()
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool("fetch_url", {"url": "https://example.com"})
        data = json.loads(result.content[0].text)
        assert data["status_code"] == 200
        assert data["ok"] is True
        assert data["backend"] == "httpx"
        assert data["elapsed_ms"] == 42.0


@pytest.mark.asyncio
async def test_e2e_fetch_url_with_params() -> None:
    """E2E: fetch_url with custom backend and profile."""
    mock_response = _make_response()
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response) as mock_fetch:
        result = await mcp.call_tool(
            "fetch_url",
            {
                "url": "https://example.com",
                "backend": "curl_cffi",
                "profile": "firefox_mac",
                "timeout": 10,
            },
        )
        data = json.loads(result.content[0].text)
        assert data["status_code"] == 200
        mock_fetch.assert_called_once_with(
            "https://example.com", backend="curl_cffi", profile="firefox_mac", timeout=10.0
        )


@pytest.mark.asyncio
async def test_e2e_fetch_url_error() -> None:
    """E2E: fetch_url error raises ToolError, which MCP wraps as isError."""
    with patch("pyfetcher.mcp.server._fetch_sync", side_effect=ConnectionError("refused")):
        from fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Failed to fetch"):
            await mcp.call_tool("fetch_url", {"url": "https://bad.example.com"})


# ---------------------------------------------------------------------------
# E2E: Scraping tools (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_scrape_css() -> None:
    """E2E: scrape_css extracts elements by CSS selector."""
    mock_response = _make_response(text=SAMPLE_HTML)
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool(
            "scrape_css",
            {
                "url": "https://example.com",
                "selector": "h1",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["selector"] == "h1"
        assert data["count"] == 1
        assert "Main Title" in data["elements"][0]


@pytest.mark.asyncio
async def test_e2e_scrape_links() -> None:
    """E2E: scrape_links extracts and classifies links."""
    mock_response = _make_response(url="https://example.com/", text=SAMPLE_HTML)
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool("scrape_links", {"url": "https://example.com"})
        data = json.loads(result.content[0].text)
        assert data["total"] > 0
        assert data["internal"] >= 1
        assert data["external"] >= 1
        urls = [lnk["url"] for lnk in data["links"]]
        assert any("external.com" in u for u in urls)


@pytest.mark.asyncio
async def test_e2e_scrape_text() -> None:
    """E2E: scrape_text returns readable text content."""
    mock_response = _make_response(text=SAMPLE_HTML)
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool("scrape_text", {"url": "https://example.com"})
        text = result.content[0].text
        # scrape_text returns a plain string, MCP wraps in JSON quotes
        if text.startswith('"'):
            text = json.loads(text)
        assert len(text) > 0
        assert "Main Title" in text or "First paragraph" in text


@pytest.mark.asyncio
async def test_e2e_scrape_metadata() -> None:
    """E2E: scrape_metadata extracts page meta tags and OG data."""
    mock_response = _make_response(url="https://example.com/", text=SAMPLE_HTML)
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool("scrape_metadata", {"url": "https://example.com"})
        data = json.loads(result.content[0].text)
        assert data["title"] == "Test Page"
        assert data["description"] == "A test page"
        assert data["og_title"] == "OG Test"
        assert data["og_description"] == "OG Description"
        assert data["og_image"] == "https://example.com/image.png"


@pytest.mark.asyncio
async def test_e2e_scrape_forms() -> None:
    """E2E: scrape_forms extracts HTML forms."""
    mock_response = _make_response(url="https://example.com/", text=SAMPLE_HTML)
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool("scrape_forms", {"url": "https://example.com"})
        data = json.loads(result.content[0].text)
        assert data["count"] >= 1
        actions = [f["action"] for f in data["forms"]]
        assert any("/search" in a for a in actions)


@pytest.mark.asyncio
async def test_e2e_scrape_table() -> None:
    """E2E: scrape_table extracts HTML table data."""
    mock_response = _make_response(text=SAMPLE_HTML)
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool("scrape_table", {"url": "https://example.com"})
        data = json.loads(result.content[0].text)
        assert data["row_count"] >= 2
        assert data["rows"][0] == ["Name", "Age"]
        assert data["rows"][1] == ["Alice", "30"]


# ---------------------------------------------------------------------------
# E2E: Robots & Sitemap (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_check_robots() -> None:
    """E2E: check_robots fetches and parses robots.txt."""
    mock_response = _make_response(
        url="https://example.com/robots.txt",
        text=ROBOTS_TXT,
        content_type="text/plain",
    )
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool(
            "check_robots",
            {
                "url": "https://example.com",
                "path": "/",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["allowed"] is True
        assert "https://example.com/sitemap.xml" in data["sitemaps"]


@pytest.mark.asyncio
async def test_e2e_check_robots_disallowed() -> None:
    """E2E: check_robots reports disallowed paths."""
    mock_response = _make_response(
        url="https://example.com/robots.txt",
        text=ROBOTS_TXT,
        content_type="text/plain",
    )
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool(
            "check_robots",
            {
                "url": "https://example.com",
                "path": "/admin/secret",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["allowed"] is False


@pytest.mark.asyncio
async def test_e2e_parse_sitemap() -> None:
    """E2E: parse_sitemap returns sitemap entries."""
    mock_response = _make_response(
        url="https://example.com/sitemap.xml",
        text=SITEMAP_XML,
        content_type="application/xml",
    )
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool(
            "parse_sitemap",
            {
                "url": "https://example.com/sitemap.xml",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["count"] == 2
        locs = [e["loc"] for e in data["entries"]]
        assert "https://example.com/" in locs
        assert "https://example.com/about" in locs


# ---------------------------------------------------------------------------
# E2E: Content extraction (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_extract_article() -> None:
    """E2E: extract_article extracts article content."""
    mock_response = _make_response(
        url="https://example.com/article",
        text=SAMPLE_HTML,
    )
    with patch("pyfetcher.mcp.server._fetch_sync", return_value=mock_response):
        result = await mcp.call_tool(
            "extract_article",
            {
                "url": "https://example.com/article",
            },
        )
        data = json.loads(result.content[0].text)
        assert data["url"] == "https://example.com/article"
        assert data["title"] == "Test Page"
        assert data["text"] is not None
        assert len(data["text"]) > 0


@pytest.mark.asyncio
async def test_e2e_convert_html_plaintext() -> None:
    """E2E: convert_html in plaintext mode."""
    result = await mcp.call_tool(
        "convert_html",
        {
            "html": "<h1>Title</h1><p>Hello world</p>",
            "format": "plaintext",
        },
    )
    text = result.content[0].text
    if text.startswith('"'):
        text = json.loads(text)
    assert "Hello world" in text


@pytest.mark.asyncio
async def test_e2e_convert_html_markdown() -> None:
    """E2E: convert_html in markdown mode (skips if markdownify not installed)."""
    try:
        result = await mcp.call_tool(
            "convert_html",
            {
                "html": "<h1>Title</h1><p>Hello world</p>",
                "format": "markdown",
            },
        )
        text = result.content[0].text
        if text.startswith('"'):
            text = json.loads(text)
        assert "Hello world" in text or "Title" in text
    except Exception as exc:
        # markdownify may not be installed; ToolError is raised
        assert "Install" in str(exc) or "markdown" in str(exc).lower()


# ---------------------------------------------------------------------------
# E2E: Resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_resource_profiles() -> None:
    """E2E: read pyfetcher://profiles resource."""
    result = await mcp.read_resource("pyfetcher://profiles")
    data = json.loads(result.contents[0].content)
    assert isinstance(data, list)
    assert len(data) >= 11
    names = [p["name"] for p in data]
    assert "chrome_win" in names


@pytest.mark.asyncio
async def test_e2e_resource_backends() -> None:
    """E2E: read pyfetcher://backends resource."""
    result = await mcp.read_resource("pyfetcher://backends")
    data = json.loads(result.contents[0].content)
    assert isinstance(data, list)
    backend_names = [b["name"] for b in data]
    assert "httpx" in backend_names
    assert "aiohttp" in backend_names
    assert "curl_cffi" in backend_names
    assert "cloudscraper" in backend_names


@pytest.mark.asyncio
async def test_e2e_resource_version() -> None:
    """E2E: read pyfetcher://version resource."""
    result = await mcp.read_resource("pyfetcher://version")
    data = json.loads(result.contents[0].content)
    assert data["name"] == "fetchkit"
    assert data["import_name"] == "pyfetcher"
    assert data["version"] == "0.2.0"
    assert data["tools"] == 16
    assert data["resources"] == 4
    assert data["prompts"] == 4
    assert "httpx" in data["backends"]


@pytest.mark.asyncio
async def test_e2e_resource_profile_headers() -> None:
    """E2E: read pyfetcher://profiles/chrome_win resource template."""
    result = await mcp.read_resource("pyfetcher://profiles/chrome_win")
    data = json.loads(result.contents[0].content)
    assert "user-agent" in data
    assert "Mozilla" in data["user-agent"]


@pytest.mark.asyncio
async def test_e2e_resource_profile_headers_safari() -> None:
    """E2E: read pyfetcher://profiles/safari_mac returns Safari headers."""
    result = await mcp.read_resource("pyfetcher://profiles/safari_mac")
    data = json.loads(result.contents[0].content)
    assert "user-agent" in data
    assert "Safari" in data["user-agent"]


# ---------------------------------------------------------------------------
# E2E: Prompts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_web_research_prompt() -> None:
    """E2E: get web_research prompt through MCP protocol."""
    prompt = await mcp.get_prompt("web_research")
    assert prompt is not None
    rendered = await prompt.render({"topic": "Python web scraping"})
    text = rendered.messages[0].content.text
    assert "Python web scraping" in text
    assert "fetch_url" in text


@pytest.mark.asyncio
async def test_e2e_site_audit_prompt() -> None:
    """E2E: get site_audit prompt through MCP protocol."""
    prompt = await mcp.get_prompt("site_audit")
    assert prompt is not None
    rendered = await prompt.render({"url": "https://example.com"})
    text = rendered.messages[0].content.text
    assert "https://example.com" in text
    assert "check_robots" in text


@pytest.mark.asyncio
async def test_e2e_scrape_guide_prompt() -> None:
    """E2E: get scrape_guide prompt through MCP protocol."""
    prompt = await mcp.get_prompt("scrape_guide")
    assert prompt is not None
    rendered = await prompt.render({"url": "https://example.com", "goal": "product prices"})
    text = rendered.messages[0].content.text
    assert "https://example.com" in text
    assert "product prices" in text


@pytest.mark.asyncio
async def test_e2e_compare_pages_prompt() -> None:
    """E2E: get compare_pages prompt through MCP protocol."""
    prompt = await mcp.get_prompt("compare_pages")
    assert prompt is not None
    rendered = await prompt.render(
        {
            "url1": "https://page1.com",
            "url2": "https://page2.com",
        }
    )
    text = rendered.messages[0].content.text
    assert "https://page1.com" in text
    assert "https://page2.com" in text
    assert "scrape_metadata" in text
