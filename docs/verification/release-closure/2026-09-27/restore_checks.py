"""Restore retained artifacts to disk; never connect to production storage."""
import pathlib,os,subprocess,json,tarfile,hashlib,shutil,threading,time
B=pathlib.Path('/home/builder/vlr-recovery-check');P=pathlib.Path('/home/builder/vlr-gates-private');O=pathlib.Path('/opt/vlr-api/docs/verification/release-closure/2026-09-27')
R=B/'restored-portable/backend';pg=B/'pg';pg.mkdir(mode=0o700);(pg/'socket').mkdir();front=B/'frontend-restored';front.mkdir(mode=0o700)
r={'initial_free_bytes':shutil.disk_usage(B).free};samples=[];stop=threading.Event()
def monitor():
 while not stop.wait(.25):samples.append(shutil.disk_usage(B).free)
threading.Thread(target=monitor,daemon=True).start()
def run(args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout
pgbin='/usr/lib/postgresql/17/bin/'
started=False
try:
 with tarfile.open(P/'frontend-rollback.tar.gz') as t:t.extractall(front,filter='data')
 manifest=json.loads((P/'frontend-manifest.json').read_text());bad=[f for f,h in manifest.items() if hashlib.sha256((front/f).read_bytes()).hexdigest()!=h];assert not bad
 r['frontend']={'files_verified':len(manifest),'mismatches':bad,'build_id':(front/'frontend/.next/BUILD_ID').read_text().strip()}
 run([pgbin+'initdb','-D',str(pg/'data'),'--encoding=UTF8','--locale=C','--auth=trust'])
 run([pgbin+'pg_ctl','-D',str(pg/'data'),'-l',str(pg/'log'),'-o',f"-k {pg/'socket'} -p 55440 -h ''",'-w','start']);started=True
 args=['-h',str(pg/'socket'),'-p','55440','-U',os.environ['USER']]
 run([pgbin+'createdb',*args,'restored'])
 dump=P/'production-20260927.dump';assert hashlib.sha256(dump.read_bytes()).hexdigest()=='4c50d9f02a7a408e7816be4d439647ef5e3976dcac5ef4bec74f4da9e5ee8d4c'
 run([pgbin+'pg_restore','--exit-on-error','--no-owner','--no-acl',*args,'-d','restored',str(dump)])
 tables=['match_results','player_snapshots','ranking_snapshots','team_snapshots']
 def counts():return {t:int(run([pgbin+'psql',*args,'-d','restored','-Atc',f'SELECT count(*) FROM {t}']).strip()) for t in tables}
 r['database_counts_before']=counts()
 env={k:v for k,v in os.environ.items() if not k.startswith('VLR_')}
 env.update(PYTHONHOME=str(R/'runtime'),PYTHONPATH=str(R/'runtime/lib/python3.13/site-packages')+':'+str(R/'source'),VLR_DATABASE_URL=f"postgresql+asyncpg://{os.environ['USER']}@/restored?host={pg/'socket'}&port=55440",VLR_REDIS_URL='unix:///home/builder/vlr-recovery-check/absent-redis.sock',VLR_ENABLE_SCHEDULER='false',VLR_BASE_URL='http://127.0.0.1:1')
 # Read-only database history + health; ASGI calls have no real HTTP socket.
 probe='''import sys,socket,asyncio,json

def audit(event,args):
 if event=='socket.connect' and isinstance(args[1],tuple):raise RuntimeError('TCP blocked in isolated restore probe')
sys.addaudithook(audit)
import httpx,app.main,uvicorn,asyncpg,redis,sqlalchemy
from app.jobs.scheduler import build_scheduler
async def main():
 out={'interpreter':sys.executable,'prefix':sys.prefix,'app_module':app.main.__file__,'dependencies':{x.__name__:getattr(x,'__version__','unknown') for x in [httpx,uvicorn,asyncpg,redis,sqlalchemy]},'scheduler_jobs_constructed':len(build_scheduler().get_jobs()),'scheduler_started':False,'lifespan_executed':False,'responses':[]}
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.main.app),base_url='http://isolated') as c:
  for path in ['/health','/api/v1/history/results?limit=2']:
   response=await c.get(path);body=response.json();assert response.status_code==200
   out['responses'].append({'path':path,'status':response.status_code,'shape':type(body).__name__,'length':len(body)})
 from app.core.db import engine
 await engine.dispose()
 print(json.dumps(out))
asyncio.run(main())
'''
 result=subprocess.run([str(R/'runtime/bin/python3.13'),'-c',probe],cwd=R/'source',env=env,capture_output=True,text=True,timeout=30)
 if result.returncode:raise RuntimeError(result.stderr)
 r['backend']=json.loads(result.stdout);r['database_counts_after']=counts();assert r['database_counts_before']==r['database_counts_after']
 r['database_restore_matches_prior_snapshot']=r['database_counts_before']=={'match_results':1572,'player_snapshots':14792,'ranking_snapshots':106077,'team_snapshots':1009};assert r['database_restore_matches_prior_snapshot']
 r['backend_full_rollback_verified']=False;r['limitation']='Known historical source only; lifespan/scheduler not executed; Redis unavailable; no attestation to loaded production worker. Health/history prove only emergency read API restoration.'
finally:
 if started:run([pgbin+'pg_ctl','-D',str(pg/'data'),'-m','fast','-w','stop'])
 stop.set()
 r['minimum_sampled_free_bytes']=min(samples,default=shutil.disk_usage(B).free);r['final_free_bytes']=shutil.disk_usage(B).free
 r['allocated_bytes']={p: int(run(['du','-s','-B1',str(B/p)]).split()[0]) for p in ['frontend-restored','pg','bundle-portable','restored-portable']}
 (O/'restoration.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
