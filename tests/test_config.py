"""Tests for pyfetcher.config module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pyfetcher.config import PyfetcherConfig


class TestPyfetcherConfigDefaults:
    """Test that PyfetcherConfig defaults are set correctly."""

    def test_database_url_default(self):
        config = PyfetcherConfig()
        assert (
            config.database_url
            == "postgresql+asyncpg://pyfetcher:pyfetcher@localhost:5432/pyfetcher"
        )

    def test_db_pool_size_default(self):
        config = PyfetcherConfig()
        assert config.db_pool_size == 10

    def test_db_max_overflow_default(self):
        config = PyfetcherConfig()
        assert config.db_max_overflow == 20

    def test_minio_endpoint_default(self):
        config = PyfetcherConfig()
        assert config.minio_endpoint == "localhost:9000"

    def test_minio_access_key_default(self):
        config = PyfetcherConfig()
        assert config.minio_access_key == "minioadmin"

    def test_minio_secret_key_default(self):
        config = PyfetcherConfig()
        assert config.minio_secret_key == "minioadmin"

    def test_minio_secure_default(self):
        config = PyfetcherConfig()
        assert config.minio_secure is False

    def test_minio_bucket_default(self):
        config = PyfetcherConfig()
        assert config.minio_bucket == "pyfetcher"

    def test_crawl_concurrency_default(self):
        config = PyfetcherConfig()
        assert config.crawl_concurrency == 10

    def test_scrape_concurrency_default(self):
        config = PyfetcherConfig()
        assert config.scrape_concurrency == 20

    def test_download_concurrency_default(self):
        config = PyfetcherConfig()
        assert config.download_concurrency == 5

    def test_default_crawl_delay_seconds_default(self):
        config = PyfetcherConfig()
        assert config.default_crawl_delay_seconds == 1.0

    def test_max_retries_default(self):
        config = PyfetcherConfig()
        assert config.max_retries == 3


class TestPyfetcherConfigEnvPrefix:
    """Test that the PYFETCHER_ env prefix works."""

    def test_env_prefix_overrides_database_url(self):
        with patch.dict(
            "os.environ",
            {"PYFETCHER_DATABASE_URL": "postgresql+asyncpg://custom:custom@db:5432/custom"},
            clear=False,
        ):
            config = PyfetcherConfig()
            assert config.database_url == "postgresql+asyncpg://custom:custom@db:5432/custom"

    def test_env_prefix_overrides_minio_endpoint(self):
        with patch.dict(
            "os.environ",
            {"PYFETCHER_MINIO_ENDPOINT": "minio.example.com:9000"},
            clear=False,
        ):
            config = PyfetcherConfig()
            assert config.minio_endpoint == "minio.example.com:9000"

    def test_env_prefix_overrides_crawl_concurrency(self):
        with patch.dict(
            "os.environ",
            {"PYFETCHER_CRAWL_CONCURRENCY": "50"},
            clear=False,
        ):
            config = PyfetcherConfig()
            assert config.crawl_concurrency == 50

    def test_env_prefix_overrides_minio_secure(self):
        with patch.dict(
            "os.environ",
            {"PYFETCHER_MINIO_SECURE": "true"},
            clear=False,
        ):
            config = PyfetcherConfig()
            assert config.minio_secure is True

    def test_env_prefix_overrides_max_retries(self):
        with patch.dict(
            "os.environ",
            {"PYFETCHER_MAX_RETRIES": "10"},
            clear=False,
        ):
            config = PyfetcherConfig()
            assert config.max_retries == 10


class TestPyfetcherConfigAllFields:
    """Test that all fields are accessible."""

    def test_all_fields_accessible(self):
        config = PyfetcherConfig()
        fields = [
            "database_url",
            "db_pool_size",
            "db_max_overflow",
            "minio_endpoint",
            "minio_access_key",
            "minio_secret_key",
            "minio_secure",
            "minio_bucket",
            "crawl_concurrency",
            "scrape_concurrency",
            "download_concurrency",
            "default_crawl_delay_seconds",
            "max_retries",
        ]
        for field_name in fields:
            assert hasattr(config, field_name), f"Missing field: {field_name}"
            # Ensure it does not raise
            getattr(config, field_name)

    def test_extra_fields_ignored(self):
        """The config should ignore extra env vars."""
        with patch.dict(
            "os.environ",
            {"PYFETCHER_NONEXISTENT_FIELD": "ignored"},
            clear=False,
        ):
            config = PyfetcherConfig()
            assert not hasattr(config, "nonexistent_field")
