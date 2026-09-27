"""Private rollback archive procedure used in this review; never overwrites."""
import pathlib,tarfile,json,hashlib,shutil,os,time
root=pathlib.Path('/opt/vlr-api');private=pathlib.Path('/home/builder/vlr-gates-private');out=root/'docs/verification/release-gates/2026-09-27'
archive=private/'frontend-rollback.tar.gz';assert not archive.exists();start=time.time()
items=['frontend/.next','frontend/node_modules','frontend/package.json','frontend/package-lock.json','frontend/next.config.ts','frontend/public']
with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
 for f in items:tar.add(root/f,arcname=f,recursive=True)
os.chmod(archive,0o600)
config=private/'configuration';config.mkdir(mode=0o700)
for src,name in [(root/'.env','backend.env'),(root/'frontend/.env','frontend.env'),(pathlib.Path('/etc/systemd/system/vlr-api.service'),'vlr-api.service'),(pathlib.Path('/etc/systemd/system/vlr-frontend.service'),'vlr-frontend.service')]:
 shutil.copy2(src,config/name);os.chmod(config/name,0o600)
manifest={};logical=0
with tarfile.open(archive) as tar:
 for member in tar:
  if member.isfile():
   digest=hashlib.sha256(tar.extractfile(member).read()).hexdigest();assert digest==hashlib.sha256((root/member.name).read_bytes()).hexdigest();manifest[member.name]=digest;logical+=member.size
r={'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'regular_files':len(manifest),'logical_bytes':logical,'seconds':round(time.time()-start,2),'all_archive_files_match_source':True,'build_id':(root/'frontend/.next/BUILD_ID').read_text().strip(),'exact_source_revision':'unattested','private_config_files':['backend.env','frontend.env','vlr-api.service','vlr-frontend.service']}
(private/'frontend-manifest.json').write_text(json.dumps(manifest));(out/'rollback-artifact.json').write_text(json.dumps(r,indent=2)+'\n')
