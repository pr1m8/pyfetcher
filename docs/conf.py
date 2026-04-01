"""Sphinx configuration for fetchkit (pyfetcher)."""

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "fetchkit"
copyright = "2026, Will"
author = "Will"
release = "0.2.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_static_path = ["_static"]
html_title = "fetchkit"

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
