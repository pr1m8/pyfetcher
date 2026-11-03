Cross-language contracts
========================

fetchkit can export its portable request, response, extraction, acquisition,
media, artifact, search, and job models as versioned JSON Schema. This is the
recommended boundary for a TypeScript control plane, API, or frontend because
it preserves one source of truth in the Python runtime without requiring the
TypeScript project to duplicate Python models by hand.

Export a catalog
----------------

Export one self-contained manifest:

.. code-block:: bash

   pyfetcher contracts list
   pyfetcher contracts list --category acquisition --output json
   pyfetcher contracts export ./generated/fetchkit-contracts.json

Use a split export when a TypeScript or Zod generator expects one JSON Schema
document per input:

.. code-block:: bash

   pyfetcher contracts export ./generated/fetchkit --split

The split layout contains ``manifest.json`` and a ``schemas/`` directory. Each
schema has a stable identifier such as ``acquisition.request@1`` or
``job.result@1``, a JSON Schema ``$id``, a role, and a SHA-256 checksum. The
manifest also includes built-in provider capabilities, provider option schemas,
and versioned job-template input schemas.

Installed acquisition-provider entry points are intentionally excluded by
default. Include them explicitly only in a trusted environment:

.. code-block:: bash

   pyfetcher contracts export ./generated/fetchkit --split \
       --load-provider-plugins

TypeScript boundary
-------------------

A predominantly TypeScript system can treat Python as the execution plane:

.. mermaid::

   flowchart LR
       TS["TypeScript control plane"] -->|JobRequest / AcquisitionRequest| PY["fetchkit worker"]
       PY -->|JobResult / AcquisitionEvent| TS
       PY -->|large bytes| BLOB["BlobStore"]
       BLOB -->|BlobRef / ArtifactRef| TS

Run the exported schemas through the JSON-Schema-to-TypeScript or
JSON-Schema-to-Zod generator selected by the TypeScript project. Generate the
types in CI and fail on an unexpected checksum change. Do not edit generated
types manually.

The first durable transport should be ordinary JSON messages or HTTP plus
Server-Sent Events for acquisition progress. Protobuf or gRPC can be layered on
later if profiling shows that stronger code generation or binary framing is
worth maintaining a second schema system.

What is portable
----------------

The catalog uses each Pydantic model's serialization schema. It includes:

* HTTP requests, buffered responses, batches, policies, and stream chunks.
* URL values and domain decomposition.
* CSS/XPath, link, image, gallery, and collection rules and results.
* Acquisition requests, results, events, provenance, and capabilities.
* Normalized media metadata and image-processing contracts.
* Blob and artifact references and ordered collections.
* Job, flow, queue, search, and built-in job-template contracts.

Process-local behavior is deliberately absent. Streaming iterators,
``content_factory`` callables, live clients, resolved credentials, blob-store
handles, and executable template implementations are injected on the Python
side. ``credential_ref`` may cross the boundary, but secret values must not.

Versioning
----------

``name@version`` identifies one contract revision. Add a new revision for a
breaking wire change; do not silently replace an existing revision. The
top-level ``protocol_version`` versions the manifest envelope, while
``package_version`` records which fetchkit build produced it. Checksums make
schema drift visible even before a package is published.

Python applications can assemble a custom catalog from their own provider and
template registries:

.. code-block:: python

   from pyfetcher import build_protocol_catalog

   catalog = build_protocol_catalog(
       providers=acquisition_service.capabilities(),
       templates=template_registry.descriptors(),
   )

   job_schema = catalog.schema_for("job.request@1")

RPC safety boundary
-------------------

The catalog is a contract export, not a remotely accessible fetch service.
Any future HTTP, WebSocket, or RPC gateway must add authentication,
authorization, egress and private-network controls, URL validation, request and
response size limits, quotas, cancellation, audit logging, and secret
resolution. Keep those policies outside provider implementations so CLI,
workers, and APIs can enforce different trust models over the same contracts.
