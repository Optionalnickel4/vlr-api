"""HTML scrapers — the only layer that knows what vlr.gg markup looks like.

One module per entity. Each exposes the same two-part shape:

    parse_x(html) -> dict/list    PURE. No network, no cache, no DB. This is what
                                  the tests call against saved fixtures.
    fetch_x(...)  -> awaitable    The thin async wrapper: one polite GET through
                                  app.core.http, then parse_x.

Keeping the parse pure is what makes the whole suite runnable offline, and it is
why a markup regression is reproducible from a saved page instead of needing a
live match to be in progress.

Two rules hold across every module here:
  - CSS selectors live ONLY in selectors.py, never inline. When vlr changes its
    markup you should need to edit exactly one file.
  - Scrapers never cache and never write to Postgres. services/refresh.py owns
    that, and the public API never calls into this package at request time.

Not entity scrapers, but shipped alongside:
  verify.py      run selectors against LIVE vlr.gg and report what broke
  capture.py     save a live page verbatim as a new test fixture
  stats_recon.py one-off column discovery for /stats
"""
