"""Page document, selector, link, image, and collection tests."""

from __future__ import annotations

import pytest
from parsel import Selector
from pydantic import BaseModel

from pyfetcher.contracts import URL, FetchResponse
from pyfetcher.documents import (
    CollectionRule,
    GalleryRule,
    ImageRule,
    LinkRule,
    ModelExtractor,
    PageDocument,
    SelectorCardinalityError,
    SelectorError,
    SelectorFunctionRegistry,
    SelectorRule,
    extract_collection,
    extract_gallery,
    extract_images,
    extract_page_links,
    run_page_extractor,
)

HTML = """
<html>
  <head><title> Example gallery </title></head>
  <body>
    <nav><a href="/ignored">Ignored</a></nav>
    <section class="gallery">
      <div class="item" data-id="101">
        <a href="/view/1"><img src="/thumb/1.jpg"
          srcset="/medium/1.jpg 600w, /large/1.webp 1200w"
          width="240" height="160" alt="One"></a>
        <p class="caption"> First image </p>
      </div>
      <div class="item" data-id="102">
        <a href="/view/2"><img data-src="/thumb/2.webp" alt="Two"></a>
        <p class="caption"> Second image </p>
      </div>
      <a rel="next" href="/gallery/9/page/2?b=2&a=1">Next</a>
      <a rel="nofollow" href="/private">Private</a>
      <a href="https://outside.example/file.zip">Archive</a>
    </section>
  </body>
</html>
"""


class GallerySummary(BaseModel):
    title: str
    item_count: int


def test_page_document_adapts_fetch_response_and_caches_selector() -> None:
    response = FetchResponse(
        request_url="https://example.com/gallery/9/page/1",
        final_url="https://example.com/gallery/9/page/1",
        status_code=200,
        headers={"content-type": "text/html; charset=utf-8"},
        body=HTML.encode(),
        backend="httpx",
        elapsed_ms=1,
    )
    page = PageDocument.from_response(response)
    assert page.url == URL("https://example.com/gallery/9/page/1")
    assert page.css("title::text").get().strip() == "Example gallery"
    assert page.xpath("count(//div[@class='item'])").get() == "2.0"
    assert page.selector is page.selector


def test_page_document_reuses_native_selector_and_honors_html_base_url() -> None:
    class Response:
        url = "https://example.com/path/page"
        status = 200
        body = b'<base href="https://cdn.example/assets/"><a href="image.jpg">Image</a>'
        headers = {b"content-type": b"text/html; charset=utf-8"}
        encoding = "utf-8"
        selector = Selector(body=body, type="html", base_url=url)

    native = Response()
    page = PageDocument.from_response(native)
    assert page.selector is native.selector
    assert page.resolve_url("image.jpg") == URL("https://cdn.example/assets/image.jpg")


def test_selection_is_chainable_across_css_xpath_and_regex() -> None:
    page = PageDocument(HTML, url="https://example.com/gallery/9/page/1")
    items = page.css(".item")
    assert len(items) == 2
    assert items.xpath("@data-id").getall() == ["101", "102"]
    assert items.css(".caption::text").re(r"(First|Second)") == ["First", "Second"]
    assert items[0].attrib["data-id"] == "101"


async def test_page_document_accepts_sync_and_async_byte_sources() -> None:
    sync_page = PageDocument.from_stream(
        [b"<h1>", b"Sync</h1>"],
        url="https://example.com/",
        media_type="text/html",
    )
    assert sync_page.css("h1::text").get() == "Sync"

    async def chunks():
        yield b"<h1>"
        yield b"Async</h1>"

    async_page = await PageDocument.afrom_stream(
        chunks(),
        url="https://example.com/",
        media_type="text/html",
    )
    assert async_page.xpath("//h1/text()").get() == "Async"


def test_selector_rules_convert_values_and_enforce_cardinality() -> None:
    page = PageDocument(HTML, url="https://example.com/gallery/9/page/1")
    ids = SelectorRule(
        css=".item",
        output="attribute",
        attribute="data-id",
        value_type="int",
    )
    target = SelectorRule(
        xpath="//div[@class='item'][1]/a",
        output="attribute",
        attribute="href",
        value_type="url",
        cardinality="one",
    )
    assert ids.apply(page) == [101, 102]
    assert target.apply(page) == URL("https://example.com/view/1")
    with pytest.raises(SelectorCardinalityError, match="exactly one"):
        SelectorRule(css=".missing", cardinality="one").apply(page)


def test_selector_rules_allow_named_bespoke_transforms_and_converters() -> None:
    page = PageDocument(HTML, url="https://example.com/gallery/9/page/1")
    functions = SelectorFunctionRegistry()
    functions.register_transform("digits", lambda value: "".join(filter(str.isdigit, value)))
    functions.register_converter(
        "asset-id",
        lambda value, document: f"{document.url.host}:{value}" if document.url else value,
    )
    rule = SelectorRule(
        css=".item:first-child",
        output="attribute",
        attribute="data-id",
        transforms=("digits",),
        value_type="asset-id",
        cardinality="one",
    )

    assert rule.apply(page, functions=functions) == "example.com:101"
    assert "digits" in functions.transforms
    assert "asset-id" in functions.converters
    with pytest.raises(SelectorError, match="unknown selector transform"):
        SelectorRule(css="title", transforms=("missing",)).apply(page)


def test_model_extractor_shares_bespoke_selector_functions() -> None:
    functions = SelectorFunctionRegistry(
        transforms={"clean-title": lambda value: value.strip().removeprefix("Example ")}
    )
    extractor = ModelExtractor(
        GallerySummary,
        {
            "title": SelectorRule(
                css="title",
                output="text",
                transforms=("clean-title",),
                cardinality="one",
            ),
            "item_count": SelectorRule(
                xpath="count(//div[@class='item'])",
                value_type="int",
                cardinality="one",
            ),
        },
        functions=functions,
    )

    assert extractor(PageDocument(HTML)) == GallerySummary(title="gallery", item_count=2)


def test_collection_rules_share_bespoke_selector_functions() -> None:
    functions = SelectorFunctionRegistry(
        transforms={"prefix": lambda value: f"asset-{value.strip()}"}
    )
    collection = extract_collection(
        PageDocument(HTML, url="https://example.com/"),
        CollectionRule(
            item_css=".item",
            fields={
                "id": SelectorRule(
                    xpath="@data-id",
                    transforms=("prefix",),
                    cardinality="one",
                )
            },
        ),
        functions=functions,
    )

    assert [item.data["id"] for item in collection.items] == ["asset-101", "asset-102"]


async def test_model_and_async_function_extractors_are_typed() -> None:
    page = PageDocument(HTML, url="https://example.com/gallery/9/page/1")
    extractor = ModelExtractor(
        GallerySummary,
        {
            "title": SelectorRule(
                css="title",
                output="text",
                transforms=("normalize_whitespace",),
                cardinality="one",
            ),
            "item_count": SelectorRule(
                xpath="count(//div[@class='item'])",
                value_type="int",
                cardinality="one",
            ),
        },
    )
    assert extractor(page) == GallerySummary(title="Example gallery", item_count=2)

    async def title(document: PageDocument) -> str:
        return str(SelectorRule(css="title", output="text", cardinality="one").apply(document))

    assert await run_page_extractor(title, page) == " Example gallery "


def test_link_rules_filter_regions_patterns_domains_extensions_and_rel() -> None:
    page = PageDocument(HTML, url="https://example.com/gallery/9/page/1")
    links = extract_page_links(
        page,
        LinkRule(
            restrict_css=(".gallery",),
            allow=(r"/(view|gallery)/",),
            denied_extensions=("zip",),
            include_nofollow=False,
            canonicalize=True,
        ),
    )
    assert [str(link.url) for link in links] == [
        "https://example.com/view/1",
        "https://example.com/view/2",
        "https://example.com/gallery/9/page/2?a=1&b=2",
    ]
    assert all(not link.external for link in links)


def test_image_extraction_handles_lazy_sources_srcset_and_parent_links() -> None:
    page = PageDocument(HTML, url="https://example.com/gallery/9/page/1")
    images = extract_images(page)
    assert len(images) == 2
    assert images[0].dimensions is not None
    assert images[0].dimensions.width == 240
    assert str(images[0].best_url) == "https://example.com/large/1.webp"
    assert images[0].to_thumbnail_info().mime_type == "image/webp"
    assert str(images[0].parent_url) == "https://example.com/view/1"
    assert images[1].source_attribute == "data-src"


def test_xpath_image_rule_is_ergonomic() -> None:
    page = PageDocument(HTML, url="https://example.com/")
    images = extract_images(page, ImageRule(xpath="//div[@data-id='102']//img"))
    assert [image.alt for image in images] == ["Two"]


def test_gallery_and_general_collection_extraction() -> None:
    page = PageDocument(HTML, url="https://example.com/gallery/9/page/1")
    gallery = extract_gallery(
        page,
        GalleryRule(
            item_css=".item",
            title=SelectorRule(
                css=".caption", output="text", cardinality="first", transforms=("strip",)
            ),
            fields={
                "id": SelectorRule(
                    xpath=".",
                    output="attribute",
                    attribute="data-id",
                    cardinality="first",
                )
            },
            collection_title=SelectorRule(
                css="title", output="text", cardinality="one", transforms=("strip",)
            ),
            next_page=LinkRule(
                restrict_css=(".gallery",),
                allow=(r"/gallery/\d+/page/\d+",),
            ),
        ),
    )
    assert gallery.kind == "gallery"
    assert gallery.title == "Example gallery"
    assert [item.title for item in gallery.items] == ["First image", "Second image"]
    assert [str(item.target_url) for item in gallery.items] == [
        "https://example.com/view/1",
        "https://example.com/view/2",
    ]
    assert gallery.items[0].thumbnail is not None
    assert [item.data["id"] for item in gallery.items] == ["101", "102"]
    assert [str(url) for url in gallery.next_urls] == [
        "https://example.com/gallery/9/page/2?b=2&a=1"
    ]

    collection = extract_collection(
        page,
        CollectionRule(item_xpath="//div[@class='item']", images=ImageRule()),
    )
    assert len(collection.items) == 2
