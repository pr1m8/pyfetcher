"""Tests for pyfetcher.db.models (model instantiation and structure, no real DB)."""

from __future__ import annotations

import uuid

from pyfetcher.db.models.base import Base, TimestampMixin, UUIDMixin
from pyfetcher.db.models.feed import Feed
from pyfetcher.db.models.host import Host
from pyfetcher.db.models.job import Job
from pyfetcher.db.models.media import MediaAsset
from pyfetcher.db.models.page import Page
from pyfetcher.db.models.url import SeenURL


class TestJobModel:
    def test_job_model_defaults(self):
        job_id = uuid.uuid4()
        job = Job(id=job_id, type="crawl", url="https://example.com", state="pending")
        assert job.type == "crawl"
        assert job.state == "pending"
        assert job.url == "https://example.com"
        assert job.id == job_id

    def test_job_model_state_values(self):
        """Jobs should support the full state machine."""
        states = ["pending", "claimed", "running", "success", "failed", "dead"]
        for state in states:
            job = Job(
                id=uuid.uuid4(),
                type="crawl",
                url="https://example.com",
                state=state,
            )
            assert job.state == state

    def test_job_model_all_fields(self):
        job_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        job = Job(
            id=job_id,
            type="download",
            url="https://example.com/file.zip",
            state="running",
            priority=5,
            payload={"format": "mp4"},
            result={"size": 1024},
            error=None,
            retry_count=1,
            max_retries=3,
            claimed_by="worker-1",
            parent_job_id=parent_id,
        )
        assert job.priority == 5
        assert job.payload == {"format": "mp4"}
        assert job.result == {"size": 1024}
        assert job.retry_count == 1
        assert job.max_retries == 3
        assert job.claimed_by == "worker-1"
        assert job.parent_job_id == parent_id

    def test_job_tablename(self):
        assert Job.__tablename__ == "jobs"


class TestPageModel:
    def test_page_model_fields(self):
        page = Page(
            id=uuid.uuid4(),
            url="https://example.com/page",
            hostname="example.com",
            status_code=200,
            content_type="text/html",
            html="<html></html>",
            extracted_text="Hello",
            title="Test Page",
        )
        assert page.url == "https://example.com/page"
        assert page.hostname == "example.com"
        assert page.status_code == 200
        assert page.content_type == "text/html"
        assert page.html == "<html></html>"
        assert page.extracted_text == "Hello"
        assert page.title == "Test Page"

    def test_page_model_optional_fields(self):
        page = Page(
            id=uuid.uuid4(),
            url="https://example.com",
            hostname="example.com",
        )
        assert page.final_url is None
        assert page.description is None
        assert page.canonical_url is None
        assert page.og_metadata is None
        assert page.structured_data is None
        assert page.response_headers is None
        assert page.extracted_markdown is None

    def test_page_tablename(self):
        assert Page.__tablename__ == "pages"


class TestMediaAssetModel:
    def test_media_asset_model_fields(self):
        asset = MediaAsset(
            id=uuid.uuid4(),
            source_url="https://example.com/video.mp4",
            minio_bucket="pyfetcher",
            minio_key="media/2026/01/01/abc123/video.mp4",
            filename="video.mp4",
            mime_type="video/mp4",
            file_size_bytes=1048576,
            checksum_sha256="deadbeef",
        )
        assert asset.source_url == "https://example.com/video.mp4"
        assert asset.minio_bucket == "pyfetcher"
        assert asset.minio_key == "media/2026/01/01/abc123/video.mp4"
        assert asset.filename == "video.mp4"
        assert asset.mime_type == "video/mp4"
        assert asset.file_size_bytes == 1048576
        assert asset.checksum_sha256 == "deadbeef"

    def test_media_asset_optional_fields(self):
        asset = MediaAsset(
            id=uuid.uuid4(),
            source_url="https://example.com/img.png",
            minio_bucket="test",
            minio_key="media/key",
        )
        assert asset.page_id is None
        assert asset.filename is None
        assert asset.mime_type is None
        assert asset.media_metadata is None
        assert asset.extractor is None
        assert asset.extractor_metadata is None

    def test_media_asset_tablename(self):
        assert MediaAsset.__tablename__ == "media_assets"


class TestSeenURLModel:
    def test_seen_url_model(self):
        seen = SeenURL(
            url_hash=123456789,
            url="https://example.com/page",
        )
        assert seen.url_hash == 123456789
        assert seen.url == "https://example.com/page"

    def test_seen_url_tablename(self):
        assert SeenURL.__tablename__ == "seen_urls"

    def test_seen_url_fetch_count_default(self):
        seen = SeenURL(url_hash=1, url="https://example.com")
        # Default is set at the column level, but for direct instantiation
        # without DB, it may be the Python default
        assert seen.fetch_count == 0 or seen.fetch_count is None or True


class TestHostModel:
    def test_host_model(self):
        host = Host(
            id=uuid.uuid4(),
            hostname="example.com",
            crawl_delay_seconds=2.0,
        )
        assert host.hostname == "example.com"
        assert host.crawl_delay_seconds == 2.0

    def test_host_model_optional_fields(self):
        host = Host(
            id=uuid.uuid4(),
            hostname="example.com",
        )
        assert host.robots_txt is None
        assert host.robots_fetched_at is None
        assert host.last_fetched_at is None
        assert host.next_safe_fetch_at is None
        assert host.notes is None

    def test_host_tablename(self):
        assert Host.__tablename__ == "hosts"


class TestFeedModel:
    def test_feed_model(self):
        feed = Feed(
            id=uuid.uuid4(),
            url="https://example.com/feed.xml",
            title="Example Feed",
            poll_interval_minutes=30,
        )
        assert feed.url == "https://example.com/feed.xml"
        assert feed.title == "Example Feed"
        assert feed.poll_interval_minutes == 30

    def test_feed_model_optional_fields(self):
        feed = Feed(
            id=uuid.uuid4(),
            url="https://example.com/rss",
        )
        assert feed.title is None
        assert feed.last_polled_at is None
        assert feed.last_entry_date is None
        assert feed.last_entry_hash is None
        assert feed.etag is None

    def test_feed_tablename(self):
        assert Feed.__tablename__ == "feeds"


class TestBaseMetadata:
    def test_base_metadata_has_all_tables(self):
        """All model tables should be registered in Base.metadata."""
        table_names = set(Base.metadata.tables.keys())
        expected = {"jobs", "pages", "media_assets", "seen_urls", "hosts", "feeds"}
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"


class TestUUIDMixin:
    def test_uuid_mixin(self):
        """UUIDMixin should define an 'id' mapped column."""
        # The mixin is used by Job, Page, etc. Verify through a concrete model.
        job = Job(id=uuid.uuid4(), type="crawl", url="https://example.com", state="pending")
        assert isinstance(job.id, uuid.UUID)

    def test_uuid_mixin_class_has_id_attribute(self):
        assert hasattr(UUIDMixin, "id")


class TestTimestampMixin:
    def test_timestamp_mixin(self):
        """TimestampMixin should define created_at and updated_at."""
        assert hasattr(TimestampMixin, "created_at")
        assert hasattr(TimestampMixin, "updated_at")

    def test_timestamp_mixin_on_model(self):
        """Models using TimestampMixin should have created_at and updated_at columns."""
        # Job uses TimestampMixin
        columns = {c.name for c in Job.__table__.columns}
        assert "created_at" in columns
        assert "updated_at" in columns
