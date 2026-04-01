"""Tests for pyfetcher.events.channels and pyfetcher.events.publisher modules."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from pyfetcher.events.channels import Channels
from pyfetcher.events.publisher import EventPublisher


class TestChannelConstants:
    def test_crawl_jobs_channel(self):
        assert Channels.CRAWL_JOBS == "crawl_jobs"

    def test_scrape_jobs_channel(self):
        assert Channels.SCRAPE_JOBS == "scrape_jobs"

    def test_download_jobs_channel(self):
        assert Channels.DOWNLOAD_JOBS == "download_jobs"

    def test_all_channels_are_strings(self):
        for attr in ("CRAWL_JOBS", "SCRAPE_JOBS", "DOWNLOAD_JOBS"):
            value = getattr(Channels, attr)
            assert isinstance(value, str)

    def test_channels_are_unique(self):
        channels = [Channels.CRAWL_JOBS, Channels.SCRAPE_JOBS, Channels.DOWNLOAD_JOBS]
        assert len(set(channels)) == 3


class TestEventPublisher:
    @pytest.mark.asyncio
    async def test_event_publisher_calls_notify(self):
        mock_session = AsyncMock()
        publisher = EventPublisher(mock_session)

        await publisher.publish(Channels.CRAWL_JOBS, "some-job-uuid")

        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        # The first positional arg is a text() clause
        sql_text = str(call_args[0][0])
        assert "NOTIFY" in sql_text
        assert "crawl_jobs" in sql_text
        # The second positional arg is the params dict
        assert call_args[0][1] == {"payload": "some-job-uuid"}

    @pytest.mark.asyncio
    async def test_event_publisher_different_channels(self):
        mock_session = AsyncMock()
        publisher = EventPublisher(mock_session)

        await publisher.publish(Channels.SCRAPE_JOBS, "uuid-1")
        await publisher.publish(Channels.DOWNLOAD_JOBS, "uuid-2")

        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_event_publisher_payload_forwarded(self):
        mock_session = AsyncMock()
        publisher = EventPublisher(mock_session)

        test_payload = "550e8400-e29b-41d4-a716-446655440000"
        await publisher.publish("custom_channel", test_payload)

        call_args = mock_session.execute.call_args
        assert call_args[0][1]["payload"] == test_payload
