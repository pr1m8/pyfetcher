"""Tests for pyfetcher.extractors modules: content, convert, article, media_meta."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# content.py tests (extract_article_text)
# ---------------------------------------------------------------------------
from pyfetcher.extractors.content import extract_article_text


class TestExtractArticleText:
    def test_extract_article_text_returns_string(self):
        """When trafilatura succeeds, it should return a string."""
        with patch("pyfetcher.extractors.content._try_trafilatura", return_value="Hello world"):
            result = extract_article_text("<html><body>Hello world</body></html>")
            assert result == "Hello world"
            assert isinstance(result, str)

    def test_extract_article_text_fallback(self):
        """When trafilatura fails, readability should be tried."""
        with (
            patch("pyfetcher.extractors.content._try_trafilatura", return_value=None),
            patch(
                "pyfetcher.extractors.content._try_readability",
                return_value="Readability text",
            ),
        ):
            result = extract_article_text("<html><body>content</body></html>")
            assert result == "Readability text"

    def test_extract_article_text_both_fail(self):
        """When both extractors fail, None should be returned."""
        with (
            patch("pyfetcher.extractors.content._try_trafilatura", return_value=None),
            patch("pyfetcher.extractors.content._try_readability", return_value=None),
        ):
            result = extract_article_text("<html><body>content</body></html>")
            assert result is None

    def test_extract_article_text_empty_string_falls_back(self):
        """Empty string from trafilatura is falsy, should try readability."""
        with (
            patch("pyfetcher.extractors.content._try_trafilatura", return_value=""),
            patch(
                "pyfetcher.extractors.content._try_readability",
                return_value="Fallback text",
            ),
        ):
            result = extract_article_text("<html><body>content</body></html>")
            assert result == "Fallback text"

    def test_extract_article_text_passes_url_to_trafilatura(self):
        """URL kwarg should be forwarded to trafilatura."""
        with patch(
            "pyfetcher.extractors.content._try_trafilatura", return_value="text"
        ) as mock_traf:
            extract_article_text("<html></html>", url="https://example.com")
            mock_traf.assert_called_once_with("<html></html>", url="https://example.com")


# ---------------------------------------------------------------------------
# convert.py tests (html_to_markdown, html_to_plaintext)
# ---------------------------------------------------------------------------


class TestHtmlToMarkdown:
    def test_html_to_markdown(self):
        try:
            import markdownify as _  # noqa: F401
        except ImportError:
            pytest.skip("markdownify not installed")
        from pyfetcher.extractors.convert import html_to_markdown

        result = html_to_markdown("<h1>Hello</h1><p>World</p>")
        assert isinstance(result, str)
        assert "Hello" in result
        assert "World" in result

    def test_html_to_markdown_converts_headings(self):
        try:
            import markdownify as _  # noqa: F401
        except ImportError:
            pytest.skip("markdownify not installed")
        from pyfetcher.extractors.convert import html_to_markdown

        result = html_to_markdown("<h1>Title</h1><p>Content</p>")
        assert "# Title" in result
        assert "Content" in result


class TestHtmlToPlaintext:
    def test_html_to_plaintext(self):
        try:
            import html2text as _  # noqa: F401
        except ImportError:
            pytest.skip("html2text not installed")
        from pyfetcher.extractors.convert import html_to_plaintext

        result = html_to_plaintext("<h1>Hello</h1><p>World</p>")
        assert isinstance(result, str)
        assert "Hello" in result
        assert "World" in result

    def test_html_to_plaintext_preserves_links(self):
        try:
            import html2text as _  # noqa: F401
        except ImportError:
            pytest.skip("html2text not installed")
        from pyfetcher.extractors.convert import html_to_plaintext

        result = html_to_plaintext('<a href="https://example.com">Link</a>')
        assert "example.com" in result


# ---------------------------------------------------------------------------
# media_meta.py tests
# ---------------------------------------------------------------------------
from pyfetcher.extractors.media_meta import extract_media_metadata


class TestExtractMediaMetadata:
    def test_extract_media_metadata_unknown_extension(self):
        result = extract_media_metadata("/tmp/file.xyz")
        assert result["type"] == "unknown"
        assert result["extension"] == ".xyz"

    def test_extract_media_metadata_unknown_no_extension(self):
        result = extract_media_metadata("/tmp/noext")
        assert result["type"] == "unknown"
        assert result["extension"] == ""

    def test_extract_media_metadata_dispatches_audio(self):
        """Audio extensions should dispatch to _extract_audio."""
        with patch(
            "pyfetcher.extractors.media_meta._extract_audio", return_value={"type": "audio"}
        ) as mock_audio:
            result = extract_media_metadata("/tmp/song.mp3")
            mock_audio.assert_called_once()
            assert result["type"] == "audio"

    def test_extract_media_metadata_dispatches_video(self):
        """Video extensions should dispatch to _extract_video."""
        with patch(
            "pyfetcher.extractors.media_meta._extract_video", return_value={"type": "video"}
        ) as mock_video:
            result = extract_media_metadata("/tmp/movie.mp4")
            mock_video.assert_called_once()
            assert result["type"] == "video"

    def test_extract_media_metadata_dispatches_image(self):
        """Image extensions should dispatch to _extract_image."""
        with patch(
            "pyfetcher.extractors.media_meta._extract_image", return_value={"type": "image"}
        ) as mock_image:
            result = extract_media_metadata("/tmp/photo.jpg")
            mock_image.assert_called_once()
            assert result["type"] == "image"

    def test_extract_media_metadata_dispatches_pdf(self):
        """PDF extension should dispatch to _extract_pdf."""
        with patch(
            "pyfetcher.extractors.media_meta._extract_pdf", return_value={"type": "pdf"}
        ) as mock_pdf:
            result = extract_media_metadata("/tmp/doc.pdf")
            mock_pdf.assert_called_once()
            assert result["type"] == "pdf"


# ---------------------------------------------------------------------------
# article.py tests
# ---------------------------------------------------------------------------
from pyfetcher.extractors.article import ArticleMeta


class TestArticleMeta:
    def test_article_meta_defaults(self):
        meta = ArticleMeta()
        assert meta.title is None
        assert meta.authors == []
        assert meta.publish_date is None
        assert meta.summary is None
        assert meta.top_image is None
        assert meta.keywords == []

    def test_article_meta_custom_values(self):
        meta = ArticleMeta(
            title="Test Article",
            authors=["Author A", "Author B"],
            publish_date="2026-01-01",
            summary="A summary",
            top_image="https://example.com/img.jpg",
            keywords=["python", "testing"],
        )
        assert meta.title == "Test Article"
        assert len(meta.authors) == 2
        assert meta.publish_date == "2026-01-01"
        assert len(meta.keywords) == 2

    def test_article_meta_frozen(self):
        meta = ArticleMeta(title="Test")
        with pytest.raises(AttributeError):
            meta.title = "Changed"


# ---------------------------------------------------------------------------
# MediaInfo from extractors (media_meta does not define it, but we test structure)
# ---------------------------------------------------------------------------
class TestMediaInfoDataclass:
    """Test the MediaInfo type from the extractors perspective (via media_meta return)."""

    def test_media_meta_returns_dict(self):
        result = extract_media_metadata("/tmp/file.unknown_ext_123")
        assert isinstance(result, dict)
        assert "type" in result
