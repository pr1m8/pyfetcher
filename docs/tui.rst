TUI Reference
=============

pyfetcher includes an interactive terminal user interface built with
`Textual <https://textual.textualize.io/>`_.

Installation
------------

.. code-block:: bash

   pip install 'fetchkit[tui]'

Launching
---------

.. code-block:: bash

   pyfetcher-tui
   # or
   python -m pyfetcher.tui.app

Layout
------

The TUI features a split-pane layout:

- **Left panel**: URL input, method selector, browser profile selector,
  custom headers editor, and action buttons.
- **Right panel**: Response log showing fetch results, headers, links,
  text, and metadata.

Keyboard Shortcuts
------------------

.. list-table::
   :header-rows: 1

   * - Key
     - Action
   * - ``Ctrl+F``
     - Execute the current request
   * - ``Ctrl+H``
     - Preview generated headers
   * - ``Ctrl+L``
     - Extract links from last response
   * - ``Ctrl+T``
     - Extract readable text from last response
   * - ``Q``
     - Quit the application

Features
--------

- **Fetch**: Enter a URL, select method and browser profile, click Fetch
  or press ``Ctrl+F``.
- **Headers Preview**: View the full set of headers that would be sent
  for the selected browser profile.
- **Link Extraction**: After fetching a page, extract all internal and
  external links.
- **Text Extraction**: Strip scripts/nav/footer and view the readable
  text content.
- **Metadata**: View page title, description, canonical URL, and Open
  Graph metadata.
