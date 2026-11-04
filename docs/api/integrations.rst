Integrations
============

.. automodule:: pyfetcher.integrations.scrapy
   :members:

.. automodule:: pyfetcher.integrations.webpoet
   :members:

.. automodule:: pyfetcher.integrations.redis_streams
   :members:

.. automodule:: pyfetcher.integrations.redis_store
   :members:

The optional :mod:`pyfetcher.integrations.api` module exposes the durable-job
control plane through FastAPI, including health, submission, inspection,
cancellation, discovery, and Server-Sent Events. Install ``fetchkit[api]``
before importing it. The adapter owns the supplied job application's lifespan.

The optional :mod:`pyfetcher.integrations.grpc` module exposes the same
transport-neutral job service through gRPC unary methods and server-streaming
worker events. Install ``fetchkit[grpc]`` before importing it. JSON payloads use
the versioned protocol catalog; configure TLS and authorization interceptors in
production hosts.
