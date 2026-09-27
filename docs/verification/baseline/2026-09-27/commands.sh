#!/bin/sh
# Preparation only; paths document this retained run. Never source as a deployment script.
# The output directory already exists: reproduce with a NEW unique destination.
set -eu
BASE=/home/builder/vlr-recovery-check/baseline-NEW
BWRAP=/home/builder/vlr-baseline-tools/root/usr/bin/bwrap
python3 scripts/baseline/package.py "$BASE"
python3 scripts/baseline/fonts.py "$BASE/frontend/font-inputs"
"$BWRAP" --unshare-all --die-with-parent \
  --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 \
  --proc /proc --dev /dev --tmpfs /tmp --bind "$BASE/frontend" /build --chdir /build \
  --clearenv --setenv PATH /usr/bin:/bin --setenv HOME /tmp \
  --setenv NODE_ENV production --setenv NEXT_TELEMETRY_DISABLED 1 \
  --setenv NEXT_FONT_GOOGLE_MOCKED_RESPONSES /build/font-inputs/responses.json \
  --setenv VLR_API_BASE http://127.0.0.1:8000/api/v1 \
  /usr/bin/node node_modules/next/dist/bin/next build --webpack > "$BASE/build-offline.log" 2>&1
# Review actual build metadata and secret-free input scan before seal.py.
# Do not auto-set a human review boolean or replace gate2-input.json.
