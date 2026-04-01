Scraping
========

pyfetcher provides a comprehensive set of scraping utilities built on
BeautifulSoup.

CSS Selector Extraction
-----------------------

.. code-block:: python

   from pyfetcher.scrape.selectors import extract_text, extract_attrs, extract_table

   # Extract text from elements
   titles = extract_text(html, "h1")

   # Extract attributes
   links = extract_attrs(html, "a", attrs=["href", "title"])

   # Parse HTML tables
   rows = extract_table(html, "table.data")

Link Harvesting
---------------

.. code-block:: python

   from pyfetcher.scrape.links import extract_links

   links = extract_links(html, base_url="https://example.com")
   internal = [l for l in links if not l.is_external]

Form Parsing
------------

.. code-block:: python

   from pyfetcher.scrape.forms import extract_forms

   forms = extract_forms(html, base_url="https://example.com")
   login_form = forms[0]
   print(login_form.action, login_form.method)
   print(login_form.to_dict())  # Field names -> default values

Robots.txt
----------

.. code-block:: python

   from pyfetcher.scrape.robots import parse_robots_txt, is_allowed

   rules = parse_robots_txt(robots_txt_content)
   if is_allowed(rules, "/admin", user_agent="MyBot"):
       print("Path is allowed")

Sitemap Parsing
---------------

.. code-block:: python

   from pyfetcher.scrape.sitemap import parse_sitemap

   entries = parse_sitemap(sitemap_xml)
   for entry in entries:
       print(entry.loc, entry.lastmod)

Content Extraction
------------------

.. code-block:: python

   from pyfetcher.scrape.content import extract_readable_text

   # Strips scripts, styles, nav, footer
   text = extract_readable_text(html)

   # Target specific element
   text = extract_readable_text(html, selector="article")
