"""Orchestration — where scraping, caching, and persistence are wired together.

The layer that decides WHEN things happen. Scrapers know how to parse a page;
routers know how to answer a request; this package owns everything in between.

    refresh.py  scrape -> cache -> history. The only module allowed to scrape.
    search.py   player search: our own DB first, vlr's typeahead only on a miss.
    trends.py   read-only analytics over banked history. Never scrapes, never writes.

A pattern worth copying if you add to this package: the pure shaping logic is
kept separate from the DB and network calls (see trends.py's builders and
search.py's statement builder and JSON parser). That is what lets the analytics
be tested exhaustively on row-like dicts with no Postgres and no fixtures.
"""
