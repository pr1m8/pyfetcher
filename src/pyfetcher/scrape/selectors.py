"""CSS selector-based extraction for :mod:`pyfetcher`.

Purpose:
    Provide ergonomic functions for extracting data from HTML using CSS
    selectors via BeautifulSoup. Covers common patterns: selecting elements,
    extracting text, extracting attributes, and parsing HTML tables.

Examples:
    ::

        >>> html = "<div class='item'>Hello</div><div class='item'>World</div>"
        >>> extract_text(html, ".item")
        ['Hello', 'World']
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup, Tag


def select(html: str, selector: str) -> list[Tag]:
    """Select all elements matching a CSS selector.

    Args:
        html: Raw HTML string to parse.
        selector: CSS selector string.

    Returns:
        A list of matching :class:`bs4.Tag` objects.

    Examples:
        ::

            >>> html = "<ul><li>A</li><li>B</li></ul>"
            >>> tags = select(html, "li")
            >>> len(tags)
            2
    """
    soup = BeautifulSoup(html, "html.parser")
    return soup.select(selector)


def select_one(html: str, selector: str) -> Tag | None:
    """Select the first element matching a CSS selector.

    Args:
        html: Raw HTML string to parse.
        selector: CSS selector string.

    Returns:
        The first matching :class:`bs4.Tag`, or ``None`` if not found.

    Examples:
        ::

            >>> html = "<h1>Title</h1><h1>Subtitle</h1>"
            >>> tag = select_one(html, "h1")
            >>> tag.get_text()
            'Title'
    """
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one(selector)


def extract_text(html: str, selector: str, *, strip: bool = True) -> list[str]:
    """Extract text content from all elements matching a CSS selector.

    Args:
        html: Raw HTML string to parse.
        selector: CSS selector string.
        strip: Whether to strip whitespace from each text result.

    Returns:
        A list of text strings from matching elements.

    Examples:
        ::

            >>> html = "<p>Hello</p><p>World</p>"
            >>> extract_text(html, "p")
            ['Hello', 'World']
    """
    tags = select(html, selector)
    return [tag.get_text(strip=strip) for tag in tags]


def extract_attrs(
    html: str,
    selector: str,
    *,
    attrs: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Extract attributes from all elements matching a CSS selector.

    If ``attrs`` is not specified, all attributes of each element are returned.
    If ``attrs`` is a list of attribute names, only those attributes are
    included (with ``None`` for missing attributes).

    Args:
        html: Raw HTML string to parse.
        selector: CSS selector string.
        attrs: Optional list of attribute names to extract.

    Returns:
        A list of dictionaries mapping attribute names to values.

    Examples:
        ::

            >>> html = '<a href="/about">About</a><a href="/home">Home</a>'
            >>> extract_attrs(html, "a", attrs=["href"])
            [{'href': '/about'}, {'href': '/home'}]
    """
    tags = select(html, selector)
    results: list[dict[str, Any]] = []
    for tag in tags:
        if attrs is None:
            results.append(dict(tag.attrs))
        else:
            results.append({attr: tag.get(attr) for attr in attrs})
    return results


def extract_table(
    html: str,
    selector: str = "table",
    *,
    include_headers: bool = True,
) -> list[list[str]]:
    """Extract data from an HTML table as a list of rows.

    Parses the first ``<table>`` element matching the selector. If
    ``include_headers`` is ``True``, the first row will contain header
    cell (``<th>``) text. Subsequent rows contain data cell (``<td>``)
    text.

    Args:
        html: Raw HTML string to parse.
        selector: CSS selector targeting the table element.
        include_headers: Whether to include ``<th>`` cells as the first row.

    Returns:
        A list of rows, where each row is a list of cell text strings.

    Examples:
        ::

            >>> html = "<table><tr><th>Name</th></tr><tr><td>Alice</td></tr></table>"
            >>> extract_table(html)
            [['Name'], ['Alice']]
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(selector)
    if table is None:
        return []

    rows: list[list[str]] = []

    if include_headers:
        header_row = table.find("tr")
        if header_row and isinstance(header_row, Tag):
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
            if headers:
                rows.append(headers)

    for tr in table.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        cells = tr.find_all("td")
        if cells:
            rows.append([td.get_text(strip=True) for td in cells])

    return rows
