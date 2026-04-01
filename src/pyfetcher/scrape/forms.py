"""HTML form extraction for :mod:`pyfetcher`.

Purpose:
    Parse ``<form>`` elements from HTML and extract their fields, making it
    easy to build form submission requests programmatically.

Examples:
    ::

        >>> html = '<form action="/login" method="post"><input name="user"/></form>'
        >>> forms = extract_forms(html, base_url="https://example.com")
        >>> forms[0].action
        'https://example.com/login'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True, slots=True)
class FormField:
    """A single form input field.

    Args:
        name: The field's ``name`` attribute.
        type: The field's ``type`` attribute (e.g. ``'text'``, ``'hidden'``).
        value: The field's default ``value`` attribute.
        options: For ``<select>`` elements, the list of ``<option>`` values.

    Examples:
        ::

            >>> field = FormField(name="user", type="text", value="")
            >>> field.name
            'user'
    """

    name: str
    type: str
    value: str
    options: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class FormData:
    """Parsed HTML form.

    Args:
        action: The resolved form action URL.
        method: The HTTP method (uppercased, e.g. ``'GET'``, ``'POST'``).
        fields: List of form fields.
        id: The form's ``id`` attribute, if present.
        name: The form's ``name`` attribute, if present.

    Examples:
        ::

            >>> form = FormData(action="https://example.com/login", method="POST", fields=[])
            >>> form.method
            'POST'
    """

    action: str
    method: str
    fields: list[FormField]
    id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Convert form fields to a submission dictionary.

        Returns a dictionary mapping field names to their default values,
        suitable for use as POST data or query parameters.

        Returns:
            A dictionary of field names to values.

        Examples:
            ::

                >>> form = FormData(
                ...     action="/submit", method="POST",
                ...     fields=[FormField(name="q", type="text", value="hello")],
                ... )
                >>> form.to_dict()
                {'q': 'hello'}
        """
        return {f.name: f.value for f in self.fields if f.name}


def extract_forms(html: str, *, base_url: str | None = None) -> list[FormData]:
    """Extract all forms from HTML.

    Parses ``<form>`` elements and their input fields (``<input>``,
    ``<textarea>``, ``<select>``) to produce structured form data.

    Args:
        html: Raw HTML string to parse.
        base_url: Base URL for resolving relative form action URLs.

    Returns:
        A list of :class:`FormData` objects.

    Examples:
        ::

            >>> html = '<form action="/search"><input name="q" value=""/></form>'
            >>> forms = extract_forms(html, base_url="https://example.com")
            >>> forms[0].action
            'https://example.com/search'
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[FormData] = []

    for form in soup.find_all("form"):
        if not isinstance(form, Tag):
            continue

        action = form.get("action", "")
        if base_url and action:
            action = urljoin(base_url, str(action))
        elif base_url:
            action = base_url

        method = str(form.get("method", "GET")).upper()
        fields: list[FormField] = []

        for inp in form.find_all("input"):
            if not isinstance(inp, Tag):
                continue
            name = str(inp.get("name", ""))
            fields.append(
                FormField(
                    name=name,
                    type=str(inp.get("type", "text")),
                    value=str(inp.get("value", "")),
                )
            )

        for textarea in form.find_all("textarea"):
            if not isinstance(textarea, Tag):
                continue
            name = str(textarea.get("name", ""))
            fields.append(
                FormField(
                    name=name,
                    type="textarea",
                    value=textarea.get_text(),
                )
            )

        for sel in form.find_all("select"):
            if not isinstance(sel, Tag):
                continue
            name = str(sel.get("name", ""))
            options = []
            selected_value = ""
            for option in sel.find_all("option"):
                if isinstance(option, Tag):
                    val = str(option.get("value", option.get_text(strip=True)))
                    options.append(val)
                    if option.get("selected") is not None:
                        selected_value = val
            if not selected_value and options:
                selected_value = options[0]
            fields.append(
                FormField(
                    name=name,
                    type="select",
                    value=selected_value,
                    options=options,
                )
            )

        results.append(
            FormData(
                action=str(action),
                method=method,
                fields=fields,
                id=form.get("id"),
                name=form.get("name"),
            )
        )

    return results
