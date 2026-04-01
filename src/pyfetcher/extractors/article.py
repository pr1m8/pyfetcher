"""Article metadata extraction for :mod:`pyfetcher.extractors`.

Purpose:
    Extract article-specific metadata (author, publish date, summary)
    using newspaper3k for news articles.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ArticleMeta:
    """Extracted article metadata."""

    title: str | None = None
    authors: list[str] = field(default_factory=list)
    publish_date: str | None = None
    summary: str | None = None
    top_image: str | None = None
    keywords: list[str] = field(default_factory=list)


def extract_article_metadata(html: str, *, url: str) -> ArticleMeta:
    """Extract article metadata using newspaper3k.

    Args:
        html: Raw HTML string.
        url: The article URL (required by newspaper3k).

    Returns:
        An :class:`ArticleMeta` with extracted fields.
    """
    try:
        from newspaper import Article  # type: ignore[import-untyped]

        article = Article(url)
        article.set_html(html)
        article.parse()
        article.nlp()
        return ArticleMeta(
            title=article.title or None,
            authors=list(article.authors),
            publish_date=str(article.publish_date) if article.publish_date else None,
            summary=article.summary or None,
            top_image=article.top_image or None,
            keywords=list(article.keywords),
        )
    except Exception:
        return ArticleMeta()
