"""Reserved for Pydantic response models. Currently EMPTY — nothing imports this.

Routers return plain dicts straight from the cache/DB layer, so responses are
whatever the scrapers produced. That is a deliberate trade for a scraper-backed
API: vlr.gg adds and renames columns without warning, and an unmapped field
should surface as a new key rather than be dropped by a strict model or 500 the
endpoint on a validation error. The scrapers already do the work a schema layer
usually does — fixed key sets, null-not-NaN coercion — at parse time.

The cost is that the response contract is defined only by the scrapers and by
frontend/src/types/vlr.ts, with nothing enforcing that the two agree. If you
want typed, self-documenting responses (OpenAPI bodies included), this is where
they go — but keep them permissive about unknown fields.
"""
