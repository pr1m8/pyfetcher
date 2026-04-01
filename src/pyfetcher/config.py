"""Application configuration for :mod:`pyfetcher`.

Purpose:
    Provide a centralized, environment-aware configuration object using
    ``pydantic-settings``. Reads from environment variables (prefixed with
    ``PYFETCHER_``) and ``.env`` files.

Design:
    - All infrastructure connection details (Postgres, MinIO) are configurable.
    - Pipeline concurrency and behavior are tunable per deployment.
    - Defaults are suitable for local development with Docker Compose.

Examples:
    ::

        >>> config = PyfetcherConfig()
        >>> config.database_url
        'postgresql+asyncpg://pyfetcher:pyfetcher@localhost:5432/pyfetcher'
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class PyfetcherConfig(BaseSettings):
    """Centralized configuration for pyfetcher infrastructure and pipeline.

    Reads from environment variables prefixed with ``PYFETCHER_`` and
    from ``.env`` files. Defaults are suitable for local development
    with the provided Docker Compose setup.

    Args:
        database_url: SQLAlchemy async connection string for PostgreSQL.
        db_pool_size: Base connection pool size for asyncpg.
        db_max_overflow: Maximum overflow connections beyond pool_size.
        minio_endpoint: MinIO server endpoint (host:port).
        minio_access_key: MinIO access key.
        minio_secret_key: MinIO secret key.
        minio_secure: Whether to use HTTPS for MinIO connections.
        minio_bucket: Default bucket name for storing assets.
        crawl_concurrency: Maximum concurrent crawl workers.
        scrape_concurrency: Maximum concurrent scrape workers.
        download_concurrency: Maximum concurrent download workers.
        default_crawl_delay_seconds: Default politeness delay between
            requests to the same host.
        max_retries: Default maximum retry attempts for failed jobs.
    """

    model_config = SettingsConfigDict(
        env_prefix="PYFETCHER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://pyfetcher:pyfetcher@localhost:5432/pyfetcher"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "pyfetcher"

    # Pipeline concurrency
    crawl_concurrency: int = 10
    scrape_concurrency: int = 20
    download_concurrency: int = 5
    default_crawl_delay_seconds: float = 1.0
    max_retries: int = 3
