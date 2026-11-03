CLI Reference
=============

pyfetcher provides a command-line interface for common operations.

fetch
-----

Fetch a URL and display the response:

.. code-block:: bash

   pyfetcher fetch https://example.com
   pyfetcher fetch https://api.example.com -m POST -d '{"key": "val"}'
   pyfetcher fetch https://example.com -o json
   pyfetcher fetch https://example.com -o raw
   pyfetcher fetch https://example.com --profile firefox_win

Backends can be selected with ``-b``:

.. code-block:: bash

   pyfetcher fetch https://example.com -b curl_cffi
   pyfetcher fetch https://example.com -b cloudscraper

headers
-------

Preview generated browser headers:

.. code-block:: bash

   pyfetcher headers --profile chrome_win
   pyfetcher headers --browser firefox -o json
   pyfetcher headers --list

scrape
------

Scrape content from a URL:

.. code-block:: bash

   pyfetcher scrape https://example.com --css "h1"
   pyfetcher scrape https://example.com --links -o json
   pyfetcher scrape https://example.com --text
   pyfetcher scrape https://example.com --meta
   pyfetcher scrape https://example.com --forms

user-agent
----------

Generate random user-agent strings:

.. code-block:: bash

   pyfetcher user-agent
   pyfetcher user-agent --browser chrome --count 5
   pyfetcher user-agent --mobile

robots
------

Check robots.txt for a URL:

.. code-block:: bash

   pyfetcher robots https://example.com
   pyfetcher robots https://example.com -p /admin -u Googlebot

download
--------

Download a file:

.. code-block:: bash

   pyfetcher download https://example.com/file.pdf ./file.pdf

templates
---------

Inspect the built-in versioned job catalog and validate JSON before enqueueing
it into a local, Redis, Temporal, or future RPC runtime:

.. code-block:: bash

   pyfetcher templates list
   pyfetcher templates list --output json
   pyfetcher templates validate job.json

jobs
----

Run a serialized job or dynamic flow to completion with shared clients, local
artifact storage, bounded concurrency, and JSON output:

.. code-block:: bash

   pyfetcher jobs run flow.json
   pyfetcher jobs run job.json --concurrency 8 --artifacts-dir ./artifacts
   pyfetcher jobs run flow.json --log-format json

Install ``fetchkit[api]`` to host the HTTP control plane and worker in one
process:

.. code-block:: bash

   pyfetcher jobs serve --host 127.0.0.1 --port 8000 --concurrency 8

Add ``fetchkit[observe]`` and pass ``--otlp-endpoint`` to either command for
OpenTelemetry job spans and metrics. The default queue and status store are
in-memory; inject durable adapters in an application host for restart or
multi-process durability.

contracts
---------

Inspect or export the versioned JSON Schema catalog used by TypeScript,
workers, queues, and future RPC layers:

.. code-block:: bash

   pyfetcher contracts list
   pyfetcher contracts list --category job --output json
   pyfetcher contracts export ./generated/fetchkit-contracts.json
   pyfetcher contracts export ./generated/fetchkit --split

Use ``--load-provider-plugins`` only when installed third-party acquisition
providers should be imported and included in the provider capability catalog.
