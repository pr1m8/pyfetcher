"""Spider and router for :mod:`pyfetcher.crawler`.

Purpose:
    Provide a base spider class with URL pattern routing for handling
    different page types during crawling.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from pyfetcher.contracts.response import FetchResponse


@dataclass
class SpiderResult:
    """Result of processing a crawled page.

    Args:
        discovered_urls: New URLs found on the page.
        items: Extracted structured data items.
        media_urls: Media URLs found for downloading.
    """

    discovered_urls: list[str] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)
    media_urls: list[str] = field(default_factory=list)


HandlerFunc = Callable[[str, FetchResponse], Coroutine[Any, Any, SpiderResult]]


class Router:
    """URL pattern router for spider handlers.

    Maps URL regex patterns to async handler functions. The first
    matching pattern wins.
    """

    def __init__(self) -> None:
        self._routes: list[tuple[re.Pattern[str], HandlerFunc]] = []
        self._default: HandlerFunc | None = None

    def add(self, pattern: str, handler: HandlerFunc) -> None:
        """Register a handler for a URL pattern.

        Args:
            pattern: Regex pattern to match URLs against.
            handler: Async function handling matching URLs.
        """
        self._routes.append((re.compile(pattern), handler))

    def default(self, handler: HandlerFunc) -> None:
        """Set the default handler for unmatched URLs.

        Args:
            handler: Async function for URLs matching no pattern.
        """
        self._default = handler

    def resolve(self, url: str) -> HandlerFunc | None:
        """Find the handler for a URL.

        Args:
            url: The URL to route.

        Returns:
            The matching handler, or the default handler, or ``None``.
        """
        for pattern, handler in self._routes:
            if pattern.search(url):
                return handler
        return self._default


class Spider:
    """Base spider with URL routing.

    Provides a router for dispatching URLs to handler functions
    that extract data and discover new URLs.

    Args:
        name: Spider name for logging/identification.
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.router = Router()

    async def handle(self, url: str, response: FetchResponse) -> SpiderResult:
        """Route a URL to its handler and return the result.

        Args:
            url: The crawled URL.
            response: The fetch response.

        Returns:
            A :class:`SpiderResult` with discovered URLs and items.
        """
        handler = self.router.resolve(url)
        if handler is None:
            return SpiderResult()
        return await handler(url, response)
