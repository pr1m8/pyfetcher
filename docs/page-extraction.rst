Typed Page Extraction
=====================

The ``pyfetcher.documents`` layer turns buffered HTML or XML into a reusable
document with CSS, XPath, regular-expression, link, image, and repeated-item
extraction. Install the standalone Parsel engine with:

.. code-block:: bash

   pip install 'fetchkit[selectors]'

This layer models extraction only. It does not require the crawler, job queue,
site configuration, WebPoet, or artifact-storage layers.

Page documents and selections
-----------------------------

Create a document directly or adapt a buffered fetchkit/Scrapy response. A
Scrapy response's existing selector is reused, while other responses are
parsed lazily once.

.. code-block:: python

   from pyfetcher import PageDocument

   page = PageDocument(html, url="https://example.com/gallery/42")

   title = page.css("h1::text").get()
   image_urls = page.xpath("//article//img/@src").getall()
   numeric_ids = page.css("[data-id]::attr(data-id)").re(r"\d+")

``PageDocument.from_stream`` and ``PageDocument.afrom_stream`` also accept the
common byte adapters, including paths, buffered responses, sync iterables, and
async iterables. Buffering remains explicit and can be bounded with
``max_bytes``.

Selections can be nested and can switch between CSS and XPath:

.. code-block:: python

   for item in page.css(".gallery-item"):
       caption = item.css(".caption").xpath("normalize-space(string(.))").get()

Serializable selector rules
---------------------------

``SelectorRule`` makes output shape and conversion explicit. Supported
cardinalities are ``one`` (exactly one), ``optional`` (zero or one), ``first``,
and ``many``. Values can be converted to strings, integers, floats, booleans,
URLs, or JSON.

.. code-block:: python

   from pyfetcher import SelectorRule

   title = SelectorRule(
       css="article h1",
       output="text",
       transforms=("normalize_whitespace",),
       cardinality="one",
   ).apply(page)

   page_number = SelectorRule(
       xpath="//meta[@name='page']/@content",
       value_type="int",
       cardinality="optional",
   ).apply(page)

``ModelExtractor`` maps named rules directly into a user-owned Pydantic model.
Plain synchronous or asynchronous functions are also valid typed page
extractors through ``run_page_extractor``.

.. code-block:: python

   from pydantic import BaseModel
   from pyfetcher import ModelExtractor

   class ArticleSummary(BaseModel):
       title: str
       tags: list[str]

   extract_article = ModelExtractor(
       ArticleSummary,
       {
           "title": SelectorRule(
               css="h1", output="text", cardinality="one",
           ),
           "tags": SelectorRule(
               css="a.tag::text", transforms=("strip",),
           ),
       },
   )

   article = extract_article(page)

Bespoke selector functions
---------------------------

Rules remain serializable even when a site needs custom cleanup or conversion.
Register functions by name in an application-owned
``SelectorFunctionRegistry`` and share it across rules or a ``ModelExtractor``.
Converters receive the source ``PageDocument`` as context.

.. code-block:: python

   from pyfetcher import ModelExtractor, SelectorFunctionRegistry, SelectorRule

   functions = SelectorFunctionRegistry()
   functions.register_transform(
       "currency-digits",
       lambda value: "".join(character for character in value if character.isdigit()),
   )
   functions.register_converter(
       "asset-key",
       lambda value, page: f"{page.url.host}:{value}",
   )

   asset_key = SelectorRule(
       css="[data-asset]",
       output="attribute",
       attribute="data-asset",
       transforms=("currency-digits",),
       value_type="asset-key",
       cardinality="one",
   ).apply(page, functions=functions)

Built-in transform names are ``strip``, ``normalize_whitespace``, ``lower``,
and ``upper``. Built-in value types are ``str``, ``int``, ``float``, ``bool``,
``url``, and ``json``. Unknown names fail when the rule executes, so a rule can
be serialized, queued, and later evaluated with the correct site-specific
function registry. For logic that does not fit a field rule, use an ordinary
typed synchronous or asynchronous page function with ``run_page_extractor``.

Link rules
----------

``LinkRule`` supports restricted CSS/XPath regions, URL allow/deny patterns,
domain and scheme controls, denied extensions, nofollow policy,
canonicalization, and stable deduplication.

.. code-block:: python

   from pyfetcher import LinkRule, extract_page_links

   links = extract_page_links(
       page,
       LinkRule(
           restrict_css=("article", ".pagination"),
           allow=(r"/gallery/\d+", r"/page/\d+"),
           deny=(r"/login",),
           denied_extensions=("zip", "pdf"),
           same_domain=True,
           canonicalize=True,
       ),
   )

Each result contains a validated ``URL``, link text, ``rel`` values,
internal/external status, nofollow status, and source tag/attribute.

Typed URL patterns
------------------

Regular expressions are not generally reversible, so matching and rendering
are separate and an explicit template enables the reverse operation.

.. code-block:: python

   from pydantic import BaseModel
   from pyfetcher import URLPattern

   class GalleryPage(BaseModel):
       gallery_id: int
       page: int = 1

   gallery_pages = URLPattern(
       "gallery.page",
       params_model=GalleryPage,
       hosts=("example.com",),
       path=r"/gallery/(?P<gallery_id>\d+)/page/(?P<page>\d+)",
       template="https://example.com/gallery/{gallery_id}/page/{page}",
   )

   params = gallery_pages.parse("https://example.com/gallery/42/page/3")
   next_url = gallery_pages.build(params.model_copy(update={"page": 4}))

Patterns match normalized scheme, host, path, and query components. Template
output is checked against the pattern by default.

Images, thumbnails, and collections
-----------------------------------

``extract_images`` understands ``src``, common lazy-loading attributes,
``srcset``, ``picture`` sources, declared dimensions, alternate text, and
ancestor links. ``ImageCandidate.to_thumbnail_info()`` bridges page-discovered
information into the canonical media model.

``CollectionRule`` extracts any repeated result shape. ``GalleryRule`` adds
useful link, image, and thumbnail defaults without introducing site or job
objects.

.. code-block:: python

   from pyfetcher import GalleryRule, LinkRule, SelectorRule, extract_gallery

   gallery = extract_gallery(
       page,
       GalleryRule(
           item_css=".gallery-item",
           title=SelectorRule(
               css=".caption",
               output="text",
               cardinality="first",
               transforms=("strip",),
           ),
           next_page=LinkRule(
               restrict_css=(".pagination",),
               allow=(r"/page/\d+",),
           ),
       ),
   )

   for item in gallery.items:
       print(item.target_url, item.thumbnail)

See ``examples/page_extraction.py`` for a complete offline example.
