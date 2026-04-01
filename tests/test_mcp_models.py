"""Unit tests for pyfetcher.mcp.models."""

from __future__ import annotations

import json

from pyfetcher.mcp.models import (
    ArticleResult,
    DownloadResult,
    FetchResult,
    FormInfo,
    FormsResult,
    HeadersResult,
    LinkInfo,
    LinksResult,
    MetadataResult,
    ProfileInfo,
    RobotsResult,
    ScrapeResult,
    SitemapResult,
    TableResult,
)

# ---------------------------------------------------------------------------
# FetchResult
# ---------------------------------------------------------------------------


class TestFetchResult:
    def test_required_fields(self) -> None:
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com/",
            status_code=200,
            ok=True,
            elapsed_ms=42.0,
            backend="httpx",
        )
        assert result.url == "https://example.com"
        assert result.final_url == "https://example.com/"
        assert result.status_code == 200
        assert result.ok is True
        assert result.elapsed_ms == 42.0
        assert result.backend == "httpx"

    def test_defaults(self) -> None:
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com/",
            status_code=200,
            ok=True,
            elapsed_ms=10.0,
            backend="httpx",
        )
        assert result.content_type is None
        assert result.headers == {}
        assert result.text is None

    def test_all_fields(self) -> None:
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com/",
            status_code=200,
            ok=True,
            content_type="text/html",
            headers={"content-type": "text/html"},
            text="<html>Hello</html>",
            elapsed_ms=42.0,
            backend="httpx",
        )
        assert result.content_type == "text/html"
        assert result.headers["content-type"] == "text/html"
        assert result.text == "<html>Hello</html>"

    def test_serialization(self) -> None:
        result = FetchResult(
            url="https://example.com",
            final_url="https://example.com/",
            status_code=200,
            ok=True,
            elapsed_ms=42.0,
            backend="httpx",
        )
        d = result.model_dump()
        assert d["url"] == "https://example.com"
        assert d["status_code"] == 200
        assert d["ok"] is True

        j = result.model_dump_json()
        parsed = json.loads(j)
        assert parsed["url"] == "https://example.com"
        assert parsed["backend"] == "httpx"


# ---------------------------------------------------------------------------
# ScrapeResult
# ---------------------------------------------------------------------------


class TestScrapeResult:
    def test_required_fields(self) -> None:
        result = ScrapeResult(
            url="https://example.com",
            selector="h1",
            count=2,
        )
        assert result.url == "https://example.com"
        assert result.selector == "h1"
        assert result.count == 2

    def test_defaults(self) -> None:
        result = ScrapeResult(url="https://example.com", selector="p", count=0)
        assert result.elements == []

    def test_with_elements(self) -> None:
        result = ScrapeResult(
            url="https://example.com",
            selector="p",
            elements=["Hello", "World"],
            count=2,
        )
        assert result.elements == ["Hello", "World"]

    def test_serialization(self) -> None:
        result = ScrapeResult(
            url="https://example.com",
            selector="h1",
            elements=["Title"],
            count=1,
        )
        d = result.model_dump()
        assert d["selector"] == "h1"
        assert d["elements"] == ["Title"]

        parsed = json.loads(result.model_dump_json())
        assert parsed["count"] == 1


# ---------------------------------------------------------------------------
# LinkInfo
# ---------------------------------------------------------------------------


class TestLinkInfo:
    def test_required_fields(self) -> None:
        info = LinkInfo(url="https://example.com", text="Example", is_external=False)
        assert info.url == "https://example.com"
        assert info.text == "Example"
        assert info.is_external is False

    def test_external_link(self) -> None:
        info = LinkInfo(url="https://other.com", text="Other", is_external=True)
        assert info.is_external is True

    def test_serialization(self) -> None:
        info = LinkInfo(url="https://example.com", text="Link", is_external=True)
        d = info.model_dump()
        assert d["url"] == "https://example.com"
        assert d["is_external"] is True

        parsed = json.loads(info.model_dump_json())
        assert parsed["text"] == "Link"


# ---------------------------------------------------------------------------
# LinksResult
# ---------------------------------------------------------------------------


class TestLinksResult:
    def test_required_fields(self) -> None:
        result = LinksResult(
            url="https://example.com",
            total=3,
            internal=2,
            external=1,
        )
        assert result.total == 3
        assert result.internal == 2
        assert result.external == 1

    def test_defaults(self) -> None:
        result = LinksResult(url="https://example.com", total=0, internal=0, external=0)
        assert result.links == []

    def test_with_links(self) -> None:
        links = [
            LinkInfo(url="/about", text="About", is_external=False),
            LinkInfo(url="https://other.com", text="Other", is_external=True),
        ]
        result = LinksResult(
            url="https://example.com",
            links=links,
            total=2,
            internal=1,
            external=1,
        )
        assert len(result.links) == 2
        assert result.links[0].url == "/about"

    def test_serialization(self) -> None:
        result = LinksResult(
            url="https://example.com",
            links=[LinkInfo(url="/a", text="A", is_external=False)],
            total=1,
            internal=1,
            external=0,
        )
        d = result.model_dump()
        assert len(d["links"]) == 1
        assert d["links"][0]["url"] == "/a"


# ---------------------------------------------------------------------------
# MetadataResult
# ---------------------------------------------------------------------------


class TestMetadataResult:
    def test_required_fields(self) -> None:
        result = MetadataResult(url="https://example.com")
        assert result.url == "https://example.com"

    def test_defaults(self) -> None:
        result = MetadataResult(url="https://example.com")
        assert result.title is None
        assert result.description is None
        assert result.canonical_url is None
        assert result.og_title is None
        assert result.og_description is None
        assert result.og_image is None
        assert result.og_type is None
        assert result.favicons == []

    def test_all_fields(self) -> None:
        result = MetadataResult(
            url="https://example.com",
            title="Example",
            description="A test page",
            canonical_url="https://example.com/canonical",
            og_title="OG Title",
            og_description="OG Desc",
            og_image="https://example.com/img.png",
            og_type="website",
            favicons=["https://example.com/favicon.ico"],
        )
        assert result.title == "Example"
        assert result.og_title == "OG Title"
        assert result.favicons == ["https://example.com/favicon.ico"]

    def test_serialization(self) -> None:
        result = MetadataResult(
            url="https://example.com",
            title="Test",
            og_type="article",
        )
        d = result.model_dump()
        assert d["title"] == "Test"
        assert d["og_type"] == "article"
        assert d["description"] is None

        parsed = json.loads(result.model_dump_json())
        assert parsed["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# FormInfo
# ---------------------------------------------------------------------------


class TestFormInfo:
    def test_required_fields(self) -> None:
        info = FormInfo(action="/submit", method="POST")
        assert info.action == "/submit"
        assert info.method == "POST"

    def test_defaults(self) -> None:
        info = FormInfo(action="/submit", method="GET")
        assert info.fields == {}

    def test_with_fields(self) -> None:
        info = FormInfo(
            action="/search",
            method="GET",
            fields={"q": "", "lang": "en"},
        )
        assert info.fields["lang"] == "en"

    def test_serialization(self) -> None:
        info = FormInfo(action="/login", method="POST", fields={"user": ""})
        d = info.model_dump()
        assert d["action"] == "/login"
        assert d["fields"]["user"] == ""


# ---------------------------------------------------------------------------
# FormsResult
# ---------------------------------------------------------------------------


class TestFormsResult:
    def test_required_fields(self) -> None:
        result = FormsResult(url="https://example.com", count=0)
        assert result.url == "https://example.com"
        assert result.count == 0

    def test_defaults(self) -> None:
        result = FormsResult(url="https://example.com", count=0)
        assert result.forms == []

    def test_with_forms(self) -> None:
        forms = [FormInfo(action="/search", method="GET")]
        result = FormsResult(url="https://example.com", forms=forms, count=1)
        assert len(result.forms) == 1
        assert result.forms[0].action == "/search"

    def test_serialization(self) -> None:
        result = FormsResult(
            url="https://example.com",
            forms=[FormInfo(action="/a", method="POST")],
            count=1,
        )
        parsed = json.loads(result.model_dump_json())
        assert parsed["count"] == 1
        assert parsed["forms"][0]["method"] == "POST"


# ---------------------------------------------------------------------------
# TableResult
# ---------------------------------------------------------------------------


class TestTableResult:
    def test_required_fields(self) -> None:
        result = TableResult(
            url="https://example.com",
            selector="table",
            row_count=0,
        )
        assert result.selector == "table"
        assert result.row_count == 0

    def test_defaults(self) -> None:
        result = TableResult(url="https://example.com", selector="table", row_count=0)
        assert result.rows == []

    def test_with_rows(self) -> None:
        result = TableResult(
            url="https://example.com",
            selector="table.data",
            rows=[["Name", "Age"], ["Alice", "30"]],
            row_count=2,
        )
        assert result.rows[0] == ["Name", "Age"]
        assert result.rows[1] == ["Alice", "30"]

    def test_serialization(self) -> None:
        result = TableResult(
            url="https://example.com",
            selector="table",
            rows=[["a", "b"]],
            row_count=1,
        )
        d = result.model_dump()
        assert d["rows"] == [["a", "b"]]


# ---------------------------------------------------------------------------
# RobotsResult
# ---------------------------------------------------------------------------


class TestRobotsResult:
    def test_required_fields(self) -> None:
        result = RobotsResult(
            url="https://example.com",
            path="/",
            user_agent="*",
            allowed=True,
        )
        assert result.allowed is True

    def test_defaults(self) -> None:
        result = RobotsResult(
            url="https://example.com",
            path="/",
            user_agent="*",
            allowed=True,
        )
        assert result.sitemaps == []

    def test_with_sitemaps(self) -> None:
        result = RobotsResult(
            url="https://example.com",
            path="/admin",
            user_agent="Googlebot",
            allowed=False,
            sitemaps=["https://example.com/sitemap.xml"],
        )
        assert result.allowed is False
        assert len(result.sitemaps) == 1

    def test_serialization(self) -> None:
        result = RobotsResult(
            url="https://example.com",
            path="/",
            user_agent="*",
            allowed=True,
            sitemaps=["https://example.com/sitemap.xml"],
        )
        parsed = json.loads(result.model_dump_json())
        assert parsed["allowed"] is True
        assert parsed["sitemaps"] == ["https://example.com/sitemap.xml"]


# ---------------------------------------------------------------------------
# SitemapResult
# ---------------------------------------------------------------------------


class TestSitemapResult:
    def test_required_fields(self) -> None:
        result = SitemapResult(
            url="https://example.com/sitemap.xml",
            count=0,
        )
        assert result.count == 0

    def test_defaults(self) -> None:
        result = SitemapResult(url="https://example.com/sitemap.xml", count=0)
        assert result.entries == []

    def test_with_entries(self) -> None:
        entries = [
            {
                "loc": "https://example.com/",
                "lastmod": "2024-01-01",
                "changefreq": "daily",
                "priority": "1.0",
            },
            {
                "loc": "https://example.com/about",
                "lastmod": None,
                "changefreq": None,
                "priority": None,
            },
        ]
        result = SitemapResult(
            url="https://example.com/sitemap.xml",
            entries=entries,
            count=2,
        )
        assert len(result.entries) == 2
        assert result.entries[0]["loc"] == "https://example.com/"

    def test_serialization(self) -> None:
        result = SitemapResult(
            url="https://example.com/sitemap.xml",
            entries=[
                {
                    "loc": "https://example.com/",
                    "lastmod": None,
                    "changefreq": None,
                    "priority": None,
                }
            ],
            count=1,
        )
        d = result.model_dump()
        assert d["count"] == 1
        assert d["entries"][0]["loc"] == "https://example.com/"


# ---------------------------------------------------------------------------
# HeadersResult
# ---------------------------------------------------------------------------


class TestHeadersResult:
    def test_required_fields(self) -> None:
        result = HeadersResult(profile="chrome_win")
        assert result.profile == "chrome_win"

    def test_defaults(self) -> None:
        result = HeadersResult(profile="chrome_win")
        assert result.headers == {}

    def test_with_headers(self) -> None:
        result = HeadersResult(
            profile="chrome_win",
            headers={"user-agent": "Mozilla/5.0", "accept": "text/html"},
        )
        assert "user-agent" in result.headers
        assert result.headers["accept"] == "text/html"

    def test_serialization(self) -> None:
        result = HeadersResult(
            profile="firefox_mac",
            headers={"user-agent": "Mozilla/5.0"},
        )
        parsed = json.loads(result.model_dump_json())
        assert parsed["profile"] == "firefox_mac"
        assert "user-agent" in parsed["headers"]


# ---------------------------------------------------------------------------
# ProfileInfo
# ---------------------------------------------------------------------------


class TestProfileInfo:
    def test_required_fields(self) -> None:
        info = ProfileInfo(
            name="chrome_win",
            browser="chrome",
            platform="Windows",
            mobile=False,
        )
        assert info.name == "chrome_win"
        assert info.browser == "chrome"
        assert info.platform == "Windows"
        assert info.mobile is False

    def test_mobile_profile(self) -> None:
        info = ProfileInfo(
            name="chrome_android",
            browser="chrome",
            platform="Android",
            mobile=True,
        )
        assert info.mobile is True

    def test_serialization(self) -> None:
        info = ProfileInfo(
            name="safari_mac",
            browser="safari",
            platform="macOS",
            mobile=False,
        )
        d = info.model_dump()
        assert d["name"] == "safari_mac"
        assert d["mobile"] is False

        parsed = json.loads(info.model_dump_json())
        assert parsed["browser"] == "safari"


# ---------------------------------------------------------------------------
# ArticleResult
# ---------------------------------------------------------------------------


class TestArticleResult:
    def test_required_fields(self) -> None:
        result = ArticleResult(url="https://example.com/article")
        assert result.url == "https://example.com/article"

    def test_defaults(self) -> None:
        result = ArticleResult(url="https://example.com/article")
        assert result.text is None
        assert result.markdown is None
        assert result.title is None

    def test_all_fields(self) -> None:
        result = ArticleResult(
            url="https://example.com/article",
            text="Article text here.",
            markdown="# Article\n\nText here.",
            title="My Article",
        )
        assert result.text == "Article text here."
        assert result.markdown == "# Article\n\nText here."
        assert result.title == "My Article"

    def test_serialization(self) -> None:
        result = ArticleResult(
            url="https://example.com/article",
            text="Hello",
            title="Title",
        )
        d = result.model_dump()
        assert d["text"] == "Hello"
        assert d["title"] == "Title"
        assert d["markdown"] is None

        parsed = json.loads(result.model_dump_json())
        assert parsed["url"] == "https://example.com/article"


# ---------------------------------------------------------------------------
# DownloadResult
# ---------------------------------------------------------------------------


class TestDownloadResult:
    def test_required_fields(self) -> None:
        result = DownloadResult(
            url="https://example.com/file.zip",
            path="/tmp/file.zip",
            size_bytes=1024,
        )
        assert result.url == "https://example.com/file.zip"
        assert result.path == "/tmp/file.zip"
        assert result.size_bytes == 1024

    def test_defaults(self) -> None:
        result = DownloadResult(
            url="https://example.com/file.zip",
            path="/tmp/file.zip",
            size_bytes=0,
        )
        assert result.checksum_sha256 is None

    def test_with_checksum(self) -> None:
        result = DownloadResult(
            url="https://example.com/file.zip",
            path="/tmp/file.zip",
            size_bytes=2048,
            checksum_sha256="abc123def456",
        )
        assert result.checksum_sha256 == "abc123def456"

    def test_serialization(self) -> None:
        result = DownloadResult(
            url="https://example.com/file.zip",
            path="/tmp/file.zip",
            size_bytes=512,
            checksum_sha256="deadbeef",
        )
        d = result.model_dump()
        assert d["size_bytes"] == 512
        assert d["checksum_sha256"] == "deadbeef"

        parsed = json.loads(result.model_dump_json())
        assert parsed["path"] == "/tmp/file.zip"
