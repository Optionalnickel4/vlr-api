import asyncio,os,pathlib,json,subprocess,hashlib,sys,time
sys.path.insert(0,'/opt/vlr-api')
from app.core.config import get_settings
from sqlalchemy.engine import make_url
import asyncpg
P=pathlib.Path('/home/builder/vlr-gates-private');O=pathlib.Path('/opt/vlr-api/docs/verification/release-gates/2026-09-27');SOCK='/tmp/vlr-gates-9301682/pg/socket'
async def main():
 s=make_url(get_settings().database_url);c=await asyncpg.connect(host=s.host,port=s.port or 5432,user=s.username,password=s.password,database=s.database,timeout=10)
 r={'commands':['pg_dump --format=custom --no-owner --no-acl --snapshot=<exported read-only snapshot> --file=<new private file>','pg_restore --list <new dump>','createdb -h <private socket> -p 55439 restored','pg_restore --exit-on-error --no-owner --no-acl -h <private socket> -p 55439 -d restored <new dump>'],'started':time.time()}
 async with c.transaction(isolation='repeatable_read',readonly=True):
  snap=await c.fetchval('SELECT pg_export_snapshot()');r['database_bytes']=await c.fetchval('SELECT pg_database_size(current_database())')
  tables=await c.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
  counts={x['tablename']:await c.fetchval('SELECT count(*) FROM "'+x['tablename'].replace('"','""')+'"') for x in tables}
  r['source_snapshot_counts']=counts
  env=dict(os.environ,PGPASSWORD=s.password or '',PGHOST=s.host or '',PGPORT=str(s.port or 5432),PGUSER=s.username or '',PGDATABASE=s.database or '',PGCONNECT_TIMEOUT='10')
  dump=P/'production-20260927.dump'
  assert not dump.exists()
  with (P/'pg-dump.log').open('w') as log:
   proc=await asyncio.create_subprocess_exec('/usr/bin/pg_dump','-Fc','--no-owner','--no-acl','--snapshot='+snap,'-f',str(dump),env=env,stdout=log,stderr=log)
   r['dump_exit']=await asyncio.wait_for(proc.wait(),90)
  assert r['dump_exit']==0
 await c.close()
 r['backup_bytes']=dump.stat().st_size;r['backup_sha256']=hashlib.sha256(dump.read_bytes()).hexdigest()
 listing=subprocess.run(['pg_restore','--list',str(dump)],capture_output=True);r['archive_list_exit']=listing.returncode;r['archive_entries']=sum(not x.startswith(b';') and bool(x.strip()) for x in listing.stdout.splitlines())
 c=await asyncpg.connect(host=SOCK,port=55439,user='builder',database='postgres');await c.execute('CREATE DATABASE restored');await c.execute('CREATE DATABASE cold');await c.close()
 with (P/'pg-restore.log').open('w') as log:
  proc=await asyncio.create_subprocess_exec('pg_restore','--exit-on-error','--no-owner','--no-acl','-h',SOCK,'-p','55439','-U','builder','-d','restored',str(dump),stdout=log,stderr=log)
  r['restore_exit']=await asyncio.wait_for(proc.wait(),90)
 c=await asyncpg.connect(host=SOCK,port=55439,user='builder',database='restored')
 r['restored_counts']={t:await c.fetchval('SELECT count(*) FROM "'+t.replace('"','""')+'"') for t in counts};r['restored_database_bytes']=await c.fetchval('SELECT pg_database_size(current_database())');await c.close()
 r['counts_match']=r['restored_counts']==counts;r['pass']=r['counts_match'] and r['restore_exit']==0;r['ended']=time.time()
 (O/'backup-restore.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
asyncio.run(main())
