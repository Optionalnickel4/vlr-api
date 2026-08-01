"""Derived ratings — the only numbers in this project we invent ourselves.

Everything else the API serves is vlr.gg's data reshaped. This package computes
something vlr does not publish: a style breakdown of a player, derived from the
stats leaderboard.

It is deliberately pure. No scraping, no cache, no DB, no I/O of any kind —
inputs are leaderboard row dicts and the output is a dict of numbers. That makes
the math exhaustively testable against a hand-built cohort fixture with
hand-computed expected values (tests/test_dimensions.py), which is the only
practical way to be confident in a formula nobody can eyeball.

If you add a rating here, keep that property: take the cohort as an argument
rather than fetching it. The caller (app/api/v1/routes.py) owns getting the
cached leaderboard; this package owns the arithmetic.
"""
