Transports
==========

pyfetcher supports multiple HTTP backends. Each transport implements the
:class:`SyncTransport` and/or :class:`AsyncTransport` protocols.

.. list-table:: Backend Capabilities
   :header-rows: 1
   :widths: 20 10 10 10 15 15

   * - Backend
     - Sync
     - Async
     - Stream
     - TLS Fingerprint
     - CF Bypass
   * - ``httpx``
     - Yes
     - Yes
     - Yes
     - No
     - No
   * - ``aiohttp``
     - No
     - Yes
     - Yes
     - No
     - No
   * - ``curl_cffi``
     - Yes
     - Yes
     - Yes
     - Yes
     - No
   * - ``cloudscraper``
     - Yes
     - No
     - No
     - No
     - Yes

Base Protocols
--------------

.. automodule:: pyfetcher.transports.base
   :members:

HTTPX
-----

.. automodule:: pyfetcher.transports.httpx
   :members:

Aiohttp
-------

.. automodule:: pyfetcher.transports.aiohttp
   :members:

curl_cffi
---------

.. automodule:: pyfetcher.transports.curl_cffi
   :members:

Cloudscraper
------------

.. automodule:: pyfetcher.transports.cloudscraper
   :members:
