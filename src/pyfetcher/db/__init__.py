"""Database layer for :mod:`pyfetcher`.

Purpose:
    Provide async SQLAlchemy ORM models, engine/session factories, and
    repository helpers for the pyfetcher pipeline's PostgreSQL backend.

Design:
    - ``engine`` provides async engine and session factory construction.
    - ``models`` contains the ORM table definitions (Base, jobs, pages, etc.).
    - ``repo`` provides common query patterns (job claiming, URL dedup).
    - All database dependencies (sqlalchemy, asyncpg) are optional; imports
      are guarded so the rest of pyfetcher works without them.
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from pyfetcher.db.engine import (  # noqa: F401
        build_async_engine,
        build_session_factory,
    )
except Exception:  # pragma: no cover - optional dependency guard  # nosec B110
    pass
else:
    __all__.extend(["build_async_engine", "build_session_factory"])

try:
    from pyfetcher.db.models.base import Base  # noqa: F401
    from pyfetcher.db.models.feed import Feed  # noqa: F401
    from pyfetcher.db.models.host import Host  # noqa: F401
    from pyfetcher.db.models.job import Job  # noqa: F401
    from pyfetcher.db.models.media import MediaAsset  # noqa: F401
    from pyfetcher.db.models.page import Page  # noqa: F401
    from pyfetcher.db.models.url import SeenURL  # noqa: F401
except Exception:  # pragma: no cover - optional dependency guard  # nosec B110
    pass
else:
    __all__.extend(["Base", "Feed", "Host", "Job", "MediaAsset", "Page", "SeenURL"])

try:
    from pyfetcher.db.repo import (  # noqa: F401
        check_url_seen,
        claim_job,
        complete_job,
        create_job,
        fail_job,
        mark_url_seen,
        notify,
    )
except Exception:  # pragma: no cover - optional dependency guard  # nosec B110
    pass
else:
    __all__.extend(
        [
            "check_url_seen",
            "claim_job",
            "complete_job",
            "create_job",
            "fail_job",
            "mark_url_seen",
            "notify",
        ]
    )
