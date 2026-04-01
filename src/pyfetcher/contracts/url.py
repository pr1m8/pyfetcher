"""Validated URL value objects for :mod:`pyfetcher`.

Purpose:
    Provide a small immutable wrapper around :class:`pydantic.HttpUrl` with
    useful derived helpers for host, path, and query decomposition.

Design:
    - ``URL`` is intentionally pure and contains no I/O behavior.
    - Computed properties remain deterministic and serialization-friendly.
    - The model is frozen so it behaves like a value object.

Examples:
    ::

        >>> url = URL("https://example.com/a/b/?x=1&x=2&y=")
        >>> url.host
        'example.com'
        >>> url.path_segments
        ['a', 'b']
        >>> url.query_params["x"]
        ['1', '2']
"""

from __future__ import annotations

from urllib.parse import parse_qs

from pydantic import ConfigDict, HttpUrl, RootModel, computed_field


class URL(RootModel[HttpUrl]):
    """Validated HTTP/HTTPS URL with derived helpers.

    Wraps :class:`pydantic.HttpUrl` to provide computed decomposition of
    scheme, host, port, path segments, and query parameters as a frozen
    value object suitable for embedding in request models.

    Args:
        root: The raw URL string or ``HttpUrl`` instance to validate.

    Raises:
        pydantic.ValidationError: If the value is not a valid HTTP/HTTPS URL.

    Examples:
        ::

            >>> url = URL("https://example.com:8443/a/b/?x=1&x=2")
            >>> url.host
            'example.com'
            >>> url.port
            8443
    """

    model_config = ConfigDict(frozen=True)

    @computed_field
    @property
    def scheme(self) -> str:
        """Return the URL scheme (e.g. ``'https'``).

        Returns:
            The scheme component of the URL.

        Examples:
            ::

                >>> URL("https://example.com").scheme
                'https'
        """
        return self.root.scheme

    @computed_field
    @property
    def host(self) -> str | None:
        """Return the hostname.

        Returns:
            The host if present, otherwise ``None``.

        Examples:
            ::

                >>> URL("https://example.com").host
                'example.com'
        """
        return self.root.host

    @computed_field
    @property
    def port(self) -> int | None:
        """Return the explicit port number.

        Returns:
            The explicit port if present, otherwise ``None``.

        Examples:
            ::

                >>> URL("https://example.com:9443").port
                9443
        """
        return self.root.port

    @computed_field
    @property
    def path(self) -> str | None:
        """Return the path component.

        Returns:
            The path if present, otherwise ``None``.

        Examples:
            ::

                >>> URL("https://example.com/a/b").path
                '/a/b'
        """
        return self.root.path

    @computed_field
    @property
    def path_segments(self) -> list[str]:
        """Return non-empty path segments.

        Returns:
            A list of non-empty path segments split on ``/``.

        Examples:
            ::

                >>> URL("https://example.com/a/b/").path_segments
                ['a', 'b']
        """
        return [segment for segment in (self.root.path or "").split("/") if segment]

    @computed_field
    @property
    def query(self) -> str | None:
        """Return the raw query string.

        Returns:
            The raw query string if present, otherwise ``None``.

        Examples:
            ::

                >>> URL("https://example.com?a=1&b=2").query
                'a=1&b=2'
        """
        return self.root.query

    @computed_field
    @property
    def query_params(self) -> dict[str, list[str]]:
        """Return parsed query parameters.

        Returns:
            Parsed query parameters as a dict mapping keys to lists of values,
            preserving blank values.

        Examples:
            ::

                >>> URL("https://example.com?a=1&a=2&b=").query_params
                {'a': ['1', '2'], 'b': ['']}
        """
        return parse_qs(self.root.query or "", keep_blank_values=True)

    def unicode_string(self) -> str:
        """Return the normalized URL string.

        Returns:
            The normalized URL as a Unicode string.

        Examples:
            ::

                >>> URL("https://example.com").unicode_string()
                'https://example.com/'
        """
        return str(self.root)

    def __str__(self) -> str:
        """Return the normalized URL string.

        Returns:
            The normalized URL as a Unicode string.

        Examples:
            ::

                >>> str(URL("https://example.com"))
                'https://example.com/'
        """
        return str(self.root)
