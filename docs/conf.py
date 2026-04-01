"""Sphinx configuration for fetchkit (pyfetcher)."""

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "fetchkit"
copyright = "2026, Will"
author = "Will"
release = "0.3.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinxcontrib.mermaid",
    "sphinx_design",
]

mermaid_version = "11"
mermaid_init_js = "mermaid.initialize({startOnLoad:true, theme:'neutral'});"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_static_path = ["_static"]
html_title = "fetchkit"
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#4A90D9",
        "color-brand-content": "#7B68EE",
        "color-admonition-background": "rgba(74, 144, 217, 0.08)",
        "color-card-background": "rgba(74, 144, 217, 0.04)",
    },
    "dark_css_variables": {
        "color-brand-primary": "#6CB4FF",
        "color-brand-content": "#A78BFA",
        "color-admonition-background": "rgba(108, 180, 255, 0.12)",
        "color-card-background": "rgba(108, 180, 255, 0.06)",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/pr1m8/pyfetcher",
            "html": '<svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>',
            "class": "",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/fetchkit/",
            "html": '<svg stroke="currentColor" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0L1.75 6v12L12 24l10.25-6V6zm-1.775 18l-4.1-2.4V9.5l4.1 2.4zm.7-7.3L6.65 8.1l4.1-2.4 4.25 2.6zm5.225 5L12 18l-.025-6.1 4.175-2.5z"/></svg>',
            "class": "",
        },
    ],
}

autodoc_member_order = "bysource"
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Suppress warnings for optional deps that may not be installed at doc build time
autodoc_mock_imports = [
    "aioboto3",
    "asyncpg",
    "trafilatura",
    "readability",
    "markdownify",
    "html2text",
    "newspaper",
    "mutagen",
    "pymediainfo",
    "exifread",
    "pypdf",
    "yt_dlp",
    "gallery_dl",
    "playwright",
    "feedparser",
    "textual",
]

todo_include_todos = True
