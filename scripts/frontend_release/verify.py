#!/usr/bin/env python3
"""Read-only cutover preflight; no service or data operations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def tree(root, expected):
    files={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
    if files!=expected:raise SystemExit('Build inventory mismatch: '+str(root))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--rollback-only',action='store_true')
    args=p.parse_args();root=args.root
    if sha(root/'manifest.json')!=args.manifest_sha256:raise SystemExit('Manifest hash mismatch')
    m=json.loads((root/'manifest.json').read_text())
    for name in ('candidate','rollback'):
        if sha(m[name+'_archive'])!=m[name+'_archive_sha256']:raise SystemExit('Archive mismatch')
    if not args.rollback_only:
        tree(root/'candidate/.next',m['candidate_files'])
    tree(root/'rollback/frontend/.next',m['rollback_files'])
    for name,digest in m['unchanged_runtime_files'].items():
        if sha(Path('/opt/vlr-api/frontend')/name)!=digest:raise SystemExit('Runtime drift: '+name)
    for name,target in m['unchanged_runtime_symlinks'].items():
        if os.readlink(Path('/opt/vlr-api/frontend')/name)!=target:raise SystemExit('Runtime link drift: '+name)
    if sha(m['node_path'])!=m['node_sha256']:raise SystemExit('Node drift')
    if sha('/etc/systemd/system/vlr-frontend.service')!=m['frontend_unit_sha256']:raise SystemExit('Frontend unit drift')
    unit=subprocess.check_output(['systemctl','show','vlr-frontend.service','-p','DropInPaths','-p','Requires','-p','Wants','-p','PartOf','-p','BindsTo','-p','PropagatesStopTo','-p','ExecStartPre','-p','ExecStopPost'],text=True)
    props=dict(line.split('=',1) for line in unit.splitlines())
    for name in ('DropInPaths','PartOf','BindsTo','PropagatesStopTo','ExecStartPre','ExecStopPost'):
        if props.get(name):raise SystemExit('Unexpected unit hook/dependency: '+name)
    if set(props.get('Requires','').split())!={'system.slice','sysinit.target'} or set(props.get('Wants','').split())!={'network-online.target'}:raise SystemExit('Unit dependency drift')
    if not args.rollback_only and Path('/opt/vlr-api/frontend/.next/BUILD_ID').read_text().strip()!=m['rollback_build_id']:raise SystemExit('Current build changed; recheck release scope')
    if root.stat().st_dev!=Path('/opt/vlr-api/frontend').stat().st_dev:raise SystemExit('Require same filesystem for directory renames')
    if not args.rollback_only and shutil.disk_usage(root).free < 1024**3:raise SystemExit('Require 1 GiB free reserve')
    print('PASS: ' + ('restored rollback' if args.rollback_only else 'candidate and restored rollback') + ', unchanged runtime/unit and swap prerequisites')

if __name__=='__main__':main()
