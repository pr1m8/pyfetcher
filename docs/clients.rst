Reusable clients
================

The module-level :func:`pyfetcher.fetch` and :func:`pyfetcher.afetch`
functions are useful for scripts. Services and web applications should keep a
client alive across requests so connection pools, TLS sessions, and HTTP/2
connections can be reused.

Async client
------------

:class:`pyfetcher.AsyncFetchClient` owns a
:class:`~pyfetcher.fetch.service.FetchService` by default and closes its pools
when the async context exits:

.. code-block:: python

   from pyfetcher import AsyncFetchClient, PoolPolicy, TimeoutPolicy

   async with AsyncFetchClient(
       base_url="https://api.example.com/v1/",
       headers={"authorization": "Bearer ..."},
       http2=True,
       pool=PoolPolicy(max_connections=100, concurrency=20),
       timeout=TimeoutPolicy(total_seconds=60),
   ) as client:
       response = await client.get("users")
       print(response.status_code, response.http_version)

HTTP/2 is enabled for the default HTTPX backend. Protocol negotiation still
depends on the server and TLS ALPN, so a request may fall back to HTTP/1.1.
Inspect :attr:`pyfetcher.FetchResponse.http_version` to see the negotiated
version. Pools with different HTTP/2, TLS verification, or pool settings are
kept separate.

Client URL adapters
-------------------

Both clients accept the standard ``URL`` input shapes directly. An injected
``URLAdapterRegistry`` adds application-specific values to base URLs, request
methods, streaming calls, and async iteration without global registration.

.. code-block:: python

   from dataclasses import dataclass

   from pyfetcher import AsyncFetchClient, URLAdapterRegistry

   @dataclass(frozen=True)
   class Endpoint:
       path: str

   adapters = URLAdapterRegistry()
   adapters.register_type(Endpoint, lambda endpoint: endpoint.path)

   async with AsyncFetchClient(
       base_url="https://api.example.com/v1/",
       url_adapters=adapters,
   ) as client:
       response = await client.get(Endpoint("users"))

FastAPI integration
-------------------

Create one client in the application lifespan and expose it through a small
dependency. fetchkit does not require FastAPI at runtime.

.. code-block:: python

   from collections.abc import AsyncIterator
   from contextlib import asynccontextmanager
   from typing import Annotated

   from fastapi import Depends, FastAPI, Request
   from pyfetcher import AsyncFetchClient

   @asynccontextmanager
   async def lifespan(app: FastAPI) -> AsyncIterator[None]:
       async with AsyncFetchClient(http2=True) as client:
           app.state.fetcher = client
           yield

   app = FastAPI(lifespan=lifespan)

   def get_fetcher(request: Request) -> AsyncFetchClient:
       return request.app.state.fetcher

   Fetcher = Annotated[AsyncFetchClient, Depends(get_fetcher)]

   @app.get("/upstream")
   async def upstream(fetcher: Fetcher) -> dict[str, object]:
       response = await fetcher.get("https://example.com")
       return {
           "status": response.status_code,
           "protocol": response.http_version,
       }

Do not construct a new client inside every route. That would discard the pool
after each request and remove most of the benefit of HTTP keepalive and HTTP/2.

Streaming responses
-------------------

Both clients provide normalized chunk streams plus direct byte and text
iterators. Text iterators use an incremental decoder, so multibyte characters
remain intact when they cross network chunk boundaries.

.. code-block:: python

   from pyfetcher import AsyncFetchClient, StreamPolicy

   async with AsyncFetchClient(
       stream=StreamPolicy(chunk_size=64 * 1024, max_bytes=100_000_000)
   ) as client:
       async for data in client.iter_bytes("GET", "https://example.com/file"):
           await destination.write(data)

The byte iterator can be passed directly to FastAPI or Starlette's
``StreamingResponse``:

.. code-block:: python

   from fastapi.responses import StreamingResponse

   @app.get("/proxy")
   async def proxy(fetcher: Fetcher) -> StreamingResponse:
       body = fetcher.iter_bytes("GET", "https://example.com/file")
       return StreamingResponse(body, media_type="application/octet-stream")

Streaming request content
-------------------------

``content`` accepts bytes, text, a synchronous byte iterable, or an
asynchronous byte iterable. The async client adapts ordinary generators to an
async request body without joining them in memory.

.. code-block:: python

   async def upload_body():
       async for record in records():
           yield record.to_json().encode() + b"\n"

   async with AsyncFetchClient() as client:
       response = await client.post(
           "https://example.com/import",
           headers={"content-type": "application/x-ndjson"},
           content=upload_body(),
       )

Each yielded item must be ``bytes``. Runtime streams are one-shot objects and
are intentionally omitted from :meth:`pyfetcher.FetchRequest.model_dump`.
Use ``data`` for serializable buffered bytes or text and ``json_data`` for a
JSON body. These body fields are mutually exclusive.

A generator passed as ``content`` is one-shot. When an upload may be retried,
pass ``content_factory`` so every attempt receives a fresh stream:

.. code-block:: python

   def content_factory():
       with source.open("rb") as handle:
           while chunk := handle.read(64 * 1024):
               yield chunk

   response = await client.post(url, content_factory=content_factory)

Lazy pooled iteration
---------------------

:meth:`pyfetcher.AsyncFetchClient.imap` consumes ordinary or async iterables
lazily and keeps at most ``concurrency`` requests active. This allows a URL
generator to be much larger than memory.

.. code-block:: python

   async with AsyncFetchClient() as client:
       async for response in client.imap(
           discover_urls(),
           concurrency=20,
           ordered=False,
       ):
           print(response.final_url, response.status_code)

``ordered=True`` (the default) preserves input order with bounded buffering.
``ordered=False`` yields completed responses immediately. Transport errors are
raised during iteration; callers that need per-item error capture can use
:meth:`pyfetcher.FetchService.afetch_many`.

Synchronous client
------------------

:class:`pyfetcher.FetchClient` provides the same defaults, pooled HTTPX
connections, and response helpers for synchronous programs:

.. code-block:: python

   from pyfetcher import FetchClient

   with FetchClient(http2=True) as client:
       for text in client.iter_text("GET", "https://example.com/events"):
           print(text, end="")

The default HTTPX backend supports synchronous streaming. aiohttp is async
only, curl_cffi currently exposes async response streaming, and cloudscraper
does not expose response streaming through fetchkit.
