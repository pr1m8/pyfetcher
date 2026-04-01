"""Politeness enforcement for :mod:`pyfetcher.crawler`.

Purpose:
    Enforce per-host crawl delays using robots.txt directives and
    configurable minimum request intervals.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from urllib.parse import urlparse

from pyfetcher.scrape.robots import is_allowed, parse_robots_txt


class PolitenessEnforcer:
    """Enforces crawl politeness per-host.

    Checks robots.txt rules and enforces minimum delays between
    requests to the same host.

    Args:
        default_delay_seconds: Default delay when no crawl-delay directive exists.
    """

    def __init__(self, default_delay_seconds: float = 1.0) -> None:
        self._default_delay = default_delay_seconds
        self._last_fetch: dict[str, float] = {}

    def extract_hostname(self, url: str) -> str:
        """Extract hostname from a URL.

        Args:
            url: The URL.

        Returns:
            The hostname string.
        """
        return urlparse(url).netloc

    def check_robots(self, robots_txt: str | None, path: str, *, user_agent: str = "*") -> bool:
        """Check if a path is allowed by robots.txt.

        Args:
            robots_txt: Raw robots.txt content (None means allowed).
            path: The URL path to check.
            user_agent: User-agent string.

        Returns:
            ``True`` if allowed.
        """
        if robots_txt is None:
            return True
        rules = parse_robots_txt(robots_txt)
        return is_allowed(rules, path, user_agent=user_agent)

    def get_crawl_delay(self, robots_txt: str | None) -> float:
        """Get the crawl delay from robots.txt or use default.

        Args:
            robots_txt: Raw robots.txt content.

        Returns:
            Delay in seconds.
        """
        if robots_txt is None:
            return self._default_delay
        rules = parse_robots_txt(robots_txt)
        return rules.crawl_delays.get("*", self._default_delay)

    async def wait_for_host(self, hostname: str, delay_seconds: float) -> None:
        """Wait until it's safe to fetch from a host.

        Args:
            hostname: The target hostname.
            delay_seconds: Minimum delay between requests.
        """
        now = datetime.now(UTC).timestamp()
        last = self._last_fetch.get(hostname, 0.0)
        wait = delay_seconds - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_fetch[hostname] = datetime.now(UTC).timestamp()
