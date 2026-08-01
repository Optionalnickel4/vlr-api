"""Shared infrastructure: config, Redis, Postgres, and the vlr.gg HTTP client.

The bottom layer — this package imports from nothing else in `app`, and every
other layer depends on it. Each module owns exactly one process-wide resource
and hands it out through a lazy accessor (`get_settings`, `get_redis`,
`get_client`, `SessionLocal`) rather than a module-level instance, so importing
a module never opens a connection. That is what lets the test suite import the
whole app with no Redis, no Postgres, and no network.
"""
