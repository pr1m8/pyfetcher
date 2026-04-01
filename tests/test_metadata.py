"""Unit tests for pyfetcher.metadata."""

from __future__ import annotations

from pyfetcher.metadata.html import extract_basic_html_metadata
from pyfetcher.metadata.opengraph import extract_open_graph_metadata


class TestBasicHTMLMetadata:
    def test_extract_title(self) -> None:
        html = "<html><head><title>My Title</title></head></html>"
        meta = extract_basic_html_metadata(html)
        assert meta.title == "My Title"

    def test_extract_description(self) -> None:
        html = '<html><head><meta name="description" content="My description" /></head></html>'
        meta = extract_basic_html_metadata(html)
        assert meta.description == "My description"

    def test_canonical_url(self) -> None:
        html = '<html><head><link rel="canonical" href="/canonical" /></head></html>'
        meta = extract_basic_html_metadata(html, base_url="https://example.com")
        assert meta.canonical_url == "https://example.com/canonical"

    def test_favicons(self) -> None:
        html = """
        <html><head>
            <link rel="icon" href="/favicon.ico" />
            <link rel="apple-touch-icon" href="/apple-icon.png" sizes="180x180" />
        </head></html>
        """
        meta = extract_basic_html_metadata(html, base_url="https://example.com")
        assert len(meta.favicons) == 2
        assert meta.favicons[0].rel == "icon"
        assert meta.favicons[1].sizes == "180x180"

    def test_empty_html(self) -> None:
        meta = extract_basic_html_metadata("")
        assert meta.title is None
        assert meta.description is None


class TestOpenGraphMetadata:
    def test_extract_og(self) -> None:
        html = """
        <html><head>
            <meta property="og:title" content="OG Title" />
            <meta property="og:description" content="OG Desc" />
            <meta property="og:image" content="https://example.com/og.png" />
            <meta property="og:type" content="website" />
        </head></html>
        """
        og = extract_open_graph_metadata(html)
        assert og is not None
        assert og.title == "OG Title"
        assert og.description == "OG Desc"
        assert og.image == "https://example.com/og.png"
        assert og.type == "website"

    def test_no_og_returns_none(self) -> None:
        html = "<html><head><title>No OG</title></head></html>"
        assert extract_open_graph_metadata(html) is None

    def test_partial_og(self) -> None:
        html = '<html><head><meta property="og:title" content="Just Title" /></head></html>'
        og = extract_open_graph_metadata(html)
        assert og is not None
        assert og.title == "Just Title"
        assert og.description is None
