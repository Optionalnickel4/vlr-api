#!/usr/bin/env python3
"""Backend startup witness and live verifier. No credentials recorded."""
import argparse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def start_ticks(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]

def check_manifest(root):
    m = json.loads((root / 'release.json').read_text())
    for name, digest in m.get('system_libraries', {}).items():
        if sha(name) != digest:
            raise RuntimeError('System library mismatch: ' + name)
    for name, digest in m['files'].items():
        p = root / name
        if not p.resolve().is_relative_to(root.resolve()) or sha(p) != digest:
            raise RuntimeError('Release file mismatch: ' + name)
    return m

def service_identity(unit):
    s = subprocess.check_output(['systemctl', 'show', unit, '-p', 'MainPID', '-p',
                                 'InvocationID', '-p', 'ExecMainStartTimestamp'], text=True)
    return dict(line.split('=', 1) for line in s.splitlines())

def verify(path, unit):
    r = json.loads(path.read_text())
    root = Path(r['release_root'])
    m = check_manifest(root)
    assert sha(root / 'release.json') == r['release_manifest_sha256']
    assert m['frontend_build_id'] == r['frontend_build_id']
    identity = service_identity(unit)
    assert identity['MainPID'] == str(r['pid'])
    assert identity['InvocationID'] == r['invocation_id']
    assert start_ticks(r['pid']) == r['proc_start_ticks']
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == r['boot_id']
    assert sha(f"/proc/{r['pid']}/exe") == r['interpreter_sha256']
    assert Path(f"/proc/{r['pid']}/cwd").resolve() == root / 'backend/source'
    for module in r['modules'].values():
        assert sha(module['path']) == module['sha256']
    # Preserve systemd's wall-clock start string beside the in-process monotonic identity.
    attestation = {'verified_at': datetime.now(timezone.utc).isoformat(), 'service': unit,
                   'systemd': identity, 'startup_receipt_sha256': sha(path), 'passed': True}
    print(json.dumps(attestation, indent=2))

def launch(root, output):
    m = check_manifest(root)
    invocation = os.environ.get('INVOCATION_ID')
    if not invocation:
        raise RuntimeError('systemd INVOCATION_ID required')
    sys.path.insert(0, str(root / 'backend/source'))
    import app.main
    import uvicorn
    original = app.main.app.router.lifespan_context
    @asynccontextmanager
    async def witnessed(application):
        async with original(application):
            modules = {}
            for name, mod in list(sys.modules.items()):
                filename = getattr(mod, '__file__', None)
                if filename and Path(filename).is_file():
                    p = Path(filename).resolve()
                    if name == 'app' or name.startswith('app.'):
                        if not p.is_relative_to(root / 'backend/source'):
                            raise RuntimeError('Imported app outside release')
                    modules[name] = {'path': str(p), 'sha256': sha(p)}
            scheduler = app.main._scheduler
            r = {'schema': 1, 'release_root': str(root), 'release_manifest_sha256': sha(root / 'release.json'),
                 'artifact_archives': m['artifact_archives'], 'frontend_build_id': m['frontend_build_id'],
                 'invocation_id': invocation, 'pid': os.getpid(), 'proc_start_ticks': start_ticks(os.getpid()),
                 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 'observed_at_utc': datetime.now(timezone.utc).isoformat(),
                 'interpreter': sys.executable, 'interpreter_sha256': sha('/proc/self/exe'),
                 'dependency_inventory_sha256': m['dependency_inventory_sha256'], 'modules': modules,
                 'scheduler_running': bool(scheduler and scheduler.running),
                 'scheduler_jobs': [j.id for j in scheduler.get_jobs()] if scheduler else []}
            output.mkdir(parents=True, exist_ok=True)
            # Unique per invocation; an existing receipt must never be replaced.
            with (output / (invocation + '.json')).open('x') as f:
                json.dump(r, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            yield
    app.main.app.router.lifespan_context = witnessed
    uvicorn.run(app.main.app, host='0.0.0.0', port=8000, workers=1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('launch')
    p.add_argument('root', type=Path)
    p.add_argument('output', type=Path)
    p = sub.add_parser('verify')
    p.add_argument('receipt', type=Path)
    p.add_argument('--unit', default='vlr-api.service')
    a = parser.parse_args()
    if a.action == 'launch':
        launch(a.root.resolve(), a.output)
    else:
        verify(a.receipt, a.unit)
