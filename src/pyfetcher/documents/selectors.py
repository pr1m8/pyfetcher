"""Chainable selections and serializable typed selector rules."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Awaitable, Iterator, Mapping
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, JsonValue, model_validator

if False:  # pragma: no cover - typing-only cycle guard
    from pyfetcher.documents.page import PageDocument

type Cardinality = Literal["one", "optional", "first", "many"]
type SelectorOutput = Literal["auto", "text", "html", "attribute"]
type BuiltinValueType = Literal["str", "int", "float", "bool", "url", "json"]
type BuiltinTransformName = Literal["strip", "normalize_whitespace", "lower", "upper"]
type ValueType = str
type TransformName = str


class SelectorError(ValueError):
    """Base error for declarative selector evaluation."""


class SelectorCardinalityError(SelectorError):
    """Raised when selector matches violate an explicit cardinality."""


class SelectorTransform(Protocol):
    """String-to-string cleanup function used by selector rules."""

    def __call__(self, value: str) -> str: ...


class SelectorConverter(Protocol):
    """Value conversion function with access to the source page."""

    def __call__(self, value: str, document: PageDocument) -> object: ...


class Selection:
    """Small, dependency-neutral wrapper around a Parsel/Scrapy selection."""

    def __init__(self, value: object, document: PageDocument) -> None:
        self._value = value
        self.document = document

    @property
    def raw(self) -> object:
        """Return the underlying Parsel or Scrapy selector value."""
        return self._value

    @property
    def attrib(self) -> dict[str, str]:
        """Return attributes from the first selected node."""
        values = getattr(self._value, "attrib", {})
        return {str(key): str(value) for key, value in dict(values).items()}

    def css(self, query: str) -> Selection:
        """Apply a CSS selector within every selected node."""
        return Selection(self._value.css(query), self.document)  # type: ignore[union-attr]

    def xpath(
        self,
        query: str,
        namespaces: Mapping[str, str] | None = None,
        **variables: object,
    ) -> Selection:
        """Apply XPath within every selected node."""
        value = self._value.xpath(  # type: ignore[union-attr]
            query,
            namespaces=namespaces,
            **variables,
        )
        return Selection(value, self.document)

    def get(self, default: str | None = None) -> str | None:
        """Return the first serialized match."""
        return cast(str | None, self._value.get(default=default))  # type: ignore[union-attr]

    def getall(self) -> list[str]:
        """Return every serialized match."""
        return list(self._value.getall())  # type: ignore[union-attr]

    def re(self, pattern: str | re.Pattern[str]) -> list[str]:
        """Extract regular-expression matches from selected values."""
        return list(self._value.re(pattern))  # type: ignore[union-attr]

    def re_first(
        self,
        pattern: str | re.Pattern[str],
        default: str | None = None,
    ) -> str | None:
        """Return the first regular-expression result."""
        return cast(
            str | None,
            self._value.re_first(pattern, default=default),  # type: ignore[union-attr]
        )

    def __len__(self) -> int:
        return len(self._value)  # type: ignore[arg-type]

    def __bool__(self) -> bool:
        return bool(self._value)

    def __iter__(self) -> Iterator[Selection]:
        for item in self._value:  # type: ignore[union-attr]
            yield Selection(item, self.document)

    def __getitem__(self, index: int | slice) -> Selection:
        return Selection(self._value[index], self.document)  # type: ignore[index]


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _convert_int(value: str, _document: PageDocument) -> int:
    parsed = float(value.replace(",", ""))
    if not parsed.is_integer():
        raise ValueError("number is not integral")
    return int(parsed)


def _convert_bool(value: str, _document: PageDocument) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("value is not a recognized boolean")


class SelectorFunctionRegistry:
    """Application-owned named selector transforms and value converters.

    Built-in functions are loaded by default. Custom names keep
    :class:`SelectorRule` serializable while allowing application-specific
    cleanup, parsing, and typed conversion at execution time.
    """

    def __init__(
        self,
        *,
        transforms: Mapping[str, SelectorTransform] | None = None,
        converters: Mapping[str, SelectorConverter] | None = None,
        include_builtins: bool = True,
    ) -> None:
        self._transforms: dict[str, SelectorTransform] = (
            {
                "strip": str.strip,
                "normalize_whitespace": _normalize_space,
                "lower": str.lower,
                "upper": str.upper,
            }
            if include_builtins
            else {}
        )
        self._converters: dict[str, SelectorConverter] = (
            {
                "str": lambda value, _document: value,
                "int": _convert_int,
                "float": lambda value, _document: float(value),
                "bool": _convert_bool,
                "url": lambda value, document: document.resolve_url(value),
                "json": lambda value, _document: cast(object, json.loads(value)),
            }
            if include_builtins
            else {}
        )
        for name, function in (transforms or {}).items():
            self.register_transform(name, function, replace=True)
        for name, function in (converters or {}).items():
            self.register_converter(name, function, replace=True)

    @property
    def transforms(self) -> tuple[str, ...]:
        """Return registered transform names in lookup order."""
        return tuple(self._transforms)

    @property
    def converters(self) -> tuple[str, ...]:
        """Return registered converter names in lookup order."""
        return tuple(self._converters)

    def register_transform(
        self,
        name: str,
        function: SelectorTransform,
        *,
        replace: bool = False,
    ) -> None:
        """Register a named string-to-string transform."""
        normalized = name.strip()
        if not normalized:
            raise ValueError("selector transform name cannot be empty")
        if normalized in self._transforms and not replace:
            raise ValueError(f"selector transform {normalized!r} is already registered")
        self._transforms[normalized] = function

    def register_converter(
        self,
        name: str,
        function: SelectorConverter,
        *,
        replace: bool = False,
    ) -> None:
        """Register a named value converter with page context."""
        normalized = name.strip()
        if not normalized:
            raise ValueError("selector converter name cannot be empty")
        if normalized in self._converters and not replace:
            raise ValueError(f"selector converter {normalized!r} is already registered")
        self._converters[normalized] = function

    def transform(self, name: str, value: str) -> str:
        """Run one named transform and require a string result."""
        try:
            function = self._transforms[name]
        except KeyError as exc:
            raise SelectorError(f"unknown selector transform {name!r}") from exc
        try:
            result = function(value)
        except Exception as exc:
            raise SelectorError(f"selector transform {name!r} failed for {value!r}") from exc
        if not isinstance(result, str):
            raise SelectorError(f"selector transform {name!r} must return str")
        return result

    def convert(self, name: str, value: str, document: PageDocument) -> object:
        """Run one named converter with page context."""
        try:
            function = self._converters[name]
        except KeyError as exc:
            raise SelectorError(f"unknown selector value type {name!r}") from exc
        try:
            return function(value, document)
        except Exception as exc:
            raise SelectorError(f"cannot convert {value!r} to {name}") from exc


_DEFAULT_SELECTOR_FUNCTIONS = SelectorFunctionRegistry()


class SelectorRule(BaseModel):
    """Serializable CSS/XPath extraction, conversion, and cardinality policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    css: str | None = None
    xpath: str | None = None
    output: SelectorOutput = "auto"
    attribute: str | None = None
    regex: str | None = None
    regex_group: int | str = 0
    transforms: tuple[TransformName, ...] = ()
    value_type: ValueType = "str"
    cardinality: Cardinality = "many"
    default: JsonValue = None

    @model_validator(mode="after")
    def _validate_rule(self) -> SelectorRule:
        if (self.css is None) == (self.xpath is None):
            raise ValueError("exactly one of css or xpath is required")
        if self.output == "attribute" and not self.attribute:
            raise ValueError("attribute output requires an attribute name")
        if self.output != "attribute" and self.attribute is not None:
            raise ValueError("attribute is only valid with attribute output")
        if self.attribute and re.fullmatch(r"[A-Za-z_:][-A-Za-z0-9_:.]*", self.attribute) is None:
            raise ValueError("attribute contains unsupported characters")
        if self.cardinality in {"one", "optional"} and self.default is not None:
            raise ValueError("defaults are only supported by first cardinality")
        if self.regex is not None:
            re.compile(self.regex)
        if any(not name.strip() for name in self.transforms):
            raise ValueError("selector transform names cannot be empty")
        if not self.value_type.strip():
            raise ValueError("selector value type cannot be empty")
        return self

    def _selection(self, root: PageDocument | Selection) -> Selection:
        return root.css(self.css) if self.css is not None else root.xpath(cast(str, self.xpath))

    def values(
        self,
        root: PageDocument | Selection,
        *,
        functions: SelectorFunctionRegistry | None = None,
    ) -> list[object]:
        """Return all converted values before cardinality is applied."""
        registry = functions or _DEFAULT_SELECTOR_FUNCTIONS
        selection = self._selection(root)
        if self.output == "text":
            selection = selection.xpath("string(.)")
        elif self.output == "attribute":
            selection = selection.xpath(f"@{self.attribute}")
        raw = selection.getall()
        processed: list[str] = []
        pattern = re.compile(self.regex) if self.regex is not None else None
        for value in raw:
            for transform in self.transforms:
                value = registry.transform(transform, value)
            if pattern is not None:
                match = pattern.search(value)
                if match is None:
                    continue
                try:
                    value = match.group(self.regex_group)
                except (IndexError, KeyError) as exc:
                    raise SelectorError(f"regex group {self.regex_group!r} is not defined") from exc
                if value is None:
                    continue
            processed.append(value)
        document = root.document if isinstance(root, Selection) else root
        return [registry.convert(self.value_type, value, document) for value in processed]

    def apply(
        self,
        root: PageDocument | Selection,
        *,
        functions: SelectorFunctionRegistry | None = None,
    ) -> object:
        """Extract values and enforce the configured cardinality."""
        values = self.values(root, functions=functions)
        if self.cardinality == "many":
            return values
        if self.cardinality == "first":
            return values[0] if values else self.default
        if self.cardinality == "optional":
            if len(values) > 1:
                raise SelectorCardinalityError(f"optional selector matched {len(values)} values")
            return values[0] if values else None
        if len(values) != 1:
            raise SelectorCardinalityError(
                f"one selector expected exactly one value, found {len(values)}"
            )
        return values[0]


class PageExtractor[ResultT](Protocol):
    """Typed sync-or-async page extraction function contract."""

    def __call__(self, page: PageDocument) -> ResultT | Awaitable[ResultT]: ...


async def run_page_extractor[ResultT](
    extractor: PageExtractor[ResultT],
    page: PageDocument,
) -> ResultT:
    """Run a synchronous or asynchronous typed page extractor."""
    value = extractor(page)
    if inspect.isawaitable(value):
        value = await value
    return cast(ResultT, value)


class ModelExtractor[ModelT: BaseModel]:
    """Build a typed Pydantic item from named selector rules."""

    def __init__(
        self,
        model: type[ModelT],
        fields: Mapping[str, SelectorRule],
        *,
        name: str | None = None,
        functions: SelectorFunctionRegistry | None = None,
    ) -> None:
        self.model = model
        self.fields = dict(fields)
        self.name = name or f"{model.__module__}.{model.__qualname__}"
        self.functions = functions

    def __call__(self, page: PageDocument) -> ModelT:
        values = {
            name: rule.apply(page, functions=self.functions) for name, rule in self.fields.items()
        }
        return self.model.model_validate(values)


__all__ = [
    "Cardinality",
    "BuiltinTransformName",
    "BuiltinValueType",
    "ModelExtractor",
    "PageExtractor",
    "Selection",
    "SelectorCardinalityError",
    "SelectorError",
    "SelectorOutput",
    "SelectorConverter",
    "SelectorFunctionRegistry",
    "SelectorRule",
    "SelectorTransform",
    "TransformName",
    "ValueType",
    "run_page_extractor",
]
