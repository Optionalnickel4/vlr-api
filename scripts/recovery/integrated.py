#!/usr/bin/env python3
"""Fail-closed Gate 2 runner. No production mounts, environment, or networking."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BASE = Path('/home/builder/vlr-recovery-check')
DEFAULT_INPUT = BASE / 'gate2-input.json'
FALLBACK = 'f0ab700c450bd9edc11775e9b7af38ef8fdfd040b6f28f25fccdb4685c53fdaa'
CANDIDATE = '9301682c4165d7507e49d6ad7678d14ca9df377e'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def member(root, name):
    p = Path(name)
    require(not p.is_absolute() and '..' not in p.parts and p.parts,
            'Invalid artifact member')
    result = root / p
    require(result.resolve().is_relative_to(root.resolve()), 'Artifact escape')
    return result


def validate_tree(spec, backend=False):
    root = Path(spec['root'])
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), 'Invalid artifact root')
    require(root.resolve().is_relative_to(BASE.resolve()), 'Artifact must be staged beneath recovery root')
    actual = set()
    for p in root.rglob('*'):
        require(not p.is_symlink(), 'Artifacts must be dereferenced, without symlinks')
        require(not p.name.startswith('.env'), 'Environment files forbidden in artifacts')
        require(p.is_dir() or p.is_file(), 'Special artifact file forbidden')
        if p.is_file():
            actual.add(p.relative_to(root).as_posix())
    require(actual == set(spec['files']), 'Manifest must cover every artifact file, exactly')
    for name, digest in spec['files'].items():
        require(sha(member(root, name)) == digest, 'Artifact hash mismatch: ' + name)
    if backend:
        for name in ('python', 'source', 'runtime_home'):
            member(root, spec[name])
        require(member(root, spec['python']).is_file(), 'Missing packaged interpreter')
        require(member(root, spec['source'] + '/app/main.py').is_file(), 'Missing backend source')
    else:
        require((root / '.next/BUILD_ID').read_text().strip() == spec['build_id'], 'Wrong frontend BUILD_ID')
        require((root / 'node_modules/next/dist/bin/next').is_file(), 'Missing installed Next runtime')


def artifact_names(data):
    return tuple(stage + '_' + kind for stage in data.get('stages', ['candidate', 'historical']) for kind in ('backend', 'frontend'))


def preflight(path):
    problems = []
    fixture = Path(__file__).resolve().parents[2] / 'tests/fixtures/results.html'
    if not fixture.is_file():
        problems.append('Missing fixture: ' + str(fixture))
    for binary in ('bwrap', 'node', 'redis-server', 'redis-cli'):
        if not shutil.which(binary):
            problems.append('Missing executable: ' + binary)
    for binary in ('initdb', 'postgres', 'psql', 'createdb'):
        if not Path('/usr/lib/postgresql/17/bin', binary).is_file():
            problems.append('Missing PostgreSQL 17 binary: ' + binary)
    if not path.is_file():
        problems.append('Missing reviewed input manifest: ' + str(path))
        return None, problems
    try:
        data = json.loads(path.read_text())
        if data.get('strategy') == 'new-known-baseline':
            require(data['stages'] == ['candidate', 'baseline'], 'Invalid baseline stages')
            require(data['secret_free_artifacts_reviewed'] is True, 'Secret-free artifact review required')
            require(data['purpose'] in ('baseline-rehearsal', 'second-release-rollback'), 'Invalid purpose')
            release = data['baseline_release']
            require(sha(release['path']) == release['sha256'], 'Baseline release manifest mismatch')
            manifest = json.loads(Path(release['path']).read_text())
            require(manifest['strategy'] == 'new-known-baseline', 'Not a new baseline')
            for kind in ('backend', 'frontend'):
                expected = {k[len(kind)+1:]: v for k, v in manifest['files'].items() if k.startswith(kind + '/')}
                require(expected == data['baseline_' + kind]['files'], 'Baseline inventory mismatch')
            if data['purpose'] == 'baseline-rehearsal':
                for kind in ('backend', 'frontend'):
                    require(data['candidate_' + kind]['files'] == data['baseline_' + kind]['files'], 'Rehearsal requires identical new baseline artifacts')
            else:
                require(data['baseline_startup_reviewed'] is True, 'Proven baseline startup review required')
                require(sha(data['baseline_receipt_path']) == data['baseline_receipt_sha256'], 'Baseline receipt mismatch')
                receipt = json.loads(Path(data['baseline_receipt_path']).read_text())
                require(receipt['release_manifest_sha256'] == release['sha256'], 'Receipt is for a different baseline')
                require(receipt['frontend_build_id'] == manifest['frontend_build_id'], 'Receipt BUILD_ID mismatch')
                require(bool(receipt['invocation_id']) and receipt['pid'] > 0, 'Missing startup identity')
                require(any(data['candidate_' + kind]['files'] != data['baseline_' + kind]['files'] for kind in ('backend', 'frontend')), 'Second release must differ from baseline')
        else:
            require(data['candidate_revision'] == CANDIDATE, 'Wrong candidate revision')
            require(data['secret_free_artifacts_reviewed'] is True, 'Secret-free artifact review required')
            provenance = data['provenance']
            require(provenance['reviewed_startup_link'] is True, 'Gate 1 startup-link review required')
            require(provenance['archive_sha256'] != FALLBACK, 'Known historical fallback is NOT attested production')
            for key in ('startup_timestamp', 'invocation_id', 'source_identity'):
                require(bool(provenance[key]), 'Missing provenance: ' + key)
            require(provenance['pid'] > 0, 'Missing startup PID')
            for name in ('archive', 'receipt'):
                require(sha(provenance[name + '_path']) == provenance[name + '_sha256'], 'Provenance file hash mismatch')
            canonical = json.dumps(data['historical_backend']['files'], sort_keys=True, separators=(',', ':')).encode()
            require(hashlib.sha256(canonical).hexdigest() == provenance['backend_files_sha256'], 'Receipt/artifact inventory mismatch')
        for name in artifact_names(data):
            validate_tree(data[name], name.endswith('backend'))
        return data, problems
    except (KeyError, ValueError, OSError, TypeError) as exc:
        problems.append(type(exc).__name__ + ': ' + str(exc))
        return None, problems


def sandbox_command(work):
    # Fresh mount, PID, IPC, user and network namespaces. Host /etc, /home,
    # /opt, /run, /var, sockets, credentials and inherited env are not mounted.
    cmd = [shutil.which('bwrap') or 'bwrap', '--unshare-all', '--die-with-parent', '--new-session',
           '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
           '--setenv', 'HOME', '/work', '--setenv', 'LANG', 'C.UTF-8']
    for path in ('/usr', '/bin', '/lib', '/lib64'):
        if Path(path).exists():
            cmd += ['--ro-bind', path, path]
    cmd += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/etc',
            '--ro-bind', str(work / 'passwd'), '/etc/passwd',
            '--ro-bind', str(work / 'artifacts'), '/artifacts',
            '--ro-bind', str(work / 'runner'), '/runner',
            '--bind', str(work / 'state'), '/work', '--chdir', '/work',
            '/usr/bin/python3', '/runner/sandbox.py']
    return cmd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    data, problems = preflight(args.input)
    if problems:
        print(json.dumps({'result': 'BLOCKED', 'problems': problems}, indent=2))
        return 2
    if args.preflight:
        print('Preflight inputs pass; namespace capability is checked only by the isolated run.')
        return 0
    if data.get('strategy') != 'new-known-baseline':
        identity = subprocess.check_output(['systemctl', 'show', 'vlr-api.service', '-p', 'MainPID',
                                            '-p', 'ExecMainStartTimestamp', '-p', 'InvocationID'], text=True)
        current = dict(line.split('=', 1) for line in identity.splitlines())
        provenance = data['provenance']
        require(current == {'MainPID': str(provenance['pid']),
                            'ExecMainStartTimestamp': provenance['startup_timestamp'],
                            'InvocationID': provenance['invocation_id']},
                'Attestation does not match current service identity')
    require(os.getuid() != 0, 'Run as the unprivileged builder user, never root')
    copied_bytes = sum(sum(member(Path(data[name]['root']), item).stat().st_size
                                 for item in data[name]['files']) * (2 if name.endswith('frontend') else 1)
                       for name in artifact_names(data))
    require(shutil.disk_usage(BASE).free >= copied_bytes + 3 * 1024 ** 3,
            'Insufficient space: artifact copies plus 1 GiB test storage/log budget and 2 GiB reserve required')
    os.umask(0o077)
    work = Path(tempfile.mkdtemp(prefix='gate2-', dir=BASE))
    (work / 'state').mkdir()
    (work / 'artifacts').mkdir()
    shutil.copytree(Path(__file__).parent, work / 'runner', ignore=shutil.ignore_patterns('__pycache__'))
    fixture = Path(__file__).resolve().parents[2] / 'tests/fixtures/results.html'
    shutil.copyfile(fixture, work / 'runner/results.html')
    (work / 'passwd').write_text(f'builder:x:{os.getuid()}:{os.getgid()}:Recovery:/work:/bin/sh\n')
    try:
        for name in artifact_names(data):
            spec = data[name]
            dest = work / 'artifacts' / name
            shutil.copytree(spec['root'], dest)
            copied = dict(spec, root=str(dest))
            validate_tree(copied, name.endswith('backend'))
            data[name]['root'] = '/artifacts/' + name
        # Only redacted identity fields cross into the sandbox. No receipt/archive.
        if 'provenance' in data:
            data['provenance'].pop('archive_path')
            data['provenance'].pop('receipt_path')
        (work / 'state/input.json').write_text(json.dumps(data, indent=2))
        print('Private recovery directory: ' + str(work), flush=True)
        with (work / 'launcher.log').open('w') as log:
            result = subprocess.run(sandbox_command(work), stdout=log, stderr=subprocess.STDOUT,
                                    env={'PATH': '/usr/bin:/bin'}, timeout=600)
        require(result.returncode == 0, 'Sandbox failed; inspect private launcher.log and state/result.json')
        receipt = json.loads((work / 'state/result.json').read_text())
        require(receipt['passed'] is True, 'Acceptance failed')
        print(json.dumps({'result': 'PASS', 'evidence': str(work / 'state/result.json')}))
        return 0
    except Exception as exc:
        (work / 'launcher-failure.txt').write_text(str(exc))
        print('FAILED; retained private evidence: ' + str(work), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
