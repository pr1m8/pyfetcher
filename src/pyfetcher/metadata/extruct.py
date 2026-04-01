"""Structured metadata extraction for :mod:`pyfetcher`.

Purpose:
    Run :mod:`extruct` against HTML and combine it with lighter HTML/Open Graph
    parsing helpers for comprehensive metadata extraction.

Design:
    - ``extruct`` is imported lazily so users can keep it optional.
    - Relative URLs are resolved with ``w3lib.html.get_base_url``.
    - The output is normalized into :class:`~pyfetcher.metadata.models.PageMetadata`.

Examples:
    ::

        >>> html = "<html><head><title>Example</title></head></html>"
        >>> meta = extract_extruct_metadata(html, page_url="https://example.com")
        >>> meta.title
        'Example'
"""

from __future__ import annotations

from pyfetcher.metadata.html import extract_basic_html_metadata
from pyfetcher.metadata.models import PageMetadata
from pyfetcher.metadata.opengraph import extract_open_graph_metadata


def extract_extruct_metadata(html: str, *, page_url: str) -> PageMetadata:
    """Extract combined page metadata using ``extruct`` plus HTML fallbacks.

    Runs basic HTML metadata extraction and Open Graph parsing, then
    augments the result with structured data (JSON-LD, microdata,
    microformat, RDFa, Dublin Core, Open Graph) via ``extruct``.

    Args:
        html: Raw HTML string to parse.
        page_url: Page URL used as the base for resolving relative URLs.

    Returns:
        A :class:`~pyfetcher.metadata.models.PageMetadata` with all available
        metadata fields populated.

    Raises:
        ImportError: If ``extruct`` or ``w3lib`` is not installed.

    Examples:
        ::

            >>> meta = extract_extruct_metadata(
            ...     "<html><head><title>Example</title></head></html>",
            ...     page_url="https://example.com",
            ... )
            >>> meta.title
            'Example'
    """
    import extruct
    from w3lib.html import get_base_url

    base_url = get_base_url(html, page_url)
    basic = extract_basic_html_metadata(html, base_url=base_url)
    open_graph = extract_open_graph_metadata(html)
    structured = extruct.extract(
        html,
        base_url=base_url,
        syntaxes=["json-ld", "opengraph", "microdata", "microformat", "rdfa", "dublincore"],
    )

    return basic.model_copy(update={"open_graph": open_graph, "structured": structured})
