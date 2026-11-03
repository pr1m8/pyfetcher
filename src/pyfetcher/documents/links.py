"""Typed, rule-driven link extraction from page documents."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, field_validator

from pyfetcher.contracts import URL
from pyfetcher.documents.page import PageDocument
from pyfetcher.documents.selectors import Selection


class ExtractedLink(BaseModel):
    """One normalized link with document-level provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: URL
    text: str = ""
    rel: tuple[str, ...] = ()
    external: bool = False
    nofollow: bool = False
    source_tag: str
    source_attribute: str


class LinkRule(BaseModel):
    """Serializable allow/deny and document-region policy for links."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tags: tuple[str, ...] = ("a", "area")
    attributes: tuple[str, ...] = ("href",)
    restrict_css: tuple[str, ...] = ()
    restrict_xpath: tuple[str, ...] = ()
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ()
    denied_domains: tuple[str, ...] = ()
    allowed_schemes: tuple[str, ...] = ("http", "https")
    denied_extensions: tuple[str, ...] = ()
    same_domain: bool = False
    include_fragments: bool = False
    include_nofollow: bool = True
    canonicalize: bool = False
    unique: bool = True

    @field_validator(
        "tags",
        "attributes",
        "allowed_domains",
        "denied_domains",
        "allowed_schemes",
        "denied_extensions",
    )
    @classmethod
    def _normalize_tokens(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(value.strip().lower().lstrip(".") for value in values if value.strip())

    @field_validator("allow", "deny")
    @classmethod
    def _compile_regexes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            re.compile(value)
        return values


def _scopes(page: PageDocument, rule: LinkRule) -> tuple[Selection, ...]:
    scopes: list[Selection] = []
    for query in rule.restrict_css:
        scopes.extend(page.css(query))
    for query in rule.restrict_xpath:
        scopes.extend(page.xpath(query))
    if scopes:
        return tuple(scopes)
    return (Selection(page.selector, page),)


def _domain_matches(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _accepted(url: URL, page: PageDocument, rule: LinkRule) -> bool:
    value = str(url)
    host = (url.host or "").lower().rstrip(".")
    if rule.allowed_schemes and url.scheme.lower() not in rule.allowed_schemes:
        return False
    if rule.allowed_domains and not _domain_matches(host, rule.allowed_domains):
        return False
    if rule.denied_domains and _domain_matches(host, rule.denied_domains):
        return False
    if rule.same_domain and (page.url is None or host != (page.url.host or "").lower()):
        return False
    if rule.allow and not any(re.search(pattern, value) for pattern in rule.allow):
        return False
    if rule.deny and any(re.search(pattern, value) for pattern in rule.deny):
        return False
    extension = PurePosixPath(url.split().path).suffix.lower().lstrip(".")
    return not extension or extension not in rule.denied_extensions


def extract_page_links(
    page: PageDocument,
    rule: LinkRule | None = None,
) -> tuple[ExtractedLink, ...]:
    """Extract normalized links from selected document regions."""
    policy = rule or LinkRule()
    results: list[ExtractedLink] = []
    seen: set[str] = set()
    page_host = (page.url.host or "").lower() if page.url is not None else ""

    for scope in _scopes(page, policy):
        for tag in policy.tags:
            for attribute in policy.attributes:
                for node in scope.css(f"{tag}[{attribute}]"):
                    raw = node.attrib.get(attribute, "").strip()
                    if not raw or raw.lower().startswith(
                        ("javascript:", "mailto:", "tel:", "data:")
                    ):
                        continue
                    if raw.startswith("#") and not policy.include_fragments:
                        continue
                    try:
                        url = page.resolve_url(raw)
                    except (TypeError, ValueError):
                        continue
                    if not policy.include_fragments:
                        url = url.with_fragment(None)
                    if policy.canonicalize:
                        url = url.canonicalize(keep_fragment=policy.include_fragments)
                    if not _accepted(url, page, policy):
                        continue
                    rel = tuple(part.lower() for part in node.attrib.get("rel", "").split() if part)
                    if "nofollow" in rel and not policy.include_nofollow:
                        continue
                    key = str(url)
                    if policy.unique and key in seen:
                        continue
                    seen.add(key)
                    text = node.xpath("normalize-space(string(.))").get("") or ""
                    results.append(
                        ExtractedLink(
                            url=url,
                            text=text,
                            rel=rel,
                            external=bool(page_host and (url.host or "").lower() != page_host),
                            nofollow="nofollow" in rel,
                            source_tag=tag,
                            source_attribute=attribute,
                        )
                    )
    return tuple(results)


__all__ = ["ExtractedLink", "LinkRule", "extract_page_links"]
