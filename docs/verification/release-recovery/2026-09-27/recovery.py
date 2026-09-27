"""Isolated application switch; no production connections or schema startup."""
import hashlib, json, os, pathlib, subprocess, sys, time, tempfile
O=pathlib.Path(__file__).resolve().parent
B=pathlib.Path('/home/builder/vlr-recovery-check')
R=B/'restored-portable/backend'
W=pathlib.Path(os.environ['REVIEW_WORK']) if 'REVIEW_WORK' in os.environ else pathlib.Path(tempfile.mkdtemp(prefix='application-switch-',dir=B))
PG='/usr/lib/postgresql/17/bin/'
def run(args):
 return subprocess.run(args,check=True,capture_output=True,text=True,timeout=45).stdout

def worker():
 def audit(event,args):
  if event=='socket.connect':
   address=args[1]
   if not isinstance(address,str) or not address.startswith(str(B)+'/'):
    raise RuntimeError('Non-private socket connection blocked')
 sys.addaudithook(audit)
 import app.main, uvicorn
 from app.core.db import check_db
 async def read_check():
  assert await check_db()
 app.main.init_db=read_check # Explicit no-migrations boundary; NOT normal startup proof.
 async def exercise():
  from datetime import datetime, timezone
  from app.jobs.scheduler import get_scheduler
  sched=get_scheduler()
  assert sched.running and len(sched.get_jobs())==8
  sched.modify_job('live_matches',next_run_time=datetime.now(timezone.utc))
 original=app.main.app.router.lifespan_context
 from contextlib import asynccontextmanager
 @asynccontextmanager
 async def lifespan(app):
  async with original(app):
   await exercise()
   yield
  (W/(os.environ['REVIEW_STAGE']+'-shutdown')).write_text('lifespan exited')
 app.main.app.router.lifespan_context=lifespan
 (W/(os.environ['REVIEW_STAGE']+'-identity.json')).write_text(json.dumps({'app_file':app.main.__file__,'interpreter':sys.executable,'prefix':sys.prefix,'schema_startup':'replaced with SELECT check','uvicorn':uvicorn.__version__}))
 uvicorn.run(app.main.app,uds=str(W/'api.sock'),loop='asyncio',workers=1,log_level='warning')

if len(sys.argv)>1:
 worker();sys.exit()
# Each run uses a fresh private directory.
r={'stages':[],'full_service_gate_passed':False,'normal_schema_startup_executed':False}
services=run(['systemctl','show','vlr-api','vlr-frontend','-p','MainPID','-p','ExecMainStartTimestamp'])
protected=[pathlib.Path('/opt/vlr-api')/x for x in ['.gitignore','docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md','.env','frontend/.env']]+[pathlib.Path('/etc/systemd/system')/x for x in ['vlr-api.service','vlr-frontend.service']]
hashes=lambda:{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=hashes();pg_started=False;redis_proc=None;api=None
try:
 manifest=json.loads((R/'SHA256SUMS.json').read_text())
 assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in manifest.items())
 r['artifact_files_verified']=len(manifest)
 run([PG+'pg_ctl','-D',str(B/'pg/data'),'-l',str(W/'postgres.log'),'-o',f"-k {B/'pg/socket'} -p 55440 -h ''",'-w','start']);pg_started=True
 args=['-h',str(B/'pg/socket'),'-p','55440','-U',os.environ['USER'],'-d','restored','-Atc']
 def sql(query):return run([PG+'psql',*args,query]).strip()
 tables=['match_results','player_snapshots','ranking_snapshots','team_snapshots']
 def fingerprint():return {t:sql(f"SELECT count(*) || ':' || md5(string_agg(row_to_json(t)::text, '' ORDER BY id)) FROM {t} t") for t in tables}
 r['before_new_data']=fingerprint()
 redis_log=open(W/'redis.log','w')
 redis_proc=subprocess.Popen(['redis-server','--port','0','--unixsocket',str(W/'redis.sock'),'--unixsocketperm','700','--save','','--appendonly','no'],stdout=redis_log,stderr=subprocess.STDOUT)
 for _ in range(100):
  if (W/'redis.sock').exists():break
  time.sleep(.05)
 def redis(*args):return run(['redis-cli','-s',str(W/'redis.sock'),*args]).strip()
 redis('SET','vlr:live','[]','EX','600')
 for stage,source in [('candidate',pathlib.Path('/home/builder/vlr-release-review-9301682')),('fallback',R/'source')]:
  if stage=='candidate':
   sql(f"INSERT INTO match_results(vlr_id,team_a,captured_at) VALUES ('{W.name}','review sentinel',now())")
   redis('SET','review:newer-data','after-backup')
   redis('SET','vlr:rankings:all:retained','[]')
   redis('SET','vlr:rankings:all:refresh','failed','EX','300')
   r['after_new_data']=fingerprint()
  redis('DEL','vlr:lastrun:live_matches') # private heartbeat only; require a new completion per process
  env={k:v for k,v in os.environ.items() if not k.startswith(('VLR_','PYTHON'))}
  env.update(PYTHONHOME=str(R/'runtime'),PYTHONPATH=str(source)+':'+str(R/'runtime/lib/python3.13/site-packages'),PYTHONDONTWRITEBYTECODE='1',REVIEW_STAGE=stage,REVIEW_WORK=str(W),VLR_DATABASE_URL=f"postgresql+asyncpg://{os.environ['USER']}@/restored?host={B/'pg/socket'}&port=55440",VLR_REDIS_URL='unix://'+str(W/'redis.sock'),VLR_ENABLE_SCHEDULER='true',VLR_BASE_URL='http://127.0.0.1:1')
  log=open(W/(stage+'.log'),'w')
  api=subprocess.Popen([str(R/'runtime/bin/python3.13'),str(pathlib.Path(__file__).resolve()),'worker'],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
  def get(path):return json.loads(run(['curl','--silent','--show-error','--fail','--max-time','5','--unix-socket',str(W/'api.sock'),'http://isolated'+path]))
  for _ in range(100):
   assert api.poll() is None, (W/(stage+'.log')).read_text()
   try:
    health=get('/health');break
   except subprocess.CalledProcessError:time.sleep(.1)
  status=get('/api/v1/status');history=get('/api/v1/history/results?limit=2')
  assert health=={'status':'ok'} and status['checks']=={'postgres':True,'redis':True}
  assert len(status['scheduler'])==8 and all(j['next_run'] for j in status['scheduler'])
  for _ in range(50):
   if redis('GET','vlr:lastrun:live_matches'):break
   time.sleep(.1)
  assert redis('GET','vlr:lastrun:live_matches')
  assert fingerprint()==r['after_new_data']
  assert redis('GET','review:newer-data')=='after-backup'
  assert redis('GET','vlr:rankings:all:retained')=='[]'
  assert int(redis('TTL','vlr:rankings:all:refresh'))>0
  r['stages'].append({'stage':stage,'identity':json.loads((W/(stage+'-identity.json')).read_text()),'health':health,'checks':status['checks'],'jobs_with_next_run':len(status['scheduler']),'fresh_job_heartbeat':redis('GET','vlr:lastrun:live_matches'),'history_rows':len(history),'database_fingerprints':fingerprint(),'new_cache_value_preserved':True,'retained_and_lease_preserved':True})
  api.terminate();api.wait(timeout=10);assert api.returncode in (0,-15) and (W/(stage+'-shutdown')).exists();r['stages'][-1]['shutdown_returncode']=api.returncode;api=None;log.close()
 r['application_switch_passed_with_startup_substitution']=True
finally:
 if api is not None and api.poll() is None:api.terminate();api.wait(timeout=10)
 if redis_proc is not None:redis_proc.terminate();redis_proc.wait(timeout=10)
 if pg_started:run([PG+'pg_ctl','-D',str(B/'pg/data'),'-m','fast','-w','stop'])
 r['production_services_unchanged']=services==run(['systemctl','show','vlr-api','vlr-frontend','-p','MainPID','-p','ExecMainStartTimestamp'])
 r['protected_files_unchanged']=before==hashes()
 r['private_processes_stopped']=True
 (O/'recovery.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
