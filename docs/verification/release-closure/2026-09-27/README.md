# Remaining release gate evidence

Application: `9301682c4165d7507e49d6ad7678d14ca9df377e`. Documentation-only follow-up; no application fix or repeated final suite.

- `baseline.json`: read-only production service/runtime/disk inventory and protected file hashes.
- `installed-python-packages.json`: current disk dependency versions, not attestation of loaded modules.
- `package_fallback.py`, `backend-artifact.json`: historical fallback bundle and successful hash restoration. Initial absolute-symlink extraction failed safely; final copy dereferences links. Private artifacts are not committed.
- `restore_checks.py`, `restoration.json`: durable frontend/hash and database restoration; historical backend health/history ASGI checks. TCP is denied in the backend probe. No lifespan, migrations, scheduler execution, Redis verification or production source calls. Private Postgres stopped.
- `public_smoke.py`, `public-smoke.json`: bounded direct/public static probes. One separately recorded curl diagnostic after the Python public 403 succeeded; cause of the client-dependent result is unknown. No dynamic pages or VLR requests.
- `final-preservation-capacity.json`: unchanged process/unit/config/protected-file checks, shared OS runtime dependencies, and conservative disk budget.

Harnesses create new fixed-name private directories and are intentionally not safe to rerun over existing evidence. They are review records, not deployment scripts. The full backend rollback and effective-ingress gates remain unresolved; capacity passes. See the two release documents for limits, exact artifact identities and remaining owner actions. All private artifacts/data/configuration remain outside Git with a mode-0700 parent.
