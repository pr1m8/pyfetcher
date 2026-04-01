Infrastructure
==============

pyfetcher includes Docker Compose infrastructure for Postgres and MinIO.

Docker Compose
--------------

.. code-block:: bash

   # Start services
   make infra-up

   # Stop services
   make infra-down

   # View logs
   make infra-logs

   # Reset (destroy volumes)
   make infra-reset

Services:

- **Postgres 17** -- Job queue, page storage, URL dedup, host rules
- **MinIO** -- S3-compatible object storage for media assets

Configuration
-------------

Copy ``infra/.env.example`` to ``.env`` and customize:

.. code-block:: bash

   PYFETCHER_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
   PYFETCHER_MINIO_ENDPOINT=localhost:9000
   PYFETCHER_MINIO_ACCESS_KEY=minioadmin
   PYFETCHER_MINIO_SECRET_KEY=minioadmin
   PYFETCHER_MINIO_BUCKET=pyfetcher

All settings are configurable via environment variables prefixed with
``PYFETCHER_``.

Database Migrations
-------------------

.. code-block:: bash

   make migrate           # Apply all migrations
   make migrate-new MSG="add foo table"  # Create new migration
   make migrate-down      # Rollback one migration
   make migrate-history   # Show history

Database Schema
---------------

.. list-table::
   :header-rows: 1

   * - Table
     - Purpose
   * - ``jobs``
     - Pipeline job queue (crawl/scrape/download) with state machine
   * - ``pages``
     - Fetched HTML with extracted text, markdown, metadata
   * - ``media_assets``
     - Binary files stored in MinIO with metadata
   * - ``seen_urls``
     - URL deduplication via hash index
   * - ``hosts``
     - Per-host robots.txt cache and crawl scheduling
   * - ``feeds``
     - RSS/Atom feed tracking with adaptive polling
