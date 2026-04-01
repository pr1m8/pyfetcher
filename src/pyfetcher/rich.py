"""Rich-friendly debug rendering helpers for :mod:`pyfetcher`.

Purpose:
    Provide a tiny set of optional rendering helpers for local debugging and
    demos without coupling the core fetch logic to Rich.

Examples:
    ::

        >>> response = FetchResponse(
        ...     request_url="https://example.com/",
        ...     final_url="https://example.com/",
        ...     status_code=200,
        ...     headers={},
        ...     backend="httpx",
        ...     elapsed_ms=1.0,
        ... )
        >>> table = render_fetch_response_table(response)
        >>> table.title
        'Fetch Response'
"""

from __future__ import annotations

from rich.table import Table

from pyfetcher.contracts.response import BatchFetchResponse, FetchResponse


def render_fetch_response_table(response: FetchResponse) -> Table:
    """Render a single fetch response as a Rich table.

    Displays the request URL, final URL, status code, backend name,
    elapsed time, and content type in a formatted table.

    Args:
        response: The fetch response to render.

    Returns:
        A :class:`rich.table.Table` instance ready for printing.

    Examples:
        ::

            >>> response = FetchResponse(
            ...     request_url="https://example.com/",
            ...     final_url="https://example.com/",
            ...     status_code=200,
            ...     headers={},
            ...     backend="httpx",
            ...     elapsed_ms=1.0,
            ... )
            >>> render_fetch_response_table(response).title
            'Fetch Response'
    """
    table = Table(title="Fetch Response")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("request_url", response.request_url)
    table.add_row("final_url", response.final_url)
    table.add_row("status_code", str(response.status_code))
    table.add_row("backend", response.backend)
    table.add_row("elapsed_ms", f"{response.elapsed_ms:.2f}")
    table.add_row("content_type", response.content_type or "")
    return table


def render_batch_summary(batch: BatchFetchResponse) -> Table:
    """Render a batch fetch summary as a Rich table.

    Displays each batch item with its URL, success status, and either
    the HTTP status code or error message.

    Args:
        batch: The batch fetch response to render.

    Returns:
        A :class:`rich.table.Table` instance ready for printing.

    Examples:
        ::

            >>> render_batch_summary(BatchFetchResponse(items=[])).title
            'Batch Fetch Summary'
    """
    table = Table(title="Batch Fetch Summary")
    table.add_column("request_url")
    table.add_column("ok")
    table.add_column("status_or_error")
    for item in batch.items:
        status_or_error = (
            str(item.response.status_code) if item.response is not None else (item.error or "")
        )
        table.add_row(item.request_url, str(item.ok), status_or_error)
    return table
