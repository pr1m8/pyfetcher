"""User-Agent generation utilities for :mod:`pyfetcher`.

Purpose:
    Provide functions for generating realistic User-Agent strings and
    selecting random profiles weighted by real-world browser market share.

Design:
    - User-Agent generation leverages the profile system for consistency.
    - Random selection uses market-share weights to produce realistic
      distributions of browser identities.
    - All randomization is done at the function call level, so each call
      may produce a different result.

Examples:
    ::

        >>> ua = random_user_agent()
        >>> "Mozilla" in ua
        True
"""

from __future__ import annotations

import random

from pyfetcher.headers.profiles import (
    _PROFILES,
    PROFILE_WEIGHTS,
    BrowserProfile,
)


def random_user_agent(
    *,
    browser: str | None = None,
    platform: str | None = None,
    mobile: bool | None = None,
) -> str:
    """Generate a random realistic User-Agent string.

    Optionally filter by browser family, platform, or mobile/desktop.
    When no filters are specified, profiles are selected using real-world
    market share weights.

    Args:
        browser: Filter to a specific browser family (e.g. ``'chrome'``,
            ``'firefox'``, ``'safari'``, ``'edge'``). Case-insensitive.
        platform: Filter to a specific platform (e.g. ``'Windows'``,
            ``'macOS'``, ``'Linux'``, ``'Android'``, ``'iOS'``).
            Case-insensitive.
        mobile: If ``True``, only mobile profiles. If ``False``, only
            desktop profiles. If ``None``, any profile.

    Returns:
        A realistic User-Agent string.

    Raises:
        ValueError: If no profiles match the given filters.

    Examples:
        ::

            >>> ua = random_user_agent(browser="chrome")
            >>> "Chrome" in ua
            True
            >>> ua = random_user_agent(mobile=True)
            >>> "Mobile" in ua or "iPhone" in ua
            True
    """
    profile = random_profile(browser=browser, platform=platform, mobile=mobile)
    return profile.user_agent


def random_profile(
    *,
    browser: str | None = None,
    platform: str | None = None,
    mobile: bool | None = None,
) -> BrowserProfile:
    """Select a random browser profile, optionally filtered.

    Profiles are selected using market-share weights when no filters are
    applied. When filters narrow the candidate set, weights are renormalized
    across matching profiles.

    Args:
        browser: Filter by browser family (case-insensitive).
        platform: Filter by platform name (case-insensitive).
        mobile: Filter by mobile/desktop.

    Returns:
        A randomly selected :class:`BrowserProfile`.

    Raises:
        ValueError: If no profiles match the given filters.

    Examples:
        ::

            >>> profile = random_profile(browser="firefox")
            >>> profile.browser
            'firefox'
    """
    candidates = list(_PROFILES.values())

    if browser is not None:
        browser_lower = browser.lower()
        candidates = [p for p in candidates if p.browser.lower() == browser_lower]

    if platform is not None:
        platform_lower = platform.lower()
        candidates = [p for p in candidates if p.platform.lower() == platform_lower]

    if mobile is not None:
        candidates = [p for p in candidates if p.mobile == mobile]

    if not candidates:
        raise ValueError(
            f"No profiles match filters: browser={browser!r}, "
            f"platform={platform!r}, mobile={mobile!r}"
        )

    weights = [PROFILE_WEIGHTS.get(p.name, 0.01) for p in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]  # noqa: S311  # nosec B311


def user_agents_for_browser(browser: str) -> list[str]:
    """Return all User-Agent strings for a given browser family.

    Args:
        browser: Browser family name (case-insensitive).

    Returns:
        A list of User-Agent strings.

    Examples:
        ::

            >>> uas = user_agents_for_browser("chrome")
            >>> all("Chrome" in ua for ua in uas)
            True
    """
    browser_lower = browser.lower()
    return [p.user_agent for p in _PROFILES.values() if p.browser.lower() == browser_lower]
