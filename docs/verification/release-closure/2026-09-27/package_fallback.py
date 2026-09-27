"""Construct a known historical fallback, never claim it is the loaded worker."""
import pathlib,subprocess,shutil,tarfile,json,hashlib,os,time
R=pathlib.Path('/opt/vlr-api');B=pathlib.Path('/home/builder/vlr-recovery-check');O=R/'docs/verification/release-closure/2026-09-27';sha='139378cb7505c6257c7b69da3491e382c4ebf0bc'
bundle=B/'bundle-portable';bundle.mkdir(mode=0o700);(bundle/'source').mkdir();(bundle/'runtime/bin').mkdir(parents=True)
archive=subprocess.check_output(['git','archive',sha],cwd=R)
import io
with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(bundle/'source',filter='data')
shutil.copy2('/usr/bin/python3.13',bundle/'runtime/bin/python3.13')
shutil.copytree('/usr/lib/python3.13',bundle/'runtime/lib/python3.13',symlinks=False)
site=bundle/'runtime/lib/python3.13/site-packages';shutil.copytree(R/'.venv/lib/python3.13/site-packages',site,symlinks=False)
# Copied editable install pointed to production. Remove only copied indirection;
# launch with source cwd/PYTHONPATH and verify all imported app modules.
for p in site.glob('__editable__*vlr*'):
 if p.is_file():p.unlink()
(site/'vlr_api-0.1.0.dist-info/direct_url.json').write_text(json.dumps({'url':'file:../../../../source','dir_info':{'editable':False}})+'\n')
metadata={'fallback_source_sha':sha,'exact_running_source':False,'runtime_origin':'current on-disk Python 3.13.5 and installed dependencies, not attested loaded-worker versions','launch':'runtime/bin/python3.13 -m uvicorn app.main:app --lifespan off --workers 1','startup_scope':'schema-preserving emergency API; lifespan off also disables in-process scheduler','source_tree':subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=R,text=True).strip()}
(bundle/'MANIFEST.json').write_text(json.dumps(metadata,indent=2)+'\n')
manifest={str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file() and not p.is_symlink()}
(bundle/'SHA256SUMS.json').write_text(json.dumps(manifest,sort_keys=True)+'\n')
out=B/'backend-fallback-139378c-portable.tar.gz'
with tarfile.open(out,'w:gz',compresslevel=1) as tar:tar.add(bundle,arcname='backend')
os.chmod(out,0o600)
restored=B/'restored-portable';restored.mkdir(mode=0o700)
with tarfile.open(out) as tar:tar.extractall(restored,filter='data')
actual=restored/'backend';bad=[f for f,h in manifest.items() if hashlib.sha256((actual/f).read_bytes()).hexdigest()!=h]
r={**metadata,'archive_bytes':out.stat().st_size,'archive_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'regular_files_verified':len(manifest),'restore_mismatches':bad,'bundle_logical_bytes':sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file() and not p.is_symlink()),'artifact':str(out),'restored_directory':str(actual)}
(O/'backend-artifact.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
assert not bad
