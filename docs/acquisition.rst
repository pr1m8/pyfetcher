Content acquisition
===================

The acquisition API provides one typed entry point for direct files, yt-dlp
media, and gallery-dl galleries while preserving provider-native controls.

Installation
------------

Direct HTTP acquisition is part of the core package. Specialized providers are
optional:

.. code-block:: bash

   python -m pip install 'fetchkit[downloaders]'

Provider discovery
------------------

.. code-block:: python

   from pyfetcher import AcquisitionService

   async with AcquisitionService() as service:
       for capability in service.capabilities():
           print(
               capability.name,
               capability.available,
               capability.install_extra,
           )

Registered providers expose availability without importing their SDK during
core package startup. If automatic selection chooses an unavailable specialized
provider, fetchkit raises ``ProviderUnavailableError`` with its install extra
instead of silently downloading the surrounding webpage through direct HTTP.

Metadata and downloads
----------------------

.. code-block:: python

   from pyfetcher import AcquisitionRequest, AcquisitionService

   request = AcquisitionRequest(
       url="https://www.youtube.com/watch?v=...",
       provider="yt_dlp",
       operation="metadata",
       yt_dlp_options={"noplaylist": True},
   )

   async with AcquisitionService() as service:
       result = await service.acquire(request)
       for media in result.media:
           print(media.title, media.duration_seconds)

For a download, set ``operation="download"`` and optionally ``output_dir``.
The result contains normalized ``DownloadResult`` entries, checksums where the
provider exposes files, and provenance recording the selected provider and
extractor.

Provider selection
------------------

``provider="auto"`` chooses the highest-scoring registered provider. Direct
files with common extensions prefer ``direct``; known video and gallery hosts
prefer their specialized providers. Use ``direct``, ``yt_dlp``, or
``gallery_dl`` explicitly when a URL is ambiguous or policy requires a fixed
engine.

Provider-native options
-----------------------

Keep native options isolated:

.. code-block:: python

   request = AcquisitionRequest(
       url=url,
       provider="yt_dlp",
       output_dir="media",
       headers={"accept-language": "en-US"},
       proxy="http://proxy.example:8080",
       retries=5,
       filename_template="%(title)s-%(id)s.%(ext)s",
       yt_dlp_options={
           "format": "bestvideo+bestaudio/best",
           "writesubtitles": True,
       },
   )

``yt_dlp_options`` is passed only to yt-dlp. ``gallery_dl_options`` is passed
only to gallery-dl. ``direct_options`` contains FetchRequest-level overrides
for direct HTTP, such as ``backend`` or a policy object. It cannot replace
provider-managed URL, method, headers, or proxy fields. Shared cookies become
an HTTP Cookie header for yt-dlp unless native headers already supply one.

Custom providers use the JSON-safe, namespaced ``provider_options`` mapping.
The same mapping passes through ``media.acquire@1`` jobs and is suitable for
generated TypeScript contracts:

.. code-block:: python

   request = AcquisitionRequest(
       url=url,
       provider="company_media",
       provider_options={
           "company_media": {"quality": 85, "variant": "mobile"},
       },
   )

Credential references
---------------------

Requests can remain serializable and secret-free by storing only a reference:

.. code-block:: python

   from pyfetcher import AcquisitionCredentials, AcquisitionService

   async def resolve_credentials(reference: str) -> AcquisitionCredentials:
       secret = await secret_store.read(reference)
       return AcquisitionCredentials(
           username=secret.username,
           password=secret.password,
           cookie_file=secret.cookie_file,
       )

   service = AcquisitionService(credential_resolver=resolve_credentials)

Pass ``credential_ref="media-account"`` on the request. Resolved credentials
are passed separately to the provider and do not become request fields.

Async event stream
------------------

.. code-block:: python

   async with AcquisitionService() as service:
       async for event in service.aiter_events(request):
           if event.progress:
               print(event.progress.status, event.progress.percent)
           if event.download:
               print("saved", event.download.local_path)

Events include ``started``, ``progress``, ``item``, ``completed``, and
``failed``. The completed event carries the full result. After yielding a
failed event, the iterator raises the original provider error.

Custom providers and middleware
-------------------------------

An acquisition provider implements ``capabilities``, ``score``, ``acquire``,
and ``aclose`` and exposes a stable ``name``. Register providers with
``service.register(provider)``. Acquisition middleware uses the same
``(request, call_next)`` async shape as HTTP fetch middleware.

For an existing downloader with ``extract_info`` and ``download`` methods,
``DownloaderAcquisitionProvider`` supplies the provider machinery. Downloader
methods may return normal iterables, awaitable iterables, or async iterables.

.. code-block:: python

   from pydantic import BaseModel, Field
   from pyfetcher import (
       AcquisitionRequest,
       AcquisitionService,
       DownloaderAcquisitionProvider,
       DownloaderContext,
   )

   class CompanyOptions(BaseModel):
       quality: int = Field(default=80, ge=1, le=100)

   def build_downloader(context: DownloaderContext):
       options = CompanyOptions.model_validate(context.options)
       return CompanyDownloader(
           quality=options.quality,
           credentials=context.credentials,
       )

   provider = DownloaderAcquisitionProvider(
       "company_media",
       factory=build_downloader,
       url_patterns=("media.example.com", "*.media.example.com"),
       auto_score=90,
       options_model=CompanyOptions,
   )

   async with AcquisitionService(providers=[provider]) as service:
       result = await service.acquire(
           AcquisitionRequest(
               url="https://media.example.com/items/42",
               provider="company_media",
               provider_options={"company_media": {"quality": 90}},
           )
       )

Factories receive resolved credentials separately from serialized options and
produce request-scoped downloaders, which fetchkit closes after execution. Pass
a shared ``downloader`` instance instead when it owns a reusable pool; the
service closes that instance with the provider. ``options_model`` validates
configuration and publishes JSON Schema through
``ProviderCapabilities.option_schema`` for CLIs, APIs, and TypeScript clients.

Provider plugins
----------------

Separate distributions may publish an entry point in the
``fetchkit.acquisition.providers`` group. Loading is deliberately explicit:

.. code-block:: toml

   [project.entry-points."fetchkit.acquisition.providers"]
   company-media = "company_fetchkit:build_provider"

.. code-block:: python

   service = AcquisitionService()
   loaded = service.load_entry_points()

An entry point may expose a provider instance, provider class, or zero-argument
factory returning a complete acquisition provider. The CLI loads installed
plugins only when ``--load-provider-plugins`` is supplied. This avoids
executing third-party plugin code during an ordinary import or fetch.

Command line
------------

.. code-block:: bash

   pyfetcher acquire URL --metadata --provider yt-dlp
   pyfetcher acquire URL -d ./media --provider yt-dlp \
       --provider-option format='"bestvideo+bestaudio/best"'
   pyfetcher acquire URL -d ./images --provider gallery-dl --events
   pyfetcher acquire URL --provider company-media \
       --load-provider-plugins --provider-option quality=90
