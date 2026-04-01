"""HTML conversion utilities for :mod:`pyfetcher.extractors`.

Purpose:
    Convert HTML to markdown or plaintext using html2text and markdownify.
"""

from __future__ import annotations


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown using markdownify.

    Args:
        html: Raw HTML string.

    Returns:
        Markdown-formatted text.
    """
    from markdownify import markdownify  # type: ignore[import-untyped]

    return markdownify(html, heading_style="ATX", strip=["script", "style"])


def html_to_plaintext(html: str) -> str:
    """Convert HTML to plaintext using html2text.

    Args:
        html: Raw HTML string.

    Returns:
        Plaintext with basic formatting preserved.
    """
    import html2text  # type: ignore[import-untyped]

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0
    return converter.handle(html)
