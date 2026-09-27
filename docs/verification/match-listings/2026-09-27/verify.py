import pathlib,hashlib,json,subprocess,urllib.request,datetime
root=pathlib.Path('/opt/vlr-api'); src=root/'frontend'; dst=pathlib.Path('/tmp/vlr-preview/listings-final');out=pathlib.Path('/tmp/vlr-listings-delivery')
files=[p for folder in ['src','public'] for p in (src/folder).rglob('*') if p.is_file()]+[src/p for p in ['package.json','package-lock.json','next.config.ts','tsconfig.json','postcss.config.mjs','next-env.d.ts'] if (src/p).exists()]
hash=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={str(p.relative_to(src)):hash(p) for p in files};assert all(hash(dst/p)==h for p,h in manifest.items())
assert (root/'.gitignore').read_bytes()==(out/'gitignore.before').read_bytes();assert (root/'docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md').read_bytes()==(out/'plan.before').read_bytes()
health={}
for url in ['http://127.0.0.1:8000/health','http://127.0.0.1:3000/favicon.ico','http://10.0.0.21:3100/schedule','http://10.0.0.21:3100/results']:
 with urllib.request.urlopen(url) as response: health[url]=response.status
services=subprocess.check_output(['systemctl','show','vlr-api','vlr-frontend','-p','Id','-p','MainPID','-p','ActiveState','-p','ActiveEnterTimestamp','-p','NRestarts'],text=True)
assert 'MainPID=61821' in services and 'MainPID=308' in services
pid=int(pathlib.Path('/tmp/vlr-preview/preview.pid').read_text());assert pathlib.Path(f'/proc/{pid}/cwd').resolve()==dst
assert not any(x.startswith(b'NODE_OPTIONS=') for x in pathlib.Path(f'/proc/{pid}/environ').read_bytes().split(b'\0'))
record=dict(checkedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),health=health,services=services,previewPid=pid,previewDirectory=str(dst),sourceFilesCompared=len(manifest),sourceHashes=manifest,unrelatedFilesUnchanged=True)
(out/'operations.json').write_text(json.dumps(record,indent=2)+'\n');print('Health, preview parity and unrelated-file preservation passed:',len(manifest),'files');print(services)
