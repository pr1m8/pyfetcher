"""Content extraction for :mod:`pyfetcher`.

Purpose:
    Extract readable text content from HTML by stripping scripts, styles,
    and navigation elements to isolate the main body text.

Examples:
    ::

        >>> html = "<html><body><p>Hello World</p><script>var x=1;</script></body></html>"
        >>> extract_readable_text(html)
        'Hello World'
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

_STRIP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "nav",
        "footer",
        "header",
    }
)

_WHITESPACE_RE = re.compile(r"\n{3,}")


def extract_readable_text(
    html: str,
    *,
    strip_tags: frozenset[str] | None = None,
    selector: str | None = None,
) -> str:
    r"""Extract readable text content from HTML.

    Removes scripts, styles, navigation, and other non-content elements
    from the HTML, then extracts and normalizes the text content.
    Optionally targets a specific element via CSS selector.

    Args:
        html: Raw HTML string to process.
        strip_tags: Set of tag names to remove before text extraction.
            Defaults to scripts, styles, noscript, iframe, svg, nav,
            footer, and header.
        selector: Optional CSS selector to narrow extraction to a specific
            element (e.g. ``'article'``, ``'main'``, ``'.content'``).

    Returns:
        Cleaned, readable text with normalized whitespace.

    Examples:
        ::

            >>> html = "<div><p>First.</p><p>Second.</p><script>x=1</script></div>"
            >>> extract_readable_text(html)
            'First.\\nSecond.'
    """
    soup = BeautifulSoup(html, "html.parser")

    tags_to_strip = strip_tags or _STRIP_TAGS
    for tag in soup.find_all(tags_to_strip):
        tag.decompose()

    target = soup
    if selector:
        selected = soup.select_one(selector)
        if selected:
            target = selected

    text = target.get_text(separator="\n", strip=True)
    text = _WHITESPACE_RE.sub("\n\n", text)
    return text.strip()
