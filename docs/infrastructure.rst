Infrastructure
==============

pyfetcher includes Docker Compose infrastructure for Postgres and MinIO.

.. mermaid::

   graph TB
       subgraph Docker Compose
           PG[("🐘 PostgreSQL 17<br/>Jobs · Pages · Media<br/>Hosts · Feeds · URLs")]
           MIO[("📦 MinIO<br/>S3-compatible<br/>Object Storage")]
       end

       subgraph pyfetcher Workers
           CW["🔍 Crawl Workers"]
           SW["📄 Scrape Workers"]
           DW["💾 Download Workers"]
       end

       CW <-->|asyncpg| PG
       SW <-->|asyncpg| PG
       DW <-->|asyncpg| PG
       DW -->|aioboto3| MIO

       PG -.->|LISTEN/NOTIFY| CW
       PG -.->|LISTEN/NOTIFY| SW
       PG -.->|LISTEN/NOTIFY| DW

       style PG fill:#336791,color:#fff
       style MIO fill:#C72C48,color:#fff
       style CW fill:#4A90D9,color:#fff
       style SW fill:#7B68EE,color:#fff
       style DW fill:#2ECC71,color:#fff

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

.. mermaid::

   erDiagram
       jobs ||--o{ jobs : "parent_job_id"
       pages ||--o{ media_assets : "page_id"

       jobs {
           uuid id PK
           text type "crawl/scrape/download"
           text state "pending/claimed/running/success/failed/dead"
           text url
           int priority
           jsonb payload
           jsonb result
           text error
           int retry_count
           uuid parent_job_id FK
       }

       pages {
           uuid id PK
           text url
           text hostname
           int status_code
           text html
           text extracted_text
           text extracted_markdown
           text title
           jsonb og_metadata
           jsonb structured_data
       }

       media_assets {
           uuid id PK
           text source_url
           uuid page_id FK
           text minio_bucket
           text minio_key
           text filename
           text mime_type
           bigint file_size_bytes
           text checksum_sha256
           jsonb media_metadata
           text extractor
       }

       seen_urls {
           bigint url_hash PK
           text url
           int fetch_count
       }

       hosts {
           uuid id PK
           text hostname UK
           text robots_txt
           float crawl_delay_seconds
           boolean is_blocked
       }

       feeds {
           uuid id PK
           text url UK
           text title
           int poll_interval_minutes
           boolean is_active
       }

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
