#!/usr/bin/env python3
"""Create a NEW baseline from reviewed disk bytes; never reconstruct a past process."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

REPO = Path(__file__).resolve().parents[2]

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}

def command(*args):
    return subprocess.check_output(args, cwd=REPO, text=True).strip()

def main():
    dest = Path(sys.argv[1]).resolve()
    if not dest.is_relative_to(Path('/home/builder/vlr-recovery-check')):
        raise SystemExit('Use a new private recovery directory')
    os.umask(0o077)
    dest.mkdir()  # Never overwrite any retained artifact.
    backend = dest / 'backend'
    source = backend / 'source'
    frontend = dest / 'frontend'
    source.mkdir(parents=True)
    frontend.mkdir()
    paths = command('git', 'ls-files', 'app', 'pyproject.toml', 'frontend').splitlines()
    for name in paths:
        p = REPO / name
        if p.name.startswith('.env'):
            continue
        target = frontend / p.relative_to(REPO / 'frontend') if name.startswith('frontend/') else source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    extra = command('git', 'ls-files', '--others', '--exclude-standard', 'app', 'frontend').splitlines()
    if extra:
        raise SystemExit('Untracked application inputs require explicit review: ' + repr(extra))
    runtime = backend / 'runtime'
    (runtime / 'bin').mkdir(parents=True)
    shutil.copy2('/usr/bin/python3.13', runtime / 'bin/python3.13')
    shutil.copytree('/usr/lib/python3.13', runtime / 'lib/python3.13', symlinks=False)
    site = runtime / 'lib/python3.13/site-packages'
    shutil.copytree(REPO / '.venv/lib/python3.13/site-packages', site, symlinks=False)
    for p in site.glob('__editable__*vlr*'):
        if p.is_file():
            p.unlink()
    direct = site / 'vlr_api-0.1.0.dist-info/direct_url.json'
    direct.write_text('{"url":"file:../../../../source","dir_info":{"editable":false}}\n')
    # Retained installed dependencies are explicit build inputs, not a claim of pip reproducibility.
    shutil.copytree(REPO / 'frontend/node_modules', frontend / 'node_modules', symlinks=False)
    shutil.copy2('/usr/bin/node', frontend / 'node')
    meta = {
        'strategy': 'new-known-baseline', 'historical_process_identity': 'unrecoverable',
        'source_commit': command('git', 'rev-parse', 'HEAD'),
        'application_patch': command('git', 'diff', 'HEAD', '--', 'app', 'pyproject.toml', 'frontend'),
        'application_files': {p: sha(REPO / p) for p in paths if not Path(p).name.startswith('.env')},
        'python_version': command('/usr/bin/python3.13', '--version'),
        'python_packages': json.loads(command(str(REPO / '.venv/bin/python'), '-m', 'pip', 'list', '--format=json')),
        'node_version': command('/usr/bin/node', '--version'), 'npm_version': command('npm', '--version'),
        'dependency_policy': 'retained installed bytes, editable app indirection removed; source PYTHONPATH explicit',
        'build_environment': {'NODE_ENV': 'production', 'NEXT_TELEMETRY_DISABLED': '1', 'VLR_API_BASE': 'http://127.0.0.1:8000/api/v1', 'NEXT_FONT_GOOGLE_MOCKED_RESPONSES': '/build/font-inputs/responses.json'},
        'build_command': 'node node_modules/next/dist/bin/next build --webpack',
        'font_policy': 'Actual Google CSS and font bytes retained and hashed in frontend/font-inputs; local CSS URL mapping for offline webpack font loader; no substituted font content',
    }
    (dest / 'inputs.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(dest)

if __name__ == '__main__':
    main()
