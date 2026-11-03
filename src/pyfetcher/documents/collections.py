"""Reusable image, thumbnail, gallery, and collection extraction."""

from __future__ import annotations

import mimetypes
import re
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, computed_field, model_validator

from pyfetcher.contracts import URL
from pyfetcher.documents.links import LinkRule, extract_page_links
from pyfetcher.documents.page import PageDocument
from pyfetcher.documents.selectors import (
    Selection,
    SelectorCardinalityError,
    SelectorFunctionRegistry,
    SelectorRule,
)
from pyfetcher.media import PixelDimensions, ThumbnailInfo


class SrcsetCandidate(BaseModel):
    """One resolved URL and descriptor from an HTML ``srcset`` value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: URL
    width: int | None = Field(default=None, gt=0)
    density: float | None = Field(default=None, gt=0)
    media_type: str | None = None


class ImageCandidate(BaseModel):
    """An image reference discovered in HTML before the file is inspected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: URL
    alt: str | None = None
    title: str | None = None
    dimensions: PixelDimensions | None = None
    media_type: str | None = None
    loading: str | None = None
    parent_url: URL | None = None
    source_tag: str = "img"
    source_attribute: str = "src"
    srcset: tuple[SrcsetCandidate, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @computed_field
    @property
    def best_url(self) -> URL:
        """Return the largest described source, falling back to ``url``."""
        if not self.srcset:
            return self.url
        return max(
            self.srcset,
            key=lambda item: (item.width or 0, item.density or 0.0),
        ).url

    def to_thumbnail_info(self) -> ThumbnailInfo:
        """Convert page-discovered information into canonical media metadata."""
        best_source = (
            max(
                self.srcset,
                key=lambda item: (item.width or 0, item.density or 0.0),
            )
            if self.srcset
            else None
        )
        best = best_source.url if best_source else self.url
        extension = PurePosixPath(best.split().path).suffix.lower().lstrip(".") or None
        return ThumbnailInfo(
            url=str(best),
            dimensions=self.dimensions,
            mime_type=(
                (best_source.media_type if best_source else None)
                or mimetypes.guess_type(str(best))[0]
                or self.media_type
            ),
            extension=extension,
            metadata={
                "alt": self.alt,
                "title": self.title,
                "loading": self.loading,
                "parent_url": str(self.parent_url) if self.parent_url else None,
                "source_attribute": self.source_attribute,
            },
        )


class ImageRule(BaseModel):
    """Serializable HTML image and lazy-loading discovery policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    css: str | None = "img"
    xpath: str | None = None
    source_attributes: tuple[str, ...] = (
        "src",
        "data-src",
        "data-original",
        "data-lazy-src",
    )
    srcset_attributes: tuple[str, ...] = ("srcset", "data-srcset")
    include_picture_sources: bool = True
    resolve_parent_link: bool = True
    unique: bool = True

    @model_validator(mode="before")
    @classmethod
    def _prefer_explicit_xpath(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("xpath") is not None and "css" not in value:
            return {**value, "css": None}
        return value

    @model_validator(mode="after")
    def _validate_selector(self) -> ImageRule:
        if (self.css is None) == (self.xpath is None):
            raise ValueError("exactly one of css or xpath is required")
        return self


def _positive_int(value: str | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", value)
    parsed = int(match.group()) if match else 0
    return parsed or None


def _tag(selection: Selection) -> str:
    root = getattr(selection.raw, "root", None)
    return str(getattr(root, "tag", "img"))


def _srcset(
    page: PageDocument,
    raw: str,
    *,
    media_type: str | None = None,
) -> Iterable[SrcsetCandidate]:
    for entry in raw.split(","):
        parts = entry.strip().rsplit(maxsplit=1)
        if not parts:
            continue
        source = parts[0]
        descriptor = parts[1].lower() if len(parts) == 2 else ""
        width = _positive_int(descriptor) if descriptor.endswith("w") else None
        density = None
        if descriptor.endswith("x"):
            try:
                density = float(descriptor[:-1])
            except ValueError:
                density = None
        try:
            url = page.resolve_url(source)
        except (TypeError, ValueError):
            continue
        yield SrcsetCandidate(
            url=url,
            width=width,
            density=density,
            media_type=media_type,
        )


def _nodes(page: PageDocument, rule: ImageRule, within: Selection | None) -> Selection:
    root: PageDocument | Selection = within or page
    return root.css(rule.css) if rule.css is not None else root.xpath(cast(str, rule.xpath))


def extract_images(
    page: PageDocument,
    rule: ImageRule | None = None,
    *,
    within: Selection | None = None,
) -> tuple[ImageCandidate, ...]:
    """Extract normal, responsive, and common lazy-loaded image candidates."""
    policy = rule or ImageRule()
    results: list[ImageCandidate] = []
    seen: set[str] = set()
    for node in _nodes(page, policy, within):
        sources: list[SrcsetCandidate] = []
        for attribute in policy.srcset_attributes:
            sources.extend(_srcset(page, node.attrib.get(attribute, "")))
        if policy.include_picture_sources:
            for source_node in node.xpath("ancestor::picture[1]/source"):
                media_type = source_node.attrib.get("type")
                for attribute in policy.srcset_attributes:
                    sources.extend(
                        _srcset(
                            page,
                            source_node.attrib.get(attribute, ""),
                            media_type=media_type,
                        )
                    )

        raw_url = ""
        source_attribute = "src"
        for attribute in policy.source_attributes:
            raw_url = node.attrib.get(attribute, "").strip()
            if raw_url:
                source_attribute = attribute
                break
        if not raw_url and sources:
            raw_url = str(max(sources, key=lambda item: (item.width or 0, item.density or 0)).url)
            source_attribute = "srcset"
        if not raw_url:
            continue
        try:
            url = page.resolve_url(raw_url)
        except (TypeError, ValueError):
            continue
        key = str(url)
        if policy.unique and key in seen:
            continue
        seen.add(key)
        width = _positive_int(node.attrib.get("width"))
        height = _positive_int(node.attrib.get("height"))
        parent_url = None
        if policy.resolve_parent_link:
            parent = node.xpath("ancestor::a[1]/@href").get()
            if parent:
                try:
                    parent_url = page.resolve_url(parent)
                except (TypeError, ValueError):
                    parent_url = None
        results.append(
            ImageCandidate(
                url=url,
                alt=node.attrib.get("alt") or None,
                title=node.attrib.get("title") or None,
                dimensions=(
                    PixelDimensions(width=width, height=height)
                    if width is not None and height is not None
                    else None
                ),
                media_type=node.attrib.get("type") or mimetypes.guess_type(str(url))[0],
                loading=node.attrib.get("loading") or None,
                parent_url=parent_url,
                source_tag=_tag(node),
                source_attribute=source_attribute,
                srcset=tuple(sources),
            )
        )
    return tuple(results)


class CollectionItem(BaseModel):
    """One ordered, typed item extracted from a repeated page region."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: int = Field(ge=0)
    target_url: URL | None = None
    title: str | None = None
    caption: str | None = None
    images: tuple[ImageCandidate, ...] = ()
    thumbnail: ThumbnailInfo | None = None
    data: dict[str, JsonValue] = Field(default_factory=dict)


class CollectionRule(BaseModel):
    """Serializable repeated-item extraction recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = "collection"
    item_css: str | None = None
    item_xpath: str | None = None
    target_url: SelectorRule | None = None
    title: SelectorRule | None = None
    caption: SelectorRule | None = None
    images: ImageRule | None = None
    fields: dict[str, SelectorRule] = Field(default_factory=dict)
    collection_title: SelectorRule | None = None
    next_page: LinkRule | None = None
    unique_by_url: bool = True

    @model_validator(mode="after")
    def _validate_item_selector(self) -> CollectionRule:
        if (self.item_css is None) == (self.item_xpath is None):
            raise ValueError("exactly one of item_css or item_xpath is required")
        if not self.kind.strip():
            raise ValueError("collection kind cannot be empty")
        return self


class GalleryRule(CollectionRule):
    """Collection recipe with gallery-oriented defaults."""

    kind: Literal["gallery"] = "gallery"
    target_url: SelectorRule | None = Field(
        default_factory=lambda: SelectorRule(
            css="a[href]",
            output="attribute",
            attribute="href",
            value_type="url",
            cardinality="first",
        )
    )
    images: ImageRule | None = Field(default_factory=ImageRule)


class ExtractedCollection(BaseModel):
    """Provider-neutral collection result from one page."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    source_url: URL | None = None
    title: str | None = None
    items: tuple[CollectionItem, ...] = ()
    next_urls: tuple[URL, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


def _json(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, URL):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return str(value)


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        if len(value) > 1:
            raise SelectorCardinalityError(
                "collection scalar field received multiple selector values"
            )
        return str(value[0]) if value else None
    return str(value)


def _url(value: object, page: PageDocument) -> URL | None:
    if value is None:
        return None
    if isinstance(value, list):
        if len(value) > 1:
            raise SelectorCardinalityError("collection URL field received multiple selector values")
        value = value[0] if value else None
    if value is None:
        return None
    return value if isinstance(value, URL) else page.resolve_url(value)


def extract_collection(
    page: PageDocument,
    rule: CollectionRule,
    *,
    functions: SelectorFunctionRegistry | None = None,
) -> ExtractedCollection:
    """Extract a gallery, playlist, result set, or other repeated collection."""
    selected = (
        page.css(rule.item_css)
        if rule.item_css is not None
        else page.xpath(cast(str, rule.item_xpath))
    )
    items: list[CollectionItem] = []
    seen: set[str] = set()
    for node in selected:
        target = (
            _url(rule.target_url.apply(node, functions=functions), page)
            if rule.target_url
            else None
        )
        if rule.unique_by_url and target is not None:
            key = str(target)
            if key in seen:
                continue
            seen.add(key)
        images = extract_images(page, rule.images, within=node) if rule.images else ()
        thumbnail_source = (
            max(
                images,
                key=lambda image: max(
                    [
                        image.dimensions.width if image.dimensions else 0,
                        *(source.width or 0 for source in image.srcset),
                    ]
                ),
            )
            if images
            else None
        )
        thumbnail = thumbnail_source.to_thumbnail_info() if thumbnail_source else None
        data = {
            name: _json(field.apply(node, functions=functions))
            for name, field in rule.fields.items()
        }
        items.append(
            CollectionItem(
                position=len(items),
                target_url=target,
                title=_text(rule.title.apply(node, functions=functions)) if rule.title else None,
                caption=(
                    _text(rule.caption.apply(node, functions=functions)) if rule.caption else None
                ),
                images=images,
                thumbnail=thumbnail,
                data=data,
            )
        )
    next_urls = (
        tuple(link.url for link in extract_page_links(page, rule.next_page))
        if rule.next_page
        else ()
    )
    return ExtractedCollection(
        kind=rule.kind.strip().lower().replace(" ", "_"),
        source_url=page.url,
        title=(
            _text(rule.collection_title.apply(page, functions=functions))
            if rule.collection_title
            else None
        ),
        items=tuple(items),
        next_urls=next_urls,
    )


def extract_gallery(
    page: PageDocument,
    rule: GalleryRule,
    *,
    functions: SelectorFunctionRegistry | None = None,
) -> ExtractedCollection:
    """Extract a gallery using collection semantics and image defaults."""
    return extract_collection(page, rule, functions=functions)


__all__ = [
    "CollectionItem",
    "CollectionRule",
    "ExtractedCollection",
    "GalleryRule",
    "ImageCandidate",
    "ImageRule",
    "SrcsetCandidate",
    "extract_collection",
    "extract_gallery",
    "extract_images",
]
