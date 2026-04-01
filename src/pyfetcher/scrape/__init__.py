"""Web scraping utilities for :mod:`pyfetcher`.

Purpose:
    Provide CSS selector extraction, link harvesting, form parsing,
    robots.txt support, sitemap parsing, and content extraction tools.

Public API:
    - :func:`~pyfetcher.scrape.selectors.select`
    - :func:`~pyfetcher.scrape.selectors.select_one`
    - :func:`~pyfetcher.scrape.selectors.extract_text`
    - :func:`~pyfetcher.scrape.selectors.extract_attrs`
    - :func:`~pyfetcher.scrape.selectors.extract_table`
    - :func:`~pyfetcher.scrape.links.extract_links`
    - :func:`~pyfetcher.scrape.forms.extract_forms`
    - :func:`~pyfetcher.scrape.robots.parse_robots_txt`
    - :func:`~pyfetcher.scrape.robots.is_allowed`
    - :func:`~pyfetcher.scrape.sitemap.parse_sitemap`
    - :func:`~pyfetcher.scrape.content.extract_readable_text`
"""

from __future__ import annotations

from pyfetcher.scrape.content import extract_readable_text
from pyfetcher.scrape.forms import FormData, extract_forms
from pyfetcher.scrape.links import LinkInfo, extract_links
from pyfetcher.scrape.robots import RobotsRules, is_allowed, parse_robots_txt
from pyfetcher.scrape.selectors import (
    extract_attrs,
    extract_table,
    extract_text,
    select,
    select_one,
)
from pyfetcher.scrape.sitemap import SitemapEntry, parse_sitemap

__all__ = [
    "FormData",
    "LinkInfo",
    "RobotsRules",
    "SitemapEntry",
    "extract_attrs",
    "extract_forms",
    "extract_links",
    "extract_readable_text",
    "extract_table",
    "extract_text",
    "is_allowed",
    "parse_robots_txt",
    "parse_sitemap",
    "select",
    "select_one",
]
