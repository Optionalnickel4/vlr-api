"""Version 1 of the JSON API.

If you need to change a response shape in a way that would break existing
consumers, add a v2 package next to this one rather than editing here — the
frontend's data layer (frontend/src/lib/vlr.ts) and its TypeScript types are
written against these exact shapes, with nothing at runtime enforcing the match.
"""
