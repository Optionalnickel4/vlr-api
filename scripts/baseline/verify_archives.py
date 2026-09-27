#!/usr/bin/env python3
"""Verify every archived byte/member against a sealed release, without extraction."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from receipt import sha
root = Path(sys.argv[1])
m = json.loads((root / 'release.json').read_text())
report = {}
for kind, spec in m['artifact_archives'].items():
    archive = root / (kind + '.tar.gz')
    assert sha(archive) == spec['sha256'], 'Archive checksum mismatch'
    found = {}
    with tarfile.open(archive) as tar:
        for member in tar:
            p = Path(member.name)
            assert not p.is_absolute() and '..' not in p.parts and p.parts[0] == kind
            assert member.isdir() or member.isfile(), 'Links/special files forbidden'
            if member.isfile():
                assert member.name not in found, 'Duplicate archive member'
                h = hashlib.sha256()
                with tar.extractfile(member) as f:
                    for block in iter(lambda: f.read(1024*1024), b''):
                        h.update(block)
                found[member.name] = h.hexdigest()
    expected = {k:v for k,v in m['files'].items() if k.startswith(kind + '/')}
    assert found == expected, 'Archive differs from release inventory'
    report[kind] = {'sha256': spec['sha256'], 'members_verified': len(found)}
print(json.dumps({'passed': True, 'archives': report}, indent=2))
