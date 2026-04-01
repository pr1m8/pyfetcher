"""RSS/Atom feed monitor for :mod:`pyfetcher.crawler`.

Purpose:
    Monitor RSS/Atom feeds for new entries with adaptive polling
    intervals based on publication frequency.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FeedEntry:
    """A single feed entry."""

    url: str
    title: str | None = None
    published: str | None = None
    summary: str | None = None


@dataclass
class FeedPollResult:
    """Result of polling a feed."""

    new_entries: list[FeedEntry] = field(default_factory=list)
    latest_entry_hash: str | None = None
    suggested_interval_minutes: int = 60


def parse_feed(content: str) -> list[FeedEntry]:
    """Parse RSS/Atom feed content into entries.

    Args:
        content: Raw feed XML/content.

    Returns:
        A list of :class:`FeedEntry` objects.
    """
    import feedparser  # type: ignore[import-untyped]

    feed = feedparser.parse(content)
    entries = []
    for entry in feed.entries:
        link = entry.get("link", "")
        if not link:
            continue
        entries.append(
            FeedEntry(
                url=link,
                title=entry.get("title"),
                published=entry.get("published"),
                summary=entry.get("summary"),
            )
        )
    return entries


def compute_entry_hash(entry: FeedEntry) -> str:
    """Compute a hash for feed entry change detection.

    Args:
        entry: The feed entry.

    Returns:
        A hex digest string.
    """
    data = f"{entry.url}|{entry.title or ''}".encode()
    return hashlib.sha256(data).hexdigest()[:16]


def calculate_poll_interval(
    entry_count: int,
    *,
    current_interval: int = 60,
    min_interval: int = 10,
    max_interval: int = 1440,
) -> int:
    """Calculate an adaptive polling interval based on new entry count.

    More new entries = shorter interval. No new entries = longer interval.

    Args:
        entry_count: Number of new entries found.
        current_interval: Current polling interval in minutes.
        min_interval: Minimum interval in minutes.
        max_interval: Maximum interval in minutes.

    Returns:
        Suggested interval in minutes.
    """
    if entry_count >= 5:
        new_interval = max(current_interval // 2, min_interval)
    elif entry_count >= 1:
        new_interval = current_interval
    else:
        new_interval = min(current_interval * 2, max_interval)
    return new_interval
