"""Article content extraction with fallback chain for :mod:`pyfetcher.extractors`.

Purpose:
    Extract readable article text from HTML using trafilatura as the
    primary extractor with readability-lxml as fallback.

Design:
    trafilatura achieves the highest F1 score (0.945) in benchmarks.
    readability-lxml has the highest median reliability (0.970).
    We try trafilatura first, fall back to readability on failure.
"""

from __future__ import annotations


def extract_article_text(html: str, *, url: str | None = None) -> str | None:
    """Extract the main article text from HTML.

    Uses trafilatura as the primary extractor with readability-lxml
    as fallback. Returns ``None`` if extraction fails entirely.

    Args:
        html: Raw HTML string.
        url: Optional page URL for better extraction context.

    Returns:
        Extracted article text, or ``None``.
    """
    text = _try_trafilatura(html, url=url)
    if text:
        return text
    return _try_readability(html, url=url)


def _try_trafilatura(html: str, *, url: str | None = None) -> str | None:
    """Attempt extraction with trafilatura."""
    try:
        import trafilatura  # type: ignore[import-untyped]

        return trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )
    except Exception:
        return None


def _try_readability(html: str, *, url: str | None = None) -> str | None:
    """Attempt extraction with readability-lxml."""
    try:
        from readability import Document  # type: ignore[import-untyped]

        doc = Document(html, url=url)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(doc.summary(), "html.parser")
        return soup.get_text(separator="\n", strip=True) or None
    except Exception:
        return None
