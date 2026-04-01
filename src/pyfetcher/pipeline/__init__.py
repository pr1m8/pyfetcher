"""Pipeline orchestration for :mod:`pyfetcher`.

Purpose:
    Connect crawl, scrape, and download stages into an event-driven
    pipeline using Postgres LISTEN/NOTIFY for coordination.
"""

from __future__ import annotations

__all__ = ["PipelineStage", "PipelineRunner"]
