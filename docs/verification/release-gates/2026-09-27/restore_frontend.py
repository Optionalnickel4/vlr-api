import pathlib,tarfile,json,hashlib,time,os
P=pathlib.Path('/home/builder/vlr-gates-private');D=pathlib.Path('/tmp/vlr-gates-9301682/restored-app');assert not D.exists();D.mkdir(mode=0o700)
start=time.monotonic()
with tarfile.open(P/'frontend-rollback.tar.gz') as tar:tar.extractall(D,filter='data')
manifest=json.loads((P/'frontend-manifest.json').read_text());bad=[]
for f,h in manifest.items():
 if hashlib.sha256((D/f).read_bytes()).hexdigest()!=h:bad.append(f)
r={'restore_seconds':round(time.monotonic()-start,2),'regular_files_verified':len(manifest),'mismatches':bad,'restored_build_id':(D/'frontend/.next/BUILD_ID').read_text().strip(),'restored_on':'private tmpfs, not durable production rollback slot','logical_bytes':sum(p.stat().st_size for p in D.rglob('*') if p.is_file() and not p.is_symlink())}
pathlib.Path('/opt/vlr-api/docs/verification/release-gates/2026-09-27/rollback-restore.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
