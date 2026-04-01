CLI Reference
=============

pyfetcher provides a command-line interface for common operations.

fetch
-----

Fetch a URL and display the response:

.. code-block:: bash

   pyfetcher fetch https://example.com
   pyfetcher fetch https://api.example.com -m POST -d '{"key": "val"}'
   pyfetcher fetch https://example.com -o json
   pyfetcher fetch https://example.com -o raw
   pyfetcher fetch https://example.com --profile firefox_win

Backends can be selected with ``-b``:

.. code-block:: bash

   pyfetcher fetch https://example.com -b curl_cffi
   pyfetcher fetch https://example.com -b cloudscraper

headers
-------

Preview generated browser headers:

.. code-block:: bash

   pyfetcher headers --profile chrome_win
   pyfetcher headers --browser firefox -o json
   pyfetcher headers --list

scrape
------

Scrape content from a URL:

.. code-block:: bash

   pyfetcher scrape https://example.com --css "h1"
   pyfetcher scrape https://example.com --links -o json
   pyfetcher scrape https://example.com --text
   pyfetcher scrape https://example.com --meta
   pyfetcher scrape https://example.com --forms

user-agent
----------

Generate random user-agent strings:

.. code-block:: bash

   pyfetcher user-agent
   pyfetcher user-agent --browser chrome --count 5
   pyfetcher user-agent --mobile

robots
------

Check robots.txt for a URL:

.. code-block:: bash

   pyfetcher robots https://example.com
   pyfetcher robots https://example.com -p /admin -u Googlebot

download
--------

Download a file:

.. code-block:: bash

   pyfetcher download https://example.com/file.pdf ./file.pdf
