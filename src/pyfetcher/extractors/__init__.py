"""Content extraction utilities for :mod:`pyfetcher`.

Purpose:
    Provide advanced content extraction beyond basic HTML scraping:
    article text (trafilatura), readability fallback, HTML-to-markdown
    conversion, and media file metadata extraction.
"""

from __future__ import annotations

from pyfetcher.extraction import (
    CallableExtractor,
    ExtractionContext,
    ExtractionResult,
    Extractor,
    ExtractorRegistry,
    MediaFileExtractor,
    default_extractor_registry,
)
from pyfetcher.extractors.article import ArticleMeta, extract_article_metadata
from pyfetcher.extractors.content import extract_article_text
from pyfetcher.extractors.convert import html_to_markdown, html_to_plaintext
from pyfetcher.extractors.media_meta import (
    ainspect_media,
    extract_media_metadata,
    inspect_media,
)

__all__ = [
    "ArticleMeta",
    "CallableExtractor",
    "ExtractionContext",
    "ExtractionResult",
    "Extractor",
    "ExtractorRegistry",
    "MediaFileExtractor",
    "ainspect_media",
    "default_extractor_registry",
    "extract_article_metadata",
    "extract_article_text",
    "extract_media_metadata",
    "html_to_markdown",
    "html_to_plaintext",
    "inspect_media",
]
