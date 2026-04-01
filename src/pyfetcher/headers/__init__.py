"""Header-provider strategies for :mod:`pyfetcher`.

Purpose:
    Provide strategy objects for generating realistic browser-like request
    headers independently of transport logic. Supports full browser profile
    generation with consistent User-Agent, Client Hints, Sec-Fetch-*, and
    Accept headers.

Public API:
    - :class:`~pyfetcher.headers.base.HeaderProvider`
    - :class:`~pyfetcher.headers.static.StaticHeaderProvider`
    - :class:`~pyfetcher.headers.browser.BrowserHeaderProvider`
    - :class:`~pyfetcher.headers.rotating.RotatingHeaderProvider`
    - :class:`~pyfetcher.headers.profiles.BrowserProfile`
    - :func:`~pyfetcher.headers.profiles.get_profile`
    - :func:`~pyfetcher.headers.ua.random_user_agent`
"""

from __future__ import annotations

from pyfetcher.headers.base import HeaderProvider
from pyfetcher.headers.browser import BrowserHeaderProvider, get_best_browser_headers
from pyfetcher.headers.profiles import BrowserProfile, get_profile, list_profiles
from pyfetcher.headers.rotating import RotatingHeaderProvider
from pyfetcher.headers.static import StaticHeaderProvider
from pyfetcher.headers.ua import random_user_agent

__all__ = [
    "BrowserHeaderProvider",
    "BrowserProfile",
    "HeaderProvider",
    "RotatingHeaderProvider",
    "StaticHeaderProvider",
    "get_best_browser_headers",
    "get_profile",
    "list_profiles",
    "random_user_agent",
]
