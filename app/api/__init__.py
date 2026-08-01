"""HTTP surface. Routers only — no scraping logic, no SQL beyond simple reads.

    v1/routes.py    the JSON API, mounted under VLR_API_PREFIX (default /api/v1)
    status_html.py  the self-contained HTML dashboard at / and /status

Versioning convention: the JSON API lives under a version package so a breaking
response change can ship as v2 alongside v1 rather than silently reshaping what
existing consumers get. The status dashboard is deliberately unversioned and
mounted at the root — it is an operator page, not a contract.
"""
