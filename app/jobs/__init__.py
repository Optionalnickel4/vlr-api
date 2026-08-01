"""Scheduled scraping — the write side of the system.

This package is what keeps the cache warm so the API never has to scrape on the
request path. It holds no logic of its own: scheduler.py maps cadences onto
`services.refresh` coroutines, and run.py is a standalone process wrapper for
deployments that don't want the scheduler inside the API (VLR_ENABLE_SCHEDULER=false).

Exactly ONE scheduler should exist across the deployment. Two — say, several
uvicorn workers each with the scheduler enabled — means every cadence runs N
times over, multiplying load on vlr.gg for no benefit.
"""
