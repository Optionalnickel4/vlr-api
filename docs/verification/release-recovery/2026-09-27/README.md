# Application-only recovery evidence

Application: `9301682c4165d7507e49d6ad7678d14ca9df377e`.
Starting documentation/remote-tracking SHA: `c630da3e5398400c7c746d350401b7e44f20ce32`.

- `provenance.json`: fresh read-only process, restricted journal, proc-access and Git observations. No exact production code/runtime attestation recovered.
- `recovery.py`: executed isolated Uvicorn application switch with database startup replaced by a read check to avoid migrations. Requires retained private artifacts/cluster; not a production deployment script. Each run adds a sentinel only to the isolated restored database.
- `recovery.json`: successful candidate→historical switch; 5,752 artifact hashes; both versions pass storage/health/history and scheduler tick; all four table fingerprints and newer cache data preserved. Normal full-service recovery remains false.
- `recovery-initial.json`: partial failed helper-API attempt; cleanup/preservation passed. Error: FastAPI has no `add_event_handler` method. Removed the unused call; custom lifespan wrapper performs the intended test setup.
- `recovery-second.json`: candidate passed, then exit-code assertion failed. Uvicorn completed lifespan shutdown and re-raised SIGTERM; final harness checks an explicit lifespan-completion marker plus exit 0 or -15.
- `checks.json`: 511 candidate blobs unchanged, JSON parsing/Python syntax pass, refreshed durable space passes. Prior application/cold-cache/deadline tests were not rerun.

Commands executed: `python3 docs/verification/release-recovery/2026-09-27/recovery.py`, read-only commands recorded in `provenance.json`, source blob hashing, `ast.parse`, JSON parsing, and `git diff --check`. Private logs and sentinels remain under `/home/builder/vlr-recovery-check/application-switch*`; test processes are stopped. No application files, production configuration/data/cache, `.gitignore`, or untracked plan were changed by this pass. No VLR request or migration occurred.

Full findings, limitations, operator collection commands and conditional full-service acceptance procedure are in [the gate report](../../../RELEASE_GATE_VERIFICATION.md#application-only-recovery-follow-up--2026-09-27). Recommendation remains **NO-GO**.
