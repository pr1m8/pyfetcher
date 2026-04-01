"""Browser profile definitions for :mod:`pyfetcher`.

Purpose:
    Define complete browser identity profiles that bundle User-Agent strings
    with matching Client Hints (Sec-CH-UA-*), Sec-Fetch-* metadata, and Accept
    headers into coherent, realistic browser identities. Profiles ensure that
    all identity-related headers are internally consistent, which is critical
    for avoiding detection by anti-bot systems.

Design:
    - Each profile represents a specific browser + version + platform combination.
    - Headers within a profile are guaranteed to be mutually consistent (e.g.
      a Chrome UA will have matching Sec-CH-UA and platform values).
    - Profiles are immutable dataclass instances for safety and hashability.
    - The ``get_profile`` function selects profiles by name; ``list_profiles``
      enumerates all available profile names.

Examples:
    ::

        >>> profile = get_profile("chrome_win")
        >>> "Chrome" in profile.user_agent
        True
        >>> profile.platform
        'Windows'
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BrowserProfile:
    """A complete browser identity profile.

    Bundles all headers that form a browser's identity fingerprint into
    a single coherent object. Anti-bot systems check for consistency
    across these headers, so they must all agree on browser type, version,
    and platform.

    Args:
        name: Unique profile identifier (e.g. ``'chrome_win'``).
        browser: Browser family name (e.g. ``'chrome'``, ``'firefox'``, ``'safari'``).
        platform: Operating system name (e.g. ``'Windows'``, ``'macOS'``, ``'Linux'``).
        mobile: Whether this is a mobile browser profile.
        user_agent: The User-Agent header string.
        sec_ch_ua: The ``Sec-CH-UA`` client hint header value.
        sec_ch_ua_full_version_list: The ``Sec-CH-UA-Full-Version-List`` header.
        sec_ch_ua_mobile: The ``Sec-CH-UA-Mobile`` header (``'?0'`` or ``'?1'``).
        sec_ch_ua_platform: The ``Sec-CH-UA-Platform`` header (quoted string).
        sec_ch_ua_platform_version: The ``Sec-CH-UA-Platform-Version`` header.
        sec_ch_ua_model: The ``Sec-CH-UA-Model`` header (empty for desktop).
        accept: The ``Accept`` header for document requests.
        accept_language_options: Pool of ``Accept-Language`` values for randomization.
        accept_encoding: The ``Accept-Encoding`` header value.
        sec_fetch_dest: Default ``Sec-Fetch-Dest`` value.
        sec_fetch_mode: Default ``Sec-Fetch-Mode`` value.
        sec_fetch_site: Default ``Sec-Fetch-Site`` value.
        sec_fetch_user: Default ``Sec-Fetch-User`` value.
        upgrade_insecure_requests: The ``Upgrade-Insecure-Requests`` header.
        extra_headers: Additional browser-specific headers.

    Examples:
        ::

            >>> profile = BrowserProfile(
            ...     name="test", browser="chrome", platform="Windows",
            ...     user_agent="Mozilla/5.0", sec_ch_ua='"Chrome";v="133"',
            ...     sec_ch_ua_full_version_list='"Chrome";v="133.0"',
            ...     sec_ch_ua_mobile="?0", sec_ch_ua_platform='"Windows"',
            ...     sec_ch_ua_platform_version='"10.0.0"',
            ... )
            >>> profile.browser
            'chrome'
    """

    name: str
    browser: str
    platform: str
    mobile: bool = False
    user_agent: str = ""
    sec_ch_ua: str = ""
    sec_ch_ua_full_version_list: str = ""
    sec_ch_ua_mobile: str = "?0"
    sec_ch_ua_platform: str = '""'
    sec_ch_ua_platform_version: str = '""'
    sec_ch_ua_model: str = '""'
    accept: str = (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    )
    accept_language_options: tuple[str, ...] = (
        "en-US,en;q=0.9",
        "en-US,en;q=0.8",
        "en-GB,en;q=0.9",
        "en-CA,en;q=0.9",
        "en-AU,en;q=0.9",
    )
    accept_encoding: str = "gzip, deflate, br, zstd"
    sec_fetch_dest: str = "document"
    sec_fetch_mode: str = "navigate"
    sec_fetch_site: str = "none"
    sec_fetch_user: str = "?1"
    upgrade_insecure_requests: str = "1"
    extra_headers: dict[str, str] = field(default_factory=dict)

    def to_headers(self) -> dict[str, str]:
        """Convert this profile to a complete headers dictionary.

        Returns a dictionary containing all identity-related headers
        appropriate for a top-level navigation request. The
        ``Accept-Encoding`` header is intentionally omitted because
        transport libraries (httpx, aiohttp) handle content negotiation
        and decompression automatically.

        Returns:
            A dictionary mapping header names to values.

        Examples:
            ::

                >>> profile = get_profile("chrome_win")
                >>> headers = profile.to_headers()
                >>> "user-agent" in headers
                True
        """
        headers: dict[str, str] = {
            "user-agent": self.user_agent,
            "accept": self.accept,
            "upgrade-insecure-requests": self.upgrade_insecure_requests,
            "sec-fetch-dest": self.sec_fetch_dest,
            "sec-fetch-mode": self.sec_fetch_mode,
            "sec-fetch-site": self.sec_fetch_site,
            "sec-fetch-user": self.sec_fetch_user,
        }
        if self.sec_ch_ua:
            headers["sec-ch-ua"] = self.sec_ch_ua
            headers["sec-ch-ua-mobile"] = self.sec_ch_ua_mobile
            headers["sec-ch-ua-platform"] = self.sec_ch_ua_platform
        if self.sec_ch_ua_full_version_list:
            headers["sec-ch-ua-full-version-list"] = self.sec_ch_ua_full_version_list
        if self.sec_ch_ua_platform_version:
            headers["sec-ch-ua-platform-version"] = self.sec_ch_ua_platform_version
        if self.sec_ch_ua_model:
            headers["sec-ch-ua-model"] = self.sec_ch_ua_model
        headers.update(self.extra_headers)
        return headers


# ---------------------------------------------------------------------------
# Chrome profiles
# ---------------------------------------------------------------------------

CHROME_WIN = BrowserProfile(
    name="chrome_win",
    browser="chrome",
    platform="Windows",
    user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    sec_ch_ua='"Google Chrome";v="133", "Chromium";v="133", "Not(A:Brand";v="99"',
    sec_ch_ua_full_version_list=(
        '"Google Chrome";v="133.0.6943.98", '
        '"Chromium";v="133.0.6943.98", '
        '"Not(A:Brand";v="99.0.0.0"'
    ),
    sec_ch_ua_mobile="?0",
    sec_ch_ua_platform='"Windows"',
    sec_ch_ua_platform_version='"10.0.0"',
    sec_ch_ua_model='""',
    extra_headers={"sec-ch-prefers-color-scheme": "light"},
)

CHROME_MAC = BrowserProfile(
    name="chrome_mac",
    browser="chrome",
    platform="macOS",
    user_agent=(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    sec_ch_ua='"Google Chrome";v="133", "Chromium";v="133", "Not(A:Brand";v="99"',
    sec_ch_ua_full_version_list=(
        '"Google Chrome";v="133.0.6943.98", '
        '"Chromium";v="133.0.6943.98", '
        '"Not(A:Brand";v="99.0.0.0"'
    ),
    sec_ch_ua_mobile="?0",
    sec_ch_ua_platform='"macOS"',
    sec_ch_ua_platform_version='"14.5.0"',
    sec_ch_ua_model='""',
    extra_headers={"sec-ch-prefers-color-scheme": "light"},
)

CHROME_LINUX = BrowserProfile(
    name="chrome_linux",
    browser="chrome",
    platform="Linux",
    user_agent=(
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    sec_ch_ua='"Google Chrome";v="133", "Chromium";v="133", "Not(A:Brand";v="99"',
    sec_ch_ua_full_version_list=(
        '"Google Chrome";v="133.0.6943.98", '
        '"Chromium";v="133.0.6943.98", '
        '"Not(A:Brand";v="99.0.0.0"'
    ),
    sec_ch_ua_mobile="?0",
    sec_ch_ua_platform='"Linux"',
    sec_ch_ua_platform_version='"6.5.0"',
    sec_ch_ua_model='""',
    extra_headers={"sec-ch-prefers-color-scheme": "light"},
)

CHROME_ANDROID = BrowserProfile(
    name="chrome_android",
    browser="chrome",
    platform="Android",
    mobile=True,
    user_agent=(
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.6943.98 Mobile Safari/537.36"
    ),
    sec_ch_ua='"Google Chrome";v="133", "Chromium";v="133", "Not(A:Brand";v="99"',
    sec_ch_ua_full_version_list=(
        '"Google Chrome";v="133.0.6943.98", '
        '"Chromium";v="133.0.6943.98", '
        '"Not(A:Brand";v="99.0.0.0"'
    ),
    sec_ch_ua_mobile="?1",
    sec_ch_ua_platform='"Android"',
    sec_ch_ua_platform_version='"14.0.0"',
    sec_ch_ua_model='"Pixel 8 Pro"',
)

# ---------------------------------------------------------------------------
# Firefox profiles
# ---------------------------------------------------------------------------

FIREFOX_WIN = BrowserProfile(
    name="firefox_win",
    browser="firefox",
    platform="Windows",
    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"),
    sec_ch_ua="",  # Firefox does not send Client Hints
    sec_ch_ua_full_version_list="",
    sec_ch_ua_mobile="",
    sec_ch_ua_platform="",
    sec_ch_ua_platform_version="",
    sec_ch_ua_model="",
    accept=(
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
    ),
    accept_language_options=(
        "en-US,en;q=0.5",
        "en-GB,en;q=0.5",
        "en-CA,en;q=0.5",
    ),
    extra_headers={"dnt": "1", "priority": "u=0, i"},
)

FIREFOX_MAC = BrowserProfile(
    name="firefox_mac",
    browser="firefox",
    platform="macOS",
    user_agent=(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0"
    ),
    sec_ch_ua="",
    sec_ch_ua_full_version_list="",
    sec_ch_ua_mobile="",
    sec_ch_ua_platform="",
    sec_ch_ua_platform_version="",
    sec_ch_ua_model="",
    accept=(
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
    ),
    accept_language_options=(
        "en-US,en;q=0.5",
        "en-GB,en;q=0.5",
        "en-CA,en;q=0.5",
    ),
    extra_headers={"dnt": "1", "priority": "u=0, i"},
)

FIREFOX_LINUX = BrowserProfile(
    name="firefox_linux",
    browser="firefox",
    platform="Linux",
    user_agent=("Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"),
    sec_ch_ua="",
    sec_ch_ua_full_version_list="",
    sec_ch_ua_mobile="",
    sec_ch_ua_platform="",
    sec_ch_ua_platform_version="",
    sec_ch_ua_model="",
    accept=(
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
    ),
    accept_language_options=(
        "en-US,en;q=0.5",
        "en-GB,en;q=0.5",
    ),
    extra_headers={"dnt": "1", "priority": "u=0, i"},
)

# ---------------------------------------------------------------------------
# Safari profiles
# ---------------------------------------------------------------------------

SAFARI_MAC = BrowserProfile(
    name="safari_mac",
    browser="safari",
    platform="macOS",
    user_agent=(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.6 Safari/605.1.15"
    ),
    sec_ch_ua="",  # Safari does not send Client Hints
    sec_ch_ua_full_version_list="",
    sec_ch_ua_mobile="",
    sec_ch_ua_platform="",
    sec_ch_ua_platform_version="",
    sec_ch_ua_model="",
    accept=("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    accept_language_options=(
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
    ),
    accept_encoding="gzip, deflate, br",
)

SAFARI_IOS = BrowserProfile(
    name="safari_ios",
    browser="safari",
    platform="iOS",
    mobile=True,
    user_agent=(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.6 Mobile/15E148 Safari/604.1"
    ),
    sec_ch_ua="",
    sec_ch_ua_full_version_list="",
    sec_ch_ua_mobile="",
    sec_ch_ua_platform="",
    sec_ch_ua_platform_version="",
    sec_ch_ua_model="",
    accept=("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    accept_language_options=(
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
    ),
    accept_encoding="gzip, deflate, br",
)

# ---------------------------------------------------------------------------
# Edge profiles
# ---------------------------------------------------------------------------

EDGE_WIN = BrowserProfile(
    name="edge_win",
    browser="edge",
    platform="Windows",
    user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
    ),
    sec_ch_ua=('"Microsoft Edge";v="133", "Chromium";v="133", "Not(A:Brand";v="99"'),
    sec_ch_ua_full_version_list=(
        '"Microsoft Edge";v="133.0.3065.69", '
        '"Chromium";v="133.0.6943.98", '
        '"Not(A:Brand";v="99.0.0.0"'
    ),
    sec_ch_ua_mobile="?0",
    sec_ch_ua_platform='"Windows"',
    sec_ch_ua_platform_version='"10.0.0"',
    sec_ch_ua_model='""',
)

EDGE_MAC = BrowserProfile(
    name="edge_mac",
    browser="edge",
    platform="macOS",
    user_agent=(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
    ),
    sec_ch_ua=('"Microsoft Edge";v="133", "Chromium";v="133", "Not(A:Brand";v="99"'),
    sec_ch_ua_full_version_list=(
        '"Microsoft Edge";v="133.0.3065.69", '
        '"Chromium";v="133.0.6943.98", '
        '"Not(A:Brand";v="99.0.0.0"'
    ),
    sec_ch_ua_mobile="?0",
    sec_ch_ua_platform='"macOS"',
    sec_ch_ua_platform_version='"14.5.0"',
    sec_ch_ua_model='""',
)

# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------

_PROFILES: dict[str, BrowserProfile] = {
    p.name: p
    for p in [
        CHROME_WIN,
        CHROME_MAC,
        CHROME_LINUX,
        CHROME_ANDROID,
        FIREFOX_WIN,
        FIREFOX_MAC,
        FIREFOX_LINUX,
        SAFARI_MAC,
        SAFARI_IOS,
        EDGE_WIN,
        EDGE_MAC,
    ]
}

# Weighted by approximate real-world browser market share.
# Chrome ~65%, Firefox ~18%, Safari ~12%, Edge ~5%.
DESKTOP_PROFILES: list[BrowserProfile] = [
    CHROME_WIN,
    CHROME_MAC,
    CHROME_LINUX,
    FIREFOX_WIN,
    FIREFOX_MAC,
    FIREFOX_LINUX,
    SAFARI_MAC,
    EDGE_WIN,
    EDGE_MAC,
]

MOBILE_PROFILES: list[BrowserProfile] = [
    CHROME_ANDROID,
    SAFARI_IOS,
]

PROFILE_WEIGHTS: dict[str, float] = {
    "chrome_win": 0.30,
    "chrome_mac": 0.20,
    "chrome_linux": 0.15,
    "chrome_android": 0.10,
    "firefox_win": 0.07,
    "firefox_mac": 0.05,
    "firefox_linux": 0.03,
    "safari_mac": 0.05,
    "safari_ios": 0.02,
    "edge_win": 0.02,
    "edge_mac": 0.01,
}


def get_profile(name: str) -> BrowserProfile:
    """Get a browser profile by name.

    Args:
        name: Profile name (e.g. ``'chrome_win'``, ``'firefox_mac'``).

    Returns:
        The matching :class:`BrowserProfile` instance.

    Raises:
        KeyError: If no profile matches the given name.

    Examples:
        ::

            >>> get_profile("chrome_win").browser
            'chrome'
    """
    return _PROFILES[name]


def list_profiles() -> list[str]:
    """List all available profile names.

    Returns:
        A sorted list of registered profile name strings.

    Examples:
        ::

            >>> "chrome_win" in list_profiles()
            True
    """
    return sorted(_PROFILES.keys())
