"""Browser header generation examples for pyfetcher.

Demonstrates profile-based header generation, rotation, and user-agent utilities.
"""

from __future__ import annotations

from pyfetcher.contracts.request import FetchRequest
from pyfetcher.headers.browser import BrowserHeaderProvider, get_best_browser_headers
from pyfetcher.headers.profiles import get_profile, list_profiles
from pyfetcher.headers.rotating import RotatingHeaderProvider
from pyfetcher.headers.ua import (
    random_user_agent,
    user_agents_for_browser,
)


def show_all_profiles() -> None:
    """List all available browser profiles."""
    print("Available profiles:")
    for name in list_profiles():
        profile = get_profile(name)
        print(f"  {name:20s} {profile.browser:10s} {profile.platform:10s} mobile={profile.mobile}")


def generate_headers_for_profile() -> None:
    """Generate a complete header set for a specific profile."""
    print("\n--- Chrome Windows Headers ---")
    headers = get_best_browser_headers("chrome_win")
    for key, value in headers.items():
        print(f"  {key}: {value}")

    print("\n--- Firefox macOS Headers ---")
    headers = get_best_browser_headers("firefox_mac")
    for key, value in headers.items():
        print(f"  {key}: {value}")


def rotating_headers_example() -> None:
    """Demonstrate rotating header provider."""
    print("\n--- Rotating Headers (5 samples) ---")
    provider = RotatingHeaderProvider()
    request = FetchRequest(url="https://example.com")
    for i in range(5):
        headers = provider.build(request=request)
        ua = headers["user-agent"]
        # Show just the browser part
        if "Chrome" in ua and "Edg" not in ua:
            browser = "Chrome"
        elif "Firefox" in ua:
            browser = "Firefox"
        elif "Safari" in ua and "Chrome" not in ua:
            browser = "Safari"
        elif "Edg" in ua:
            browser = "Edge"
        else:
            browser = "Unknown"
        print(f"  [{i+1}] {browser}: {ua[:80]}...")


def random_user_agent_examples() -> None:
    """Generate random user-agents with filters."""
    print("\n--- Random User-Agents ---")
    print(f"  Any:     {random_user_agent()}")
    print(f"  Chrome:  {random_user_agent(browser='chrome')}")
    print(f"  Firefox: {random_user_agent(browser='firefox')}")
    print(f"  Mobile:  {random_user_agent(mobile=True)}")
    print(f"  macOS:   {random_user_agent(platform='macOS')}")

    print("\n--- All Chrome UAs ---")
    for ua in user_agents_for_browser("chrome"):
        print(f"  {ua}")


def header_provider_with_fetch() -> None:
    """Use a header provider with FetchService."""
    from pyfetcher.fetch.service import FetchService

    # Fixed profile
    service = FetchService(header_provider=BrowserHeaderProvider("safari_mac"))
    print("\n--- Safari macOS via FetchService ---")
    # Just show what headers would be generated
    request = FetchRequest(url="https://example.com")
    prepared = service._prepare_request(request)
    print(f"  User-Agent: {prepared.headers.get('user-agent', 'N/A')}")
    service.close()


if __name__ == "__main__":
    show_all_profiles()
    generate_headers_for_profile()
    rotating_headers_example()
    random_user_agent_examples()
    header_provider_with_fetch()
