"""Shared resource models for :mod:`pyfetcher`.

Purpose:
    Provide lightweight reusable models for fetched pages and downloadable media
    that scraper and downloader layers can build on.

Design:
    - Resource models are intentionally generic.
    - They reference URLs through the shared :class:`~pyfetcher.contracts.url.URL`.
    - Scraper-specific models should extend or wrap these models rather than
      replacing them for common cases.

Examples:
    ::

        >>> page = WebPage(url="https://example.com", title="Home")
        >>> page.title
        'Home'
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pyfetcher.contracts.url import URL


class WebResource(BaseModel):
    """Generic web resource.

    Base model for any resource identified by a URL with an optional
    MIME type. Scraper and downloader models extend this to add
    domain-specific fields.

    Args:
        url: Resource URL (string or :class:`~pyfetcher.contracts.url.URL`).
        mime_type: MIME type if known (e.g. ``'text/html'``).

    Examples:
        ::

            >>> WebResource(url="https://example.com/image.png").url.host
            'example.com'
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: URL
    mime_type: str | None = None


class WebPage(WebResource):
    """Generic fetched web page.

    Extends :class:`WebResource` with optional title and description
    fields suitable for representing a fetched HTML page.

    Args:
        url: Page URL.
        mime_type: MIME type if known.
        title: Best-effort page title extracted from HTML.
        description: Best-effort page description.

    Examples:
        ::

            >>> WebPage(url="https://example.com", title="Home").title
            'Home'
    """

    title: str | None = None
    description: str | None = None


class MediaResource(WebResource):
    """Generic downloadable media resource.

    Extends :class:`WebResource` with filename and content length fields
    suitable for representing a downloadable binary resource.

    Args:
        url: Resource URL.
        mime_type: MIME type if known.
        filename: Best-effort filename derived from URL or headers.
        content_length: Content length in bytes if known.

    Examples:
        ::

            >>> MediaResource(url="https://example.com/file.mp4", filename="file.mp4").filename
            'file.mp4'
    """

    filename: str | None = None
    content_length: int | None = None
