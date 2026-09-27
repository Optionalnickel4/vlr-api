#!/usr/bin/env python3
"""Post-start frontend witness. Read-only; no HTTP requests. Writes JSON to stdout."""
import json
from pathlib import Path
import sys
from receipt import sha, start_ticks, service_identity, check_manifest
root = Path(sys.argv[1]).resolve()
m = check_manifest(root)
s = service_identity('vlr-frontend.service')
pid = int(s['MainPID'])
assert pid > 0
assert Path(f'/proc/{pid}/cwd').resolve() == root / 'frontend'
assert sha(f'/proc/{pid}/exe') == sha(root / 'frontend/node')
args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
# Next rewrites process.title, so cwd/exe/cgroup/systemd ExecStart must corroborate it.
assert 'vlr-frontend.service' in Path(f'/proc/{pid}/cgroup').read_text()
print(json.dumps({'service': s, 'pid': pid, 'proc_start_ticks': start_ticks(pid),
                  'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  'cmdline': [a.decode() for a in args if a],
                  'release_manifest_sha256': sha(root / 'release.json'),
                  'node_sha256': sha(f'/proc/{pid}/exe'), 'frontend_build_id': m['frontend_build_id']}, indent=2))
assert s == service_identity('vlr-frontend.service'), 'Process changed while collecting'
