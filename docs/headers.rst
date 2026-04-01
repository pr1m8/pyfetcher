Browser Headers
===============

pyfetcher generates realistic browser headers with full identity consistency.
Each browser profile bundles User-Agent, Client Hints (Sec-CH-UA-*),
Sec-Fetch-* metadata, and Accept headers into a coherent identity.

Available Profiles
------------------

.. list-table::
   :header-rows: 1
   :widths: 20 15 15 10

   * - Profile Name
     - Browser
     - Platform
     - Mobile
   * - ``chrome_win``
     - Chrome
     - Windows
     - No
   * - ``chrome_mac``
     - Chrome
     - macOS
     - No
   * - ``chrome_linux``
     - Chrome
     - Linux
     - No
   * - ``chrome_android``
     - Chrome
     - Android
     - Yes
   * - ``firefox_win``
     - Firefox
     - Windows
     - No
   * - ``firefox_mac``
     - Firefox
     - macOS
     - No
   * - ``firefox_linux``
     - Firefox
     - Linux
     - No
   * - ``safari_mac``
     - Safari
     - macOS
     - No
   * - ``safari_ios``
     - Safari
     - iOS
     - Yes
   * - ``edge_win``
     - Edge
     - Windows
     - No
   * - ``edge_mac``
     - Edge
     - macOS
     - No

Using Profiles
--------------

Fixed profile:

.. code-block:: python

   from pyfetcher.headers.browser import BrowserHeaderProvider

   provider = BrowserHeaderProvider("chrome_win")

Rotating profiles (weighted by market share):

.. code-block:: python

   from pyfetcher.headers.rotating import RotatingHeaderProvider

   provider = RotatingHeaderProvider()

Random user-agent generation:

.. code-block:: python

   from pyfetcher.headers.ua import random_user_agent

   ua = random_user_agent(browser="chrome", platform="macOS")
