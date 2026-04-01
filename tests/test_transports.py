"""Unit tests for transport classes.

Tests helpers and constructor attributes for httpx, aiohttp, curl_cffi,
and cloudscraper transports.  Since curl_cffi and cloudscraper may not be
installed in the test environment, those tests are guarded with importorskip
or test only constructor-level attributes.
"""

from __future__ import annotations

import httpx

from pyfetcher.contracts.policy import PoolPolicy, TimeoutPolicy
from pyfetcher.contracts.request import FetchRequest
from pyfetcher.transports.httpx import HttpxTransport, _build_limits, _build_timeout

# ---------------------------------------------------------------------------
# httpx: _build_timeout
# ---------------------------------------------------------------------------


def test_build_timeout_defaults():
    policy = TimeoutPolicy()
    timeout = _build_timeout(policy)
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 10.0
    assert timeout.read == 30.0
    assert timeout.write == 30.0
    assert timeout.pool == 10.0


def test_build_timeout_custom():
    policy = TimeoutPolicy(
        total_seconds=60.0,
        connect_seconds=5.0,
        read_seconds=15.0,
        write_seconds=20.0,
        pool_seconds=8.0,
    )
    timeout = _build_timeout(policy)
    assert timeout.connect == 5.0
    assert timeout.read == 15.0
    assert timeout.write == 20.0
    assert timeout.pool == 8.0


# ---------------------------------------------------------------------------
# httpx: _build_limits
# ---------------------------------------------------------------------------


def test_build_limits_defaults():
    policy = PoolPolicy()
    limits = _build_limits(policy)
    assert isinstance(limits, httpx.Limits)
    assert limits.max_connections == 100
    assert limits.max_keepalive_connections == 20


def test_build_limits_custom():
    policy = PoolPolicy(
        max_connections=50,
        max_keepalive_connections=10,
        keepalive_expiry_seconds=30.0,
    )
    limits = _build_limits(policy)
    assert limits.max_connections == 50
    assert limits.max_keepalive_connections == 10


# ---------------------------------------------------------------------------
# HttpxTransport: constructor and lifecycle
# ---------------------------------------------------------------------------


def test_httpx_transport_default_constructor():
    transport = HttpxTransport()
    assert transport._sync_client is None
    assert transport._async_client is None
    assert transport._owns_sync_client is True
    assert transport._owns_async_client is True


def test_httpx_transport_external_client():
    sync_client = httpx.Client()
    async_client = httpx.AsyncClient()
    transport = HttpxTransport(sync_client=sync_client, async_client=async_client)
    assert transport._sync_client is sync_client
    assert transport._async_client is async_client
    assert transport._owns_sync_client is False
    assert transport._owns_async_client is False
    sync_client.close()


def test_httpx_transport_close():
    transport = HttpxTransport()
    # close() should be safe even when no client has been created.
    transport.close()
    assert transport._sync_client is None


async def test_httpx_transport_aclose():
    transport = HttpxTransport()
    # aclose() should be safe even when no async client has been created.
    await transport.aclose()
    assert transport._async_client is None


def test_httpx_transport_close_with_client():
    transport = HttpxTransport()
    # Force lazy client creation.
    request = FetchRequest(url="https://example.com")
    client = transport._get_sync_client(request)
    assert client is not None
    transport.close()
    assert transport._sync_client is None


async def test_httpx_transport_aclose_with_client():
    transport = HttpxTransport()
    request = FetchRequest(url="https://example.com")
    client = transport._get_async_client(request)
    assert client is not None
    await transport.aclose()
    assert transport._async_client is None


def test_httpx_transport_does_not_close_external_client():
    """External clients should NOT be closed by the transport."""
    sync_client = httpx.Client()
    transport = HttpxTransport(sync_client=sync_client)
    transport.close()
    # The external client should still be present (not closed by transport).
    assert not sync_client.is_closed
    sync_client.close()


# ---------------------------------------------------------------------------
# AiohttpTransport: constructor and helpers
# ---------------------------------------------------------------------------


def test_aiohttp_transport_constructor():
    from pyfetcher.transports.aiohttp import AiohttpTransport

    transport = AiohttpTransport()
    assert transport._session is None
    assert transport._owns_session is True


def test_aiohttp_transport_build_timeout():
    from pyfetcher.transports.aiohttp import AiohttpTransport

    transport = AiohttpTransport()
    request = FetchRequest(
        url="https://example.com",
        timeout=TimeoutPolicy(total_seconds=60.0, connect_seconds=5.0, read_seconds=15.0),
    )
    timeout = transport._build_timeout(request)
    assert timeout.total == 60.0
    assert timeout.connect == 5.0
    assert timeout.sock_read == 15.0


async def test_aiohttp_transport_build_connector():
    """Verify that _build_connector passes pool policy values to TCPConnector."""
    from pyfetcher.transports.aiohttp import AiohttpTransport

    transport = AiohttpTransport()
    request = FetchRequest(
        url="https://example.com",
        pool=PoolPolicy(max_connections=50, max_connections_per_host=5),
    )
    connector = transport._build_connector(request)
    assert connector._limit == 50
    assert connector._limit_per_host == 5
    await connector.close()


# ---------------------------------------------------------------------------
# CurlCffiTransport: constructor attributes
# ---------------------------------------------------------------------------


def test_curl_cffi_targets_constant():
    """CURL_CFFI_TARGETS should be a non-empty list of known impersonation targets."""
    from pyfetcher.transports.curl_cffi import CURL_CFFI_TARGETS

    assert isinstance(CURL_CFFI_TARGETS, list)
    assert len(CURL_CFFI_TARGETS) > 0
    assert "chrome120" in CURL_CFFI_TARGETS
    assert "firefox117" in CURL_CFFI_TARGETS


def test_curl_cffi_transport_constructor():
    from pyfetcher.transports.curl_cffi import CurlCffiTransport

    transport = CurlCffiTransport(impersonate="chrome133")
    assert transport.impersonate == "chrome133"
    assert transport._sync_session is None
    assert transport._async_session is None
    assert transport._owns_sync is True
    assert transport._owns_async is True


def test_curl_cffi_transport_default_impersonate():
    from pyfetcher.transports.curl_cffi import CurlCffiTransport

    transport = CurlCffiTransport()
    assert transport.impersonate == "chrome120"


# ---------------------------------------------------------------------------
# CloudscraperTransport: constructor attributes
# ---------------------------------------------------------------------------


def test_cloudscraper_transport_constructor():
    from pyfetcher.transports.cloudscraper import CloudscraperTransport

    transport = CloudscraperTransport()
    assert transport._browser == "chrome"
    assert transport._scraper is None


def test_cloudscraper_transport_custom_browser():
    from pyfetcher.transports.cloudscraper import CloudscraperTransport

    transport = CloudscraperTransport(browser="firefox")
    assert transport._browser == "firefox"
