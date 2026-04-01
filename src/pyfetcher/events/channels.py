"""NOTIFY channel constants for :mod:`pyfetcher.events`."""

from __future__ import annotations


class Channels:
    """Postgres NOTIFY channel names for pipeline stages."""

    CRAWL_JOBS = "crawl_jobs"
    SCRAPE_JOBS = "scrape_jobs"
    DOWNLOAD_JOBS = "download_jobs"
