"""Unit tests for pyfetcher.headers."""

from __future__ import annotations

import pytest

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.headers.browser import BrowserHeaderProvider, get_best_browser_headers
from pyfetcher.headers.profiles import (
    CHROME_WIN,
    DESKTOP_PROFILES,
    MOBILE_PROFILES,
    BrowserProfile,
    get_profile,
    list_profiles,
)
from pyfetcher.headers.rotating import RotatingHeaderProvider
from pyfetcher.headers.static import StaticHeaderProvider
from pyfetcher.headers.ua import (
    random_profile,
    random_user_agent,
    user_agents_for_browser,
)


class TestBrowserProfile:
    def test_chrome_win_profile(self) -> None:
        profile = CHROME_WIN
        assert profile.browser == "chrome"
        assert profile.platform == "Windows"
        assert "Chrome" in profile.user_agent
        assert not profile.mobile

    def test_to_headers(self) -> None:
        headers = CHROME_WIN.to_headers()
        assert "user-agent" in headers
        assert "accept" in headers
        assert "sec-ch-ua" in headers
        assert "sec-fetch-dest" in headers
        assert headers["sec-fetch-dest"] == "document"

    def test_mobile_profile(self) -> None:
        profile = get_profile("chrome_android")
        assert profile.mobile is True
        assert profile.sec_ch_ua_mobile == "?1"

    def test_firefox_no_client_hints(self) -> None:
        profile = get_profile("firefox_win")
        headers = profile.to_headers()
        assert "sec-ch-ua" not in headers

    def test_safari_no_client_hints(self) -> None:
        profile = get_profile("safari_mac")
        headers = profile.to_headers()
        assert "sec-ch-ua" not in headers


class TestProfiles:
    def test_get_profile(self) -> None:
        profile = get_profile("chrome_win")
        assert profile.name == "chrome_win"

    def test_get_profile_invalid(self) -> None:
        with pytest.raises(KeyError):
            get_profile("nonexistent")

    def test_list_profiles(self) -> None:
        names = list_profiles()
        assert "chrome_win" in names
        assert "firefox_win" in names
        assert "safari_mac" in names
        assert len(names) >= 11

    def test_desktop_profiles(self) -> None:
        assert all(not p.mobile for p in DESKTOP_PROFILES)

    def test_mobile_profiles(self) -> None:
        assert all(p.mobile for p in MOBILE_PROFILES)


class TestGetBestBrowserHeaders:
    def test_chrome_headers(self) -> None:
        headers = get_best_browser_headers("chrome_win")
        assert "user-agent" in headers
        assert "accept-language" in headers
        assert "Chrome" in headers["user-agent"]

    def test_legacy_alias(self) -> None:
        headers = get_best_browser_headers("chrome")
        assert "Chrome" in headers["user-agent"]

    def test_firefox_headers(self) -> None:
        headers = get_best_browser_headers("firefox_win")
        assert "Firefox" in headers["user-agent"]

    def test_unknown_falls_back_to_chrome(self) -> None:
        headers = get_best_browser_headers("unknown_browser_xyz")
        assert "Chrome" in headers["user-agent"]


class TestBrowserHeaderProvider:
    def test_build(self) -> None:
        provider = BrowserHeaderProvider("chrome_win")
        request = FetchRequest(url="https://example.com")
        headers = provider.build(request=request)
        assert "user-agent" in headers
        assert "accept" in headers

    def test_request_headers_override(self) -> None:
        provider = BrowserHeaderProvider("chrome_win")
        request = FetchRequest(
            url="https://example.com",
            headers={"user-agent": "custom-ua"},
        )
        headers = provider.build(request=request)
        assert headers["user-agent"] == "custom-ua"

    def test_profile_property(self) -> None:
        provider = BrowserHeaderProvider("firefox_win")
        assert provider.profile.browser == "firefox"


class TestStaticHeaderProvider:
    def test_build(self) -> None:
        provider = StaticHeaderProvider({"x-test": "value"})
        request = FetchRequest(url="https://example.com")
        headers = provider.build(request=request)
        assert headers["x-test"] == "value"

    def test_returns_copy(self) -> None:
        original = {"x-test": "value"}
        provider = StaticHeaderProvider(original)
        request = FetchRequest(url="https://example.com")
        headers = provider.build(request=request)
        headers["x-test"] = "modified"
        assert provider.build(request=request)["x-test"] == "value"


class TestRotatingHeaderProvider:
    def test_build(self) -> None:
        provider = RotatingHeaderProvider()
        request = FetchRequest(url="https://example.com")
        headers = provider.build(request=request)
        assert "user-agent" in headers
        assert "accept" in headers

    def test_produces_different_profiles(self) -> None:
        provider = RotatingHeaderProvider()
        request = FetchRequest(url="https://example.com")
        user_agents = {provider.build(request=request)["user-agent"] for _ in range(50)}
        assert len(user_agents) > 1

    def test_custom_profiles(self) -> None:
        from pyfetcher.headers.profiles import CHROME_WIN, FIREFOX_WIN

        provider = RotatingHeaderProvider(profiles=[CHROME_WIN, FIREFOX_WIN])
        assert len(provider.profiles) == 2


class TestRandomUserAgent:
    def test_basic(self) -> None:
        ua = random_user_agent()
        assert "Mozilla" in ua

    def test_filter_browser(self) -> None:
        ua = random_user_agent(browser="chrome")
        assert "Chrome" in ua

    def test_filter_mobile(self) -> None:
        ua = random_user_agent(mobile=True)
        assert "Mobile" in ua or "iPhone" in ua

    def test_no_match_raises(self) -> None:
        with pytest.raises(ValueError, match="No profiles match"):
            random_user_agent(browser="nonexistent")


class TestRandomProfile:
    def test_basic(self) -> None:
        profile = random_profile()
        assert isinstance(profile, BrowserProfile)

    def test_filter_browser(self) -> None:
        profile = random_profile(browser="firefox")
        assert profile.browser == "firefox"

    def test_filter_platform(self) -> None:
        profile = random_profile(platform="macOS")
        assert profile.platform == "macOS"


class TestUserAgentsForBrowser:
    def test_chrome(self) -> None:
        uas = user_agents_for_browser("chrome")
        assert len(uas) >= 4
        assert all("Chrome" in ua for ua in uas)

    def test_firefox(self) -> None:
        uas = user_agents_for_browser("firefox")
        assert len(uas) >= 3
        assert all("Firefox" in ua for ua in uas)
