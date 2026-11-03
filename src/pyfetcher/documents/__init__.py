"""Typed page documents, selectors, links, images, and collections."""

from pyfetcher.documents.collections import (
    CollectionItem,
    CollectionRule,
    ExtractedCollection,
    GalleryRule,
    ImageCandidate,
    ImageRule,
    SrcsetCandidate,
    extract_collection,
    extract_gallery,
    extract_images,
)
from pyfetcher.documents.links import ExtractedLink, LinkRule, extract_page_links
from pyfetcher.documents.page import PageDocument, PageRule
from pyfetcher.documents.selectors import (
    ModelExtractor,
    PageExtractor,
    Selection,
    SelectorCardinalityError,
    SelectorError,
    SelectorFunctionRegistry,
    SelectorRule,
    run_page_extractor,
)

__all__ = [
    "CollectionItem",
    "CollectionRule",
    "ExtractedCollection",
    "ExtractedLink",
    "GalleryRule",
    "ImageCandidate",
    "ImageRule",
    "LinkRule",
    "ModelExtractor",
    "PageDocument",
    "PageExtractor",
    "PageRule",
    "Selection",
    "SelectorCardinalityError",
    "SelectorError",
    "SelectorFunctionRegistry",
    "SelectorRule",
    "SrcsetCandidate",
    "extract_collection",
    "extract_gallery",
    "extract_images",
    "extract_page_links",
    "run_page_extractor",
]
