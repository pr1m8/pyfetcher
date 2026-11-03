"""Example: typed selectors, URL patterns, and gallery extraction.

Run with:
    python examples/page_extraction.py

Requires:
    pip install 'fetchkit[selectors]'
"""

from __future__ import annotations

from pydantic import BaseModel

from pyfetcher import (
    GalleryRule,
    LinkRule,
    ModelExtractor,
    PageDocument,
    SelectorFunctionRegistry,
    SelectorRule,
    URLPattern,
    extract_gallery,
)

HTML = """
<html>
  <head><title>Landscape collection</title></head>
  <body>
    <section class="gallery">
      <figure>
        <a href="/photo/101">
          <img src="/thumb/101.jpg" srcset="/large/101.webp 1200w" alt="Canyon">
        </a>
        <figcaption>Red canyon</figcaption>
      </figure>
      <figure>
        <a href="/photo/102"><img data-src="/thumb/102.webp" alt="Lake"></a>
        <figcaption>Mountain lake</figcaption>
      </figure>
    </section>
    <nav class="pages"><a href="/gallery/7/page/2">Next</a></nav>
  </body>
</html>
"""


class PageSummary(BaseModel):
    """Application-owned extracted item type."""

    title: str
    captions: list[str]


class GalleryPage(BaseModel):
    """Typed parameters captured from gallery URLs."""

    gallery_id: int
    page: int


def main() -> None:
    """Run a complete extraction without network access."""
    page = PageDocument(HTML, url="https://example.com/gallery/7/page/1")
    functions = SelectorFunctionRegistry(
        transforms={"title-case": lambda value: value.strip().title()}
    )
    summary = ModelExtractor(
        PageSummary,
        {
            "title": SelectorRule(
                css="title",
                output="text",
                cardinality="one",
                transforms=("title-case",),
            ),
            "captions": SelectorRule(
                css="figcaption",
                output="text",
                transforms=("strip",),
            ),
        },
        functions=functions,
    )(page)

    gallery = extract_gallery(
        page,
        GalleryRule(
            item_css="figure",
            title=SelectorRule(
                css="figcaption",
                output="text",
                cardinality="first",
                transforms=("strip",),
            ),
            next_page=LinkRule(
                restrict_css=(".pages",),
                allow=(r"/gallery/\d+/page/\d+",),
            ),
        ),
    )

    pages = URLPattern(
        "gallery.page",
        params_model=GalleryPage,
        hosts=("example.com",),
        path=r"/gallery/(?P<gallery_id>\d+)/page/(?P<page>\d+)",
        template="https://example.com/gallery/{gallery_id}/page/{page}",
    )
    current = pages.parse(page.url)

    print(summary.model_dump())
    print([str(item.thumbnail.url) for item in gallery.items if item.thumbnail])
    print([str(url) for url in gallery.next_urls])
    print(pages.build(current.model_copy(update={"page": current.page + 1})))


if __name__ == "__main__":
    main()
