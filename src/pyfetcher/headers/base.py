"""Base header-provider protocols for :mod:`pyfetcher`.

Purpose:
    Define the small protocol surface used by fetch services to obtain headers
    for a request. Any object with a ``build`` method accepting a
    :class:`~pyfetcher.contracts.request.FetchRequest` and returning a
    ``dict[str, str]`` satisfies the protocol.

Examples:
    ::

        >>> from pyfetcher.headers.static import StaticHeaderProvider
        >>> provider = StaticHeaderProvider({"x-test": "1"})
        >>> hasattr(provider, "build")
        True
"""

from __future__ import annotations

from typing import Protocol

from pyfetcher.contracts.request import FetchRequest


class HeaderProvider(Protocol):
    """Protocol for header-provider strategies.

    Any object that implements ``build(*, request: FetchRequest) -> dict[str, str]``
    satisfies this protocol and can be used with :class:`~pyfetcher.fetch.service.FetchService`.

    Examples:
        ::

            >>> from pyfetcher.headers.static import StaticHeaderProvider
            >>> provider = StaticHeaderProvider({"user-agent": "test"})
            >>> provider.build(request=FetchRequest(url="https://example.com"))["user-agent"]
            'test'
    """

    def build(self, *, request: FetchRequest) -> dict[str, str]:
        """Build request headers for the given fetch request.

        Args:
            request: The fetch request for which headers are needed.

        Returns:
            A dictionary mapping header names to values.
        """
        ...
