"""Unit tests for pyfetcher.scrape."""

from __future__ import annotations

from pyfetcher.scrape.content import extract_readable_text
from pyfetcher.scrape.forms import extract_forms
from pyfetcher.scrape.links import extract_links
from pyfetcher.scrape.robots import is_allowed, parse_robots_txt
from pyfetcher.scrape.selectors import (
    extract_attrs,
    extract_table,
    extract_text,
    select,
    select_one,
)
from pyfetcher.scrape.sitemap import parse_sitemap


class TestSelectors:
    def test_select(self) -> None:
        html = "<ul><li>A</li><li>B</li></ul>"
        tags = select(html, "li")
        assert len(tags) == 2

    def test_select_one(self) -> None:
        html = "<h1>First</h1><h1>Second</h1>"
        tag = select_one(html, "h1")
        assert tag is not None
        assert tag.get_text() == "First"

    def test_select_one_not_found(self) -> None:
        html = "<p>Hello</p>"
        assert select_one(html, "h1") is None

    def test_extract_text(self) -> None:
        html = "<p>Hello</p><p>World</p>"
        texts = extract_text(html, "p")
        assert texts == ["Hello", "World"]

    def test_extract_text_strip(self) -> None:
        html = "<p>  Hello  </p>"
        assert extract_text(html, "p", strip=True) == ["Hello"]
        assert extract_text(html, "p", strip=False) == ["  Hello  "]

    def test_extract_attrs(self) -> None:
        html = '<a href="/about" class="link">About</a><a href="/home">Home</a>'
        attrs = extract_attrs(html, "a", attrs=["href"])
        assert attrs == [{"href": "/about"}, {"href": "/home"}]

    def test_extract_attrs_all(self) -> None:
        html = '<img src="pic.jpg" alt="Photo" />'
        attrs = extract_attrs(html, "img")
        assert len(attrs) == 1
        assert attrs[0]["src"] == "pic.jpg"
        assert attrs[0]["alt"] == "Photo"

    def test_extract_table(self) -> None:
        html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"
        rows = extract_table(html)
        assert rows == [["Name", "Age"], ["Alice", "30"]]

    def test_extract_table_no_headers(self) -> None:
        html = "<table><tr><td>Alice</td><td>30</td></tr></table>"
        rows = extract_table(html, include_headers=False)
        assert rows == [["Alice", "30"]]

    def test_extract_table_not_found(self) -> None:
        html = "<p>No table here</p>"
        assert extract_table(html) == []


class TestLinks:
    def test_extract_links(self) -> None:
        html = '<a href="https://example.com">Example</a>'
        links = extract_links(html, base_url="https://example.com")
        assert len(links) == 1
        assert links[0].url == "https://example.com"
        assert links[0].text == "Example"

    def test_relative_links(self) -> None:
        html = '<a href="/about">About</a>'
        links = extract_links(html, base_url="https://example.com")
        assert links[0].url == "https://example.com/about"

    def test_external_detection(self) -> None:
        html = '<a href="https://other.com">Other</a><a href="/local">Local</a>'
        links = extract_links(html, base_url="https://example.com")
        assert links[0].is_external is True
        assert links[1].is_external is False

    def test_same_domain_only(self) -> None:
        html = '<a href="https://other.com">Other</a><a href="/local">Local</a>'
        links = extract_links(html, base_url="https://example.com", same_domain_only=True)
        assert len(links) == 1
        assert links[0].url == "https://example.com/local"

    def test_fragments_excluded(self) -> None:
        html = '<a href="#section">Jump</a><a href="/page">Page</a>'
        links = extract_links(html, base_url="https://example.com")
        assert len(links) == 1

    def test_fragments_included(self) -> None:
        html = '<a href="#section">Jump</a>'
        links = extract_links(html, base_url="https://example.com", include_fragments=True)
        assert len(links) == 1

    def test_skip_javascript(self) -> None:
        html = '<a href="javascript:void(0)">Click</a>'
        links = extract_links(html, base_url="https://example.com")
        assert len(links) == 0

    def test_skip_mailto(self) -> None:
        html = '<a href="mailto:test@test.com">Email</a>'
        links = extract_links(html, base_url="https://example.com")
        assert len(links) == 0


class TestForms:
    def test_basic_form(self) -> None:
        html = '<form action="/search" method="GET"><input name="q" value="test" /></form>'
        forms = extract_forms(html, base_url="https://example.com")
        assert len(forms) == 1
        assert forms[0].action == "https://example.com/search"
        assert forms[0].method == "GET"

    def test_form_fields(self) -> None:
        html = """
        <form action="/submit" method="POST">
            <input type="text" name="username" value="" />
            <input type="hidden" name="token" value="abc123" />
        </form>
        """
        forms = extract_forms(html, base_url="https://example.com")
        assert len(forms[0].fields) == 2
        assert forms[0].fields[1].value == "abc123"
        assert forms[0].fields[1].type == "hidden"

    def test_form_select(self) -> None:
        html = """
        <form action="/filter">
            <select name="sort">
                <option value="a">A</option>
                <option value="b" selected>B</option>
            </select>
        </form>
        """
        forms = extract_forms(html, base_url="https://example.com")
        field = forms[0].fields[0]
        assert field.type == "select"
        assert field.value == "b"
        assert field.options == ["a", "b"]

    def test_form_textarea(self) -> None:
        html = '<form action="/note"><textarea name="body">Content here</textarea></form>'
        forms = extract_forms(html, base_url="https://example.com")
        assert forms[0].fields[0].type == "textarea"
        assert forms[0].fields[0].value == "Content here"

    def test_to_dict(self) -> None:
        html = """
        <form action="/search">
            <input name="q" value="hello" />
            <input name="lang" value="en" />
        </form>
        """
        forms = extract_forms(html, base_url="https://example.com")
        assert forms[0].to_dict() == {"q": "hello", "lang": "en"}

    def test_multiple_forms(self) -> None:
        html = """
        <form action="/a"><input name="x" /></form>
        <form action="/b" id="form2"><input name="y" /></form>
        """
        forms = extract_forms(html, base_url="https://example.com")
        assert len(forms) == 2
        assert forms[1].id == "form2"


class TestRobots:
    def test_basic_robots(self) -> None:
        txt = "User-agent: *\nDisallow: /admin\nAllow: /admin/public"
        rules = parse_robots_txt(txt)
        assert is_allowed(rules, "/") is True
        assert is_allowed(rules, "/admin") is False
        assert is_allowed(rules, "/admin/settings") is False
        assert is_allowed(rules, "/admin/public") is True

    def test_empty_robots(self) -> None:
        rules = parse_robots_txt("")
        assert is_allowed(rules, "/anything") is True

    def test_specific_user_agent(self) -> None:
        txt = "User-agent: Googlebot\nDisallow: /private\nUser-agent: *\nAllow: /"
        rules = parse_robots_txt(txt)
        assert is_allowed(rules, "/private", user_agent="Googlebot") is False
        assert is_allowed(rules, "/private", user_agent="*") is True

    def test_sitemaps(self) -> None:
        txt = "User-agent: *\nDisallow:\nSitemap: https://example.com/sitemap.xml"
        rules = parse_robots_txt(txt)
        assert len(rules.sitemaps) == 1
        assert rules.sitemaps[0] == "https://example.com/sitemap.xml"

    def test_crawl_delay(self) -> None:
        txt = "User-agent: *\nCrawl-delay: 5\nDisallow: /slow"
        rules = parse_robots_txt(txt)
        assert rules.crawl_delays.get("*") == 5.0

    def test_comments_ignored(self) -> None:
        txt = "# This is a comment\nUser-agent: *\nDisallow: /secret # inline comment"
        rules = parse_robots_txt(txt)
        assert is_allowed(rules, "/secret") is False


class TestSitemap:
    def test_basic_sitemap(self) -> None:
        xml = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/</loc></url>"
            "<url><loc>https://example.com/about</loc><priority>0.8</priority></url>"
            "</urlset>"
        )
        entries = parse_sitemap(xml)
        assert len(entries) == 2
        assert entries[0].loc == "https://example.com/"
        assert entries[1].priority == "0.8"
        assert entries[0].is_sitemap is False

    def test_sitemap_index(self) -> None:
        xml = (
            '<?xml version="1.0"?>'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>"
            "<sitemap><loc>https://example.com/sitemap2.xml</loc></sitemap>"
            "</sitemapindex>"
        )
        entries = parse_sitemap(xml)
        assert len(entries) == 2
        assert entries[0].is_sitemap is True

    def test_sitemap_with_metadata(self) -> None:
        xml = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url>"
            "<loc>https://example.com/</loc>"
            "<lastmod>2024-01-01</lastmod>"
            "<changefreq>daily</changefreq>"
            "<priority>1.0</priority>"
            "</url>"
            "</urlset>"
        )
        entries = parse_sitemap(xml)
        assert entries[0].lastmod == "2024-01-01"
        assert entries[0].changefreq == "daily"


class TestContent:
    def test_extract_readable_text(self) -> None:
        html = "<p>Hello World</p><script>var x=1;</script>"
        text = extract_readable_text(html)
        assert "Hello World" in text
        assert "var x" not in text

    def test_strip_nav_footer(self) -> None:
        html = "<nav>Menu</nav><main><p>Content</p></main><footer>Foot</footer>"
        text = extract_readable_text(html)
        assert "Content" in text
        assert "Menu" not in text
        assert "Foot" not in text

    def test_with_selector(self) -> None:
        html = "<div><p>Outside</p></div><article><p>Inside</p></article>"
        text = extract_readable_text(html, selector="article")
        assert "Inside" in text
        assert "Outside" not in text

    def test_whitespace_normalization(self) -> None:
        html = "<p>First</p>" + "<br/>" * 10 + "<p>Second</p>"
        text = extract_readable_text(html)
        assert "\n\n\n" not in text
