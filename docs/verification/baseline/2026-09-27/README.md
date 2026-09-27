# New baseline preparation evidence

Governing [proposal/runbook](../../../BASELINE_DEPLOYMENT_PROPOSAL.md). **NO-GO for production; baseline preparation and isolated recovery pass.** Historical September 17 provenance is unrecoverable from available evidence; the old gate is failed/superseded, never converted to pass.

- `assessment.json`: current gates, resolved prerequisites, failed attempts, boundaries and protected-file hashes.
- `artifacts.json`: release manifest and compressed artifact digests, retained locations, frontend BUILD_ID.
- `inputs.json`: source inventory/dirty patch, Python dependencies and versions, Node/npm, build inputs, private Bubblewrap identity and input manifest hash.
- `archive-verification.json`: complete compressed archive member hashes match the release inventory; no links, traversal or duplicate members. This is streaming byte verification, not a new production extraction.
- `integrated-recovery.json`: exact successful private result; two known-baseline stages, normal lifespan/schema/scheduler, real Next/API fixture integration, newer data/cache preservation, storage continuity and complete graceful cleanup. It is not a different release's rollback test.
- `tests.txt`: 12 offline safety/receipt tests; receipt generation test uses mocked lifespan/systemd invocation, not a live deployment claim.
- `capacity.json`: measured retained allocations/free capacity and harness budget; future cutover capacity remains gated.
- `secret-review.json`: no environment files or known credential/token matches; one reviewed public noncredential source default triggered the initial broad URL scan. This is bounded review, not universal secret detection.
- `cleanup.json`: only redundant artifact/runtime copies from this task's failed isolated runs were reclaimed. Logs/results/inputs, source archives, successful run and prior task evidence remain retained.
- `commands.sh`: reproducible networkless frontend build; use new paths, inspect metadata and review before sealing.

Full manifests/archives/dependency trees/build and rehearsal logs stay in private durable `/home/builder/vlr-recovery-check/baseline-20260927`. Successful private run: `/home/builder/vlr-recovery-check/gate2-6t1ng6jg`. Both on-host read-only archives and a committed digest are available; independently immutable off-host storage has not been supplied and remains a first-cutover gate. No production services/configuration/data/cache were changed, no production migrations ran, and no VLR requests were made.
