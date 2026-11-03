Integrations
============

.. automodule:: pyfetcher.integrations.scrapy
   :members:

.. automodule:: pyfetcher.integrations.webpoet
   :members:

.. automodule:: pyfetcher.integrations.redis_streams
   :members:

The optional :mod:`pyfetcher.integrations.api` module exposes the durable-job
control plane through FastAPI, including health, submission, inspection,
cancellation, discovery, and Server-Sent Events. Install ``fetchkit[api]``
before importing it. The adapter owns the supplied job application's lifespan.
