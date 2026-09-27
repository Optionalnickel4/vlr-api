#!/usr/bin/env python3
"""Read existing verified artifacts; prepare private frontend-only release/rollback."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile

BASE = Path('/home/builder/vlr-frontend-only-9301682')
BUILD = Path('/home/builder/vlr-release-review-9301682/frontend/.next')
OLD = Path('/home/builder/vlr-gates-private/frontend-rollback.tar.gz')
EXPECTED = 'cfabf6b2d94faf3d253bcdbb5191c10b0fe725d00ba3a992891de53ad992a5b6'

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()

def inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}

def main():
    os.umask(0o077)
    assert sha(OLD) == EXPECTED
    assert (BUILD / 'BUILD_ID').read_text().strip() == '86jVlbyKpPMhJnvsgczQ5'
    assert shutil.disk_usage(BASE.parent).free > 2*1024**3
    BASE.mkdir(exist_ok=True)
    assert not (BASE/'manifest.json').exists() and not (BASE/'candidate').exists(), 'Already prepared'
    rollback = BASE / 'rollback'
    if not rollback.exists():
        rollback.mkdir()
        with tarfile.open(OLD) as tar:
            tar.extractall(rollback, filter='data')
    old_manifest = json.loads(Path('/home/builder/vlr-gates-private/frontend-manifest.json').read_text())
    with tarfile.open(OLD) as tar:
        for member in tar:
            if member.islnk():
                old_manifest[member.name] = old_manifest[member.linkname]
    assert inventory(rollback) == old_manifest
    for p in rollback.rglob('*'):
        if p.is_symlink():
            assert p.resolve().is_relative_to(rollback), 'Rollback symlink escape'
    candidate = BASE / 'candidate'
    candidate.mkdir()
    shutil.copytree(BUILD, candidate / '.next')
    candidate_files = inventory(candidate / '.next')
    assert candidate_files == inventory(BUILD)
    archive = BASE / 'frontend-next-9301682.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        tar.add(candidate / '.next', arcname='.next')
    # Pin everything that this minimal cutover requires to remain unchanged.
    runtime = {k.removeprefix('frontend/'): v for k,v in old_manifest.items() if not k.startswith('frontend/.next/')}
    for k,v in runtime.items():
        assert sha(Path('/opt/vlr-api/frontend') / k) == v, k
    links={str(p.relative_to(rollback/'frontend')):os.readlink(p) for p in (rollback/'frontend').rglob('*') if p.is_symlink() and not str(p.relative_to(rollback/'frontend')).startswith('.next/')}
    for name,target in links.items():
        assert os.readlink(Path('/opt/vlr-api/frontend')/name)==target
    manifest = {'unchanged_runtime_symlinks': links, 'release_commit': '9301682c4165d7507e49d6ad7678d14ca9df377e',
                'last_frontend_commit': 'a251c99ade3e8d426e2782ab5d140815db1f33d4',
                'frontend_tree': '2a5c474942a81a58ceda8cf49ad2398a65e763ae',
                'candidate_build_id': '86jVlbyKpPMhJnvsgczQ5',
                'rollback_build_id': (rollback/'frontend/.next/BUILD_ID').read_text().strip(),
                'candidate_archive': str(archive), 'candidate_archive_sha256': sha(archive),
                'candidate_archive_bytes': archive.stat().st_size,
                'rollback_archive': str(OLD), 'rollback_archive_sha256': sha(OLD),
                'rollback_archive_bytes': OLD.stat().st_size,
                'node_path': '/usr/bin/node', 'node_sha256': sha('/usr/bin/node'),
                'frontend_unit_sha256': sha('/etc/systemd/system/vlr-frontend.service'),
                'candidate_files': candidate_files,
                'rollback_files': inventory(rollback/'frontend/.next'),
                'unchanged_runtime_files': runtime,
                'rollback_regular_files_verified': len(old_manifest)}
    (BASE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    summary={k:v for k,v in manifest.items() if not k.endswith('_files')}
    summary['manifest_path']=str(BASE/'manifest.json')
    summary['manifest_sha256']=sha(BASE/'manifest.json')
    summary['source_build_directory']=str(BUILD)
    summary['rollback_restored_directory']=str(rollback/'frontend')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
