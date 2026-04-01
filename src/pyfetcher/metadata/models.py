"""Metadata models for :mod:`pyfetcher`.

Purpose:
    Provide reusable Pydantic models for page-level metadata parsed from HTML,
    Open Graph tags, and structured metadata extraction.

Examples:
    ::

        >>> PageMetadata(title="Home").title
        'Home'
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FaviconLink(BaseModel):
    """Single favicon or related icon link.

    Represents a ``<link>`` element from an HTML document that references
    an icon resource (favicon, apple-touch-icon, mask-icon).

    Args:
        href: Resolved icon URL.
        rel: HTML ``rel`` attribute value (e.g. ``'icon'``).
        sizes: Optional HTML ``sizes`` attribute value (e.g. ``'32x32'``).
        mime_type: Optional content type (e.g. ``'image/png'``).

    Examples:
        ::

            >>> FaviconLink(href="https://example.com/favicon.ico", rel="icon").rel
            'icon'
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    href: str
    rel: str
    sizes: str | None = None
    mime_type: str | None = None


class OpenGraphMetadata(BaseModel):
    """Open Graph metadata model.

    Captures the most common Open Graph (``og:``) meta tag values from
    an HTML document.

    Args:
        title: ``og:title`` value.
        description: ``og:description`` value.
        image: ``og:image`` URL.
        site_name: ``og:site_name`` value.
        url: ``og:url`` canonical URL.
        type: ``og:type`` value (e.g. ``'website'``, ``'article'``).

    Examples:
        ::

            >>> OpenGraphMetadata(title="Example").title
            'Example'
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str | None = None
    description: str | None = None
    image: str | None = None
    site_name: str | None = None
    url: str | None = None
    type: str | None = None


class PageMetadata(BaseModel):
    """Combined page metadata model.

    Aggregates metadata from multiple sources (HTML tags, Open Graph,
    structured data) into a single unified model.

    Args:
        title: Best-effort page title from ``<title>`` or ``og:title``.
        description: Best-effort description from ``<meta>`` or ``og:description``.
        canonical_url: Canonical URL from ``<link rel="canonical">``.
        open_graph: Parsed Open Graph metadata, if present.
        favicons: Collected favicon/icon links.
        structured: Raw structured metadata payload from extruct.

    Examples:
        ::

            >>> PageMetadata(title="Home").title
            'Home'
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    open_graph: OpenGraphMetadata | None = None
    favicons: list[FaviconLink] = Field(default_factory=list)
    structured: dict[str, object] | None = None
