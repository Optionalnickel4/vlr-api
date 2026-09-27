#!/usr/bin/env python3
"""Seal prepared artifacts and emit a new-baseline rehearsal input, never a historical receipt."""
import json
from pathlib import Path
import shutil
import sys
import subprocess
import re
import tarfile
from package import inventory, sha

assert '--reviewed-secret-free' in sys.argv, 'Explicit artifact secret review required'
root = Path(sys.argv[1]).resolve()
assert not (root / 'release.json').exists(), 'Already sealed'
shutil.copy2(Path(__file__).with_name('receipt.py'), root / 'receipt.py')
# Build cache is unnecessary input and may contain absolute build paths.
shutil.rmtree(root / 'frontend/.next/cache', ignore_errors=True)
files = inventory(root / 'backend')
frontfiles = inventory(root / 'frontend')
deps = {k: v for k, v in files.items() if k.startswith('runtime/')}
deps.update({'frontend/' + k: v for k, v in frontfiles.items() if k.startswith('node_modules/') or k == 'node'})
(root / 'dependencies.json').write_text(json.dumps(deps, sort_keys=True) + '\n')
archives = {}
for name in ('backend', 'frontend'):
    archive = root / (name + '.tar.gz')
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        tar.add(root / name, arcname=name)
    archives[name] = {'path': str(archive), 'sha256': sha(archive), 'bytes': archive.stat().st_size}
system_libraries = {}
for binary in [root / 'backend/runtime/bin/python3.13', root / 'frontend/node', *list((root / 'backend/runtime').rglob('*.so')), *list((root / 'frontend/node_modules').rglob('*.node'))]:
    result = subprocess.run(['ldd', str(binary)], capture_output=True, text=True)
    for library in re.findall(r'(/[^ \n]+)', result.stdout):
        if Path(library).is_file():
            system_libraries[library] = sha(library)
manifest = {'schema': 1, 'system_libraries': system_libraries, 'strategy': 'new-known-baseline',
            'source': json.loads((root / 'inputs.json').read_text()),
            'frontend_build_id': (root / 'frontend/.next/BUILD_ID').read_text().strip(),
            'dependency_inventory_sha256': sha(root / 'dependencies.json'),
            'artifact_archives': archives,
            'files': {**{'backend/' + k: v for k, v in files.items()}, **{'frontend/' + k: v for k, v in frontfiles.items()},
                      'receipt.py': sha(root / 'receipt.py'), 'inputs.json': sha(root / 'inputs.json'),
                      'dependencies.json': sha(root / 'dependencies.json')}}
(root / 'release.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
spec = {'strategy': 'new-known-baseline', 'purpose': 'baseline-rehearsal', 'stages': ['candidate', 'baseline'],
        'secret_free_artifacts_reviewed': True,
        'baseline_release': {'path': str(root / 'release.json'), 'sha256': sha(root / 'release.json')}}
for stage in spec['stages']:
    spec[stage + '_backend'] = {'root': str(root / 'backend'), 'files': files, 'source': 'source',
                              'python': 'runtime/bin/python3.13', 'runtime_home': 'runtime'}
    spec[stage + '_frontend'] = {'root': str(root / 'frontend'), 'files': frontfiles, 'build_id': manifest['frontend_build_id']}
# File creation is exclusive; never replace an existing Gate 2 input.
with (root.parent / 'gate2-input.json').open('x') as f:
    json.dump(spec, f, indent=2)
for name in ('backend', 'frontend'):
    for p in (root / name).rglob('*'):
        p.chmod(p.stat().st_mode & ~0o222)
    (root / name).chmod(0o500)
for name in ('backend.tar.gz', 'frontend.tar.gz', 'release.json', 'inputs.json', 'dependencies.json', 'receipt.py'):
    (root / name).chmod(0o400)
print(json.dumps({'release': str(root / 'release.json'), 'sha256': sha(root / 'release.json'), 'archives': archives,
                  'frontend_build_id': manifest['frontend_build_id']}, indent=2))
