"""Rotating header provider for :mod:`pyfetcher`.

Purpose:
    Provide a header provider that rotates through browser profiles to
    distribute requests across multiple browser identities, reducing the
    likelihood of fingerprint-based blocking.

Design:
    - Rotation happens at the session level: a profile is selected per
      call and all headers for that request are internally consistent.
    - Profile selection uses market-share weights by default but can be
      configured with an explicit profile list.
    - The provider maintains no mutable state beyond the configuration,
      so it is safe to share across threads/tasks.

Examples:
    ::

        >>> provider = RotatingHeaderProvider()
        >>> headers = provider.build(request=FetchRequest(url="https://example.com"))
        >>> "user-agent" in headers
        True
"""

from __future__ import annotations

import random

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.headers.profiles import (
    DESKTOP_PROFILES,
    PROFILE_WEIGHTS,
    BrowserProfile,
)


class RotatingHeaderProvider:
    """Header provider that rotates through browser profiles.

    Each call to :meth:`build` selects a random profile from the configured
    pool (weighted by market share) and returns a complete, internally
    consistent set of headers for that browser identity.

    Args:
        profiles: Optional list of profiles to rotate through. Defaults
            to all desktop profiles.
        weights: Optional list of weights for profile selection. Must have
            the same length as ``profiles``. Defaults to market-share weights.

    Examples:
        ::

            >>> provider = RotatingHeaderProvider()
            >>> headers = provider.build(request=FetchRequest(url="https://example.com"))
            >>> "user-agent" in headers
            True
    """

    def __init__(
        self,
        profiles: list[BrowserProfile] | None = None,
        weights: list[float] | None = None,
    ) -> None:
        self._profiles = profiles or list(DESKTOP_PROFILES)
        self._weights = weights or [PROFILE_WEIGHTS.get(p.name, 0.01) for p in self._profiles]

    @property
    def profiles(self) -> list[BrowserProfile]:
        """Return the configured profile pool.

        Returns:
            The list of profiles available for rotation.
        """
        return list(self._profiles)

    def _select_profile(self) -> BrowserProfile:
        """Select a random profile using configured weights.

        Returns:
            A randomly selected :class:`BrowserProfile`.
        """
        selected = random.choices(self._profiles, weights=self._weights, k=1)  # nosec B311
        return selected[0]

    def build(self, *, request: FetchRequest) -> dict[str, str]:
        """Build headers using a randomly selected browser profile.

        Selects a profile, generates its full header set with randomized
        variation, then merges per-request headers on top.

        Args:
            request: The fetch request for which to build headers.

        Returns:
            A complete headers dictionary from the selected profile.

        Examples:
            ::

                >>> provider = RotatingHeaderProvider()
                >>> headers = provider.build(request=FetchRequest(url="https://example.com"))
                >>> "accept" in headers
                True
        """
        profile = self._select_profile()
        headers = profile.to_headers()
        headers["accept-language"] = random.choice(
            profile.accept_language_options
        )  # noqa: S311  # nosec B311
        if profile.browser in ("chrome", "edge"):
            headers["sec-ch-prefers-color-scheme"] = random.choice(  # noqa: S311  # nosec B311
                ["light", "dark", "no-preference"]
            )
        headers.update(request.headers)
        return headers
