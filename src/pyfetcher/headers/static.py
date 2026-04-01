"""Static header providers for :mod:`pyfetcher`.

Purpose:
    Provide the simplest possible provider that always returns the same header
    set regardless of the request.

Examples:
    ::

        >>> provider = StaticHeaderProvider({"user-agent": "ua"})
        >>> provider.build(request=FetchRequest(url="https://example.com"))["user-agent"]
        'ua'
"""

from __future__ import annotations

from pyfetcher.contracts.request import FetchRequest


class StaticHeaderProvider:
    """Always return the same header set.

    Useful for testing or when a fixed set of headers is required for all
    requests (e.g. an API token header).

    Args:
        headers: Static headers to return for every request.

    Examples:
        ::

            >>> provider = StaticHeaderProvider({"x-demo": "1"})
            >>> provider.build(request=FetchRequest(url="https://example.com"))["x-demo"]
            '1'
    """

    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = dict(headers)

    def build(self, *, request: FetchRequest) -> dict[str, str]:
        """Return static headers.

        Args:
            request: The fetch request (ignored).

        Returns:
            A shallow copy of the configured headers.
        """
        return dict(self._headers)
