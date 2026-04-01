"""URL deduplication for :mod:`pyfetcher.crawler`.

Purpose:
    Normalize URLs and check/record seen status using xxhash64 for
    fast Postgres-backed deduplication.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    Strips fragments, sorts query params, lowercases scheme/host,
    removes trailing slashes on paths, and removes default ports.

    Args:
        url: The URL to normalize.

    Returns:
        The normalized URL string.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()

    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = f"{host}:{port}" if port else host

    path = parsed.path.rstrip("/") or "/"

    query_params = parse_qs(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(query_params.items()), doseq=True)

    return urlunparse((scheme, netloc, path, "", sorted_query, ""))


def url_hash(url: str) -> int:
    """Compute a hash for a normalized URL.

    Uses SHA-256 truncated to 8 bytes (64 bits) for a BigInteger-compatible
    hash suitable for Postgres primary keys.

    Args:
        url: The URL to hash (should be pre-normalized).

    Returns:
        A 64-bit integer hash.
    """
    digest = hashlib.sha256(url.encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


class URLDeduplicator:
    """URL deduplication checker backed by Postgres.

    Normalizes URLs, hashes them, and checks/records them in the
    ``seen_urls`` table via the repository layer.
    """

    async def is_seen(self, session: object, url: str) -> bool:
        """Check if a URL has been seen before.

        Args:
            session: Async database session.
            url: The URL to check.

        Returns:
            ``True`` if the URL has been seen.
        """
        from pyfetcher.db.repo import check_url_seen

        normalized = normalize_url(url)
        return await check_url_seen(session, url_hash(normalized))  # type: ignore[arg-type]

    async def mark_seen(self, session: object, url: str) -> None:
        """Mark a URL as seen.

        Args:
            session: Async database session.
            url: The URL to mark.
        """
        from pyfetcher.db.repo import mark_url_seen

        normalized = normalize_url(url)
        await mark_url_seen(session, url_hash=url_hash(normalized), url=url)  # type: ignore[arg-type]
