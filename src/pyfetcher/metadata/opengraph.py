"""Open Graph metadata extraction for :mod:`pyfetcher`.

Purpose:
    Extract common Open Graph fields from HTML ``<meta property="og:*">`` tags.

Examples:
    ::

        >>> html = "<meta property='og:title' content='Example' />"
        >>> extract_open_graph_metadata(html).title
        'Example'
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from pyfetcher.metadata.models import OpenGraphMetadata


def extract_open_graph_metadata(html: str) -> OpenGraphMetadata | None:
    """Extract Open Graph metadata from HTML.

    Parses ``og:title``, ``og:description``, ``og:image``, ``og:site_name``,
    ``og:url``, and ``og:type`` meta tags from the provided HTML. Returns
    ``None`` if no Open Graph fields are found.

    Args:
        html: Raw HTML string to parse.

    Returns:
        An :class:`~pyfetcher.metadata.models.OpenGraphMetadata` instance,
        or ``None`` if no OG fields exist.

    Examples:
        ::

            >>> html = "<html><head><meta property='og:title' content='Example' /></head></html>"
            >>> extract_open_graph_metadata(html).title
            'Example'
    """
    soup = BeautifulSoup(html, "html.parser")

    def _get(property_name: str) -> str | None:
        tag = soup.find("meta", attrs={"property": property_name})
        return tag.get("content", "").strip() if tag and tag.get("content") else None

    metadata = OpenGraphMetadata(
        title=_get("og:title"),
        description=_get("og:description"),
        image=_get("og:image"),
        site_name=_get("og:site_name"),
        url=_get("og:url"),
        type=_get("og:type"),
    )

    if not any(metadata.model_dump().values()):
        return None
    return metadata
