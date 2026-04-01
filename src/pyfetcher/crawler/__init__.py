"""Web crawler framework for :mod:`pyfetcher`.

Purpose:
    Provide URL frontier management, deduplication, politeness enforcement,
    spider routing, and feed monitoring for systematic web crawling.
"""

from __future__ import annotations

__all__: list[str] = [
    "Frontier",
    "Spider",
    "Router",
    "URLDeduplicator",
    "PolitenessEnforcer",
]
