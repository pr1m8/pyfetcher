"""Browser-like header providers for :mod:`pyfetcher`.

Purpose:
    Provide header providers that generate realistic browser-like headers
    using the profile system. Supports both fixed-profile and randomized
    header generation with small per-request variations.

Design:
    - Browser profiles are sourced from :mod:`pyfetcher.headers.profiles`.
    - Small randomized fields (Accept-Language, color scheme preference)
      are applied at build time to add realistic variation.
    - Providers remain separate from transport and retry concerns.

Examples:
    ::

        >>> provider = BrowserHeaderProvider("chrome_win")
        >>> headers = provider.build(request=FetchRequest(url="https://example.com"))
        >>> "user-agent" in headers
        True
"""

from __future__ import annotations

import random

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.headers.profiles import (
    _PROFILES,
    CHROME_WIN,
    BrowserProfile,
    get_profile,
)


def _resolve_profile(impersonate: str) -> BrowserProfile:
    """Resolve a profile name or legacy alias to a BrowserProfile.

    Supports both the new profile names (e.g. ``'chrome_win'``) and
    legacy aliases (e.g. ``'chrome'``, ``'firefox'``) for backwards
    compatibility.

    Args:
        impersonate: Profile name or legacy alias.

    Returns:
        The resolved :class:`BrowserProfile`.
    """
    if impersonate in _PROFILES:
        return get_profile(impersonate)

    # Legacy alias mapping
    alias_map: dict[str, str] = {
        "chrome": "chrome_win",
        "chrome124": "chrome_win",
        "chrome131": "chrome_win",
        "chrome133": "chrome_win",
        "firefox": "firefox_win",
        "safari": "safari_mac",
        "edge": "edge_win",
    }
    resolved = alias_map.get(impersonate.lower())
    if resolved:
        return get_profile(resolved)

    return CHROME_WIN


def get_best_browser_headers(impersonate: str = "chrome_win") -> dict[str, str]:
    """Return browser-like headers with small randomized fields.

    Generates a complete set of browser headers from the named profile,
    then adds randomized ``Accept-Language`` and ``Sec-CH-Prefers-Color-Scheme``
    values for realistic per-request variation.

    Args:
        impersonate: Profile name or legacy alias.

    Returns:
        A browser-like headers dictionary suitable for HTTP requests.

    Examples:
        ::

            >>> headers = get_best_browser_headers("chrome_win")
            >>> "accept-language" in headers
            True
    """
    profile = _resolve_profile(impersonate)
    headers = profile.to_headers()
    headers["accept-language"] = random.choice(
        profile.accept_language_options
    )  # noqa: S311  # nosec B311
    if profile.browser in ("chrome", "edge"):
        headers["sec-ch-prefers-color-scheme"] = random.choice(  # noqa: S311  # nosec B311
            ["light", "dark", "no-preference"]
        )
    return headers


class BrowserHeaderProvider:
    """Provide browser-like headers for fetch requests.

    Wraps a browser profile and generates consistent, realistic headers
    for every request. Per-request headers from the
    :class:`~pyfetcher.contracts.request.FetchRequest` take precedence
    over profile headers when both are present.

    Args:
        impersonate: Profile name or legacy alias (default ``'chrome_win'``).

    Examples:
        ::

            >>> provider = BrowserHeaderProvider("chrome_win")
            >>> headers = provider.build(request=FetchRequest(url="https://example.com"))
            >>> "user-agent" in headers
            True
    """

    def __init__(self, impersonate: str = "chrome_win") -> None:
        self.impersonate = impersonate
        self._profile = _resolve_profile(impersonate)

    @property
    def profile(self) -> BrowserProfile:
        """Return the resolved browser profile.

        Returns:
            The :class:`BrowserProfile` used by this provider.
        """
        return self._profile

    def build(self, *, request: FetchRequest) -> dict[str, str]:
        """Build browser-like headers for the given request.

        Generates headers from the profile, adds randomized variation,
        then merges with any per-request headers (request headers win
        on conflict).

        Args:
            request: The fetch request for which to build headers.

        Returns:
            A complete headers dictionary.

        Examples:
            ::

                >>> provider = BrowserHeaderProvider()
                >>> headers = provider.build(request=FetchRequest(url="https://example.com"))
                >>> "accept" in headers
                True
        """
        headers = get_best_browser_headers(self.impersonate)
        headers.update(request.headers)
        return headers
