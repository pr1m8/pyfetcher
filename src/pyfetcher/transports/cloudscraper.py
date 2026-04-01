"""Cloudscraper transport implementation for :mod:`pyfetcher`.

Purpose:
    Provide synchronous fetching using ``cloudscraper`` as the underlying
    HTTP client library.  Cloudscraper automatically handles Cloudflare's
    anti-bot challenges (JavaScript challenges, CAPTCHAs, etc.), allowing
    transparent access to Cloudflare-protected sites.

Design:
    - ``cloudscraper`` is imported lazily so the package remains optional.
    - One transport instance owns a long-lived scraper session that is
      lazily created on first use.
    - Only synchronous fetch is supported because ``cloudscraper`` is
      built on top of :mod:`requests`, which is inherently synchronous.

Examples:
    ::

        >>> transport = CloudscraperTransport()
        >>> hasattr(transport, "fetch")
        True
"""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.contracts.response import FetchResponse

if TYPE_CHECKING:
    import cloudscraper


class CloudscraperTransport:
    """Synchronous cloudscraper transport for Cloudflare challenge bypass.

    Manages a long-lived :func:`cloudscraper.create_scraper` session that is
    lazily initialized on first use.  The *browser* parameter controls which
    browser profile cloudscraper uses for challenge solving.

    Args:
        browser: Browser profile identifier passed to
            :func:`cloudscraper.create_scraper`.  Defaults to ``"chrome"``.

    Note:
        This transport only supports synchronous fetch.  Cloudscraper is built
        on :mod:`requests` and does not provide an async API.

    Examples:
        ::

            >>> transport = CloudscraperTransport()
            >>> hasattr(transport, "fetch")
            True
    """

    def __init__(self, *, browser: str = "chrome") -> None:
        self._browser = browser
        self._scraper: cloudscraper.CloudScraper | None = None

    def _get_scraper(self) -> cloudscraper.CloudScraper:
        """Get or lazily create the cloudscraper session.

        Returns:
            A configured :class:`cloudscraper.CloudScraper` instance.
        """
        if self._scraper is None:
            import cloudscraper as _cloudscraper  # noqa: PLC0415

            self._scraper = _cloudscraper.create_scraper(
                browser={"browser": self._browser, "mobile": False},
            )
        return self._scraper

    def fetch(self, request: FetchRequest) -> FetchResponse:
        """Fetch a request synchronously using cloudscraper.

        Automatically handles Cloudflare anti-bot challenges, retrying
        internally when a challenge page is encountered.

        Args:
            request: The fetch request to execute.

        Returns:
            A normalized :class:`~pyfetcher.contracts.response.FetchResponse`.

        Raises:
            cloudscraper.exceptions.CloudflareChallengeError:
                If the Cloudflare challenge cannot be solved.
            requests.exceptions.HTTPError:
                If the response status indicates an error.
        """
        scraper = self._get_scraper()
        start = perf_counter()
        response = scraper.request(
            request.method,
            request.url.unicode_string(),
            params=request.params or None,
            headers=request.headers or None,
            data=request.data,
            json=request.json_data,
            allow_redirects=request.allow_redirects,
            verify=request.verify_ssl,
            timeout=request.timeout.total_seconds,
        )
        elapsed_ms = (perf_counter() - start) * 1000.0
        response.raise_for_status()
        return FetchResponse(
            request_url=request.url.unicode_string(),
            final_url=str(response.url),
            status_code=response.status_code,
            headers=dict(response.headers),
            content_type=response.headers.get("content-type"),
            text=response.text,
            body=response.content,
            backend="cloudscraper",
            elapsed_ms=elapsed_ms,
        )

    def close(self) -> None:
        """Close the owned scraper session if present.

        Releases resources held by the underlying :mod:`requests` session.
        """
        if self._scraper is not None:
            self._scraper.close()
            self._scraper = None
