"""ORM models for :mod:`pyfetcher.db`.

Purpose:
    Re-export all SQLAlchemy ORM model classes for convenient access.
"""

from __future__ import annotations

from pyfetcher.db.models.base import Base, TimestampMixin, UUIDMixin
from pyfetcher.db.models.feed import Feed
from pyfetcher.db.models.host import Host
from pyfetcher.db.models.job import Job
from pyfetcher.db.models.media import MediaAsset
from pyfetcher.db.models.page import Page
from pyfetcher.db.models.url import SeenURL

__all__ = [
    "Base",
    "Feed",
    "Host",
    "Job",
    "MediaAsset",
    "Page",
    "SeenURL",
    "TimestampMixin",
    "UUIDMixin",
]
