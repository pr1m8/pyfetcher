"""Policy models for :mod:`pyfetcher`.

Purpose:
    Provide serializable policy objects that control retries, timeouts,
    connection pooling, and streaming behavior.

Design:
    - Policies are explicit and reusable across transports.
    - Policies are serializable so they can be persisted or queued later.
    - Backend-specific conversion happens outside these models.

Examples:
    ::

        >>> retry = RetryPolicy(attempts=4)
        >>> retry.attempts
        4
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RetryPolicy(BaseModel):
    """Retry policy shared by fetch services.

    Controls how failed requests are retried using exponential backoff. Status
    codes that trigger retries are configurable, as is whether connection-level
    errors should be retried.

    Args:
        attempts: Total number of attempts including the first call.
        wait_base_seconds: Base exponential backoff delay in seconds.
        wait_max_seconds: Maximum delay between attempts in seconds.
        retry_status_codes: HTTP status codes that should trigger retries.
        retry_on_connection_errors: Whether connection errors should retry.
        reraise: Whether the final failure should be re-raised to the caller.

    Examples:
        ::

            >>> RetryPolicy(attempts=3).attempts
            3
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempts: int = 3
    wait_base_seconds: float = 0.5
    wait_max_seconds: float = 8.0
    retry_status_codes: set[int] = Field(
        default_factory=lambda: {408, 409, 425, 429, 500, 502, 503, 504},
    )
    retry_on_connection_errors: bool = True
    reraise: bool = True


class TimeoutPolicy(BaseModel):
    """Timeout policy shared by fetch services.

    Provides granular timeout control for different phases of an HTTP request.
    The ``total_seconds`` value acts as an overall budget that caps the entire
    operation regardless of the per-phase values.

    Args:
        total_seconds: Overall timeout budget in seconds.
        connect_seconds: Maximum time to establish a TCP connection.
        read_seconds: Maximum time to receive the response body.
        write_seconds: Maximum time to send the request body.
        pool_seconds: Maximum time to acquire a connection from the pool.

    Examples:
        ::

            >>> TimeoutPolicy().total_seconds
            30.0
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_seconds: float = 30.0
    connect_seconds: float = 10.0
    read_seconds: float = 30.0
    write_seconds: float = 30.0
    pool_seconds: float = 10.0


class PoolPolicy(BaseModel):
    """Connection pooling and concurrency policy.

    Controls connection pool sizing and keepalive behavior for transport
    backends, as well as the concurrency limit used for async batch
    operations.

    Args:
        max_connections: Maximum total connections across all hosts.
        max_keepalive_connections: Maximum keepalive connections where supported.
        keepalive_expiry_seconds: Time-to-live for idle keepalive connections.
        max_connections_per_host: Maximum connections to a single host.
        concurrency: Maximum in-flight tasks for async batching.

    Examples:
        ::

            >>> PoolPolicy(concurrency=8).concurrency
            8
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry_seconds: float = 10.0
    max_connections_per_host: int = 10
    concurrency: int = 8


class StreamPolicy(BaseModel):
    """Streaming behavior policy.

    Controls chunk sizing and optional byte limits for streaming operations.
    The ``decode_text`` flag signals downstream consumers that text decoding
    is desired.

    Args:
        chunk_size: Size in bytes of each emitted chunk.
        decode_text: Whether downstream consumers expect text decoding.
        max_bytes: Optional cap on total consumed bytes (``None`` for unlimited).

    Examples:
        ::

            >>> StreamPolicy().chunk_size
            65536
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_size: int = 65_536
    decode_text: bool = False
    max_bytes: int | None = None
