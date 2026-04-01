"""Metadata extraction helpers for :mod:`pyfetcher`.

Purpose:
    Parse and extract structured metadata from HTML documents including
    basic HTML metadata, Open Graph tags, and structured data (JSON-LD,
    microdata, etc.).

Public API:
    - :class:`~pyfetcher.metadata.models.PageMetadata`
    - :func:`~pyfetcher.metadata.html.extract_basic_html_metadata`
    - :func:`~pyfetcher.metadata.opengraph.extract_open_graph_metadata`
    - :func:`~pyfetcher.metadata.extruct.extract_extruct_metadata`
"""

from __future__ import annotations

from pyfetcher.metadata.extruct import extract_extruct_metadata
from pyfetcher.metadata.html import extract_basic_html_metadata
from pyfetcher.metadata.models import FaviconLink, OpenGraphMetadata, PageMetadata
from pyfetcher.metadata.opengraph import extract_open_graph_metadata

__all__ = [
    "FaviconLink",
    "OpenGraphMetadata",
    "PageMetadata",
    "extract_basic_html_metadata",
    "extract_extruct_metadata",
    "extract_open_graph_metadata",
]
