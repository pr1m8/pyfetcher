"""Advanced backend examples for pyfetcher.

Demonstrates using curl_cffi and cloudscraper backends.

Note: These examples require optional dependencies:
    pip install curl_cffi cloudscraper
"""

from __future__ import annotations

from pyfetcher import FetchRequest


def curl_cffi_example() -> None:
    """Fetch with curl_cffi TLS fingerprint impersonation.

    curl_cffi matches real browser JA3/JA4 TLS fingerprints,
    making requests appear to originate from genuine browsers
    at the network layer.

    Install: pip install curl_cffi
    """
    print("=== curl_cffi Backend ===")
    try:
        from pyfetcher.fetch.service import FetchService

        service = FetchService()
        request = FetchRequest(
            url="https://httpbin.org/get",
            backend="curl_cffi",
        )
        response = service.fetch(request)
        print(f"  Status: {response.status_code}")
        print(f"  Backend: {response.backend}")
        print(f"  Elapsed: {response.elapsed_ms:.1f}ms")
        service.close()
    except ImportError:
        print("  curl_cffi not installed. Run: pip install curl_cffi")


def cloudscraper_example() -> None:
    """Fetch with cloudscraper Cloudflare bypass.

    cloudscraper solves Cloudflare's JavaScript challenges
    automatically. Sync-only.

    Install: pip install cloudscraper
    """
    print("\n=== cloudscraper Backend ===")
    try:
        from pyfetcher.fetch.service import FetchService

        service = FetchService()
        request = FetchRequest(
            url="https://httpbin.org/get",
            backend="cloudscraper",
        )
        response = service.fetch(request)
        print(f"  Status: {response.status_code}")
        print(f"  Backend: {response.backend}")
        print(f"  Elapsed: {response.elapsed_ms:.1f}ms")
        service.close()
    except ImportError:
        print("  cloudscraper not installed. Run: pip install cloudscraper")


def backend_comparison() -> None:
    """Show available backends and their capabilities."""
    print("\n=== Backend Capabilities ===")
    print("  Backend       | Sync | Async | Stream | TLS Fingerprint | CF Bypass")
    print("  ------------- | ---- | ----- | ------ | --------------- | ---------")
    print("  httpx         |  Y   |   Y   |   Y    |       N         |    N     ")
    print("  aiohttp       |  N   |   Y   |   Y    |       N         |    N     ")
    print("  curl_cffi     |  Y   |   Y   |   Y    |       Y         |    N     ")
    print("  cloudscraper  |  Y   |   N   |   N    |       N         |    Y     ")


if __name__ == "__main__":
    backend_comparison()
    curl_cffi_example()
    cloudscraper_example()
