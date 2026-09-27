"""Serial checks on the pinned archive; build peak measurements are sampled."""
import datetime,json,os,pathlib,shutil,signal,subprocess,time
R=pathlib.Path('/home/builder/vlr-release-review-9301682');O=pathlib.Path('/opt/vlr-api/docs/verification/release-gates/2026-09-27');(O/'logs').mkdir(exist_ok=True)
env=dict(os.environ,PYTHONPATH=str(R),VLR_ENABLE_SCHEDULER='false',VLR_DATABASE_URL='postgresql+asyncpg://invalid:invalid@127.0.0.1:1/invalid',VLR_REDIS_URL='redis://127.0.0.1:1/0',VLR_BASE_URL='http://127.0.0.1:1',VLR_API_BASE='http://127.0.0.1:9/api/v1',TWITCH_CLIENT_ID='',TWITCH_CLIENT_SECRET='',TWITCH_FEATURED='',NO_COLOR='1',NEXT_TELEMETRY_DISABLED='1')
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file() and not x.is_symlink()) if p.exists() else 0
def rss_tree(pid):
 rows={}
 for d in pathlib.Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   stat=(d/'stat').read_text().split(') ',1)[1].split();rows[int(d.name)]=(int(stat[1]),int(stat[21])*os.sysconf('SC_PAGE_SIZE'))
  except (OSError,ValueError,IndexError):pass
 selected={pid}
 for _ in range(12):
  new={p for p,(parent,_) in rows.items() if parent in selected}
  if new<=selected:break
  selected|=new
 return sum(rows.get(p,(0,0))[1] for p in selected)
results={}
for name,cmd,cwd in [('backend',['/opt/vlr-api/.venv/bin/python','-m','pytest','-q'],R),('frontend',['npm','test'],R/'frontend'),('lint',['npm','run','lint'],R/'frontend'),('build',['npm','run','build','--','--webpack'],R/'frontend'),('typescript',['./node_modules/.bin/tsc','--noEmit','--incremental','false'],R/'frontend')]:
 if name=='build':shutil.rmtree(R/'frontend/.next') # only this task's stopped isolated build
 start=time.monotonic();row={'release':'9301682c4165d7507e49d6ad7678d14ca9df377e','command':cmd,'started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'disk_available_before':shutil.disk_usage('/').free,'peak_process_tree_rss_bytes':0,'peak_build_logical_bytes':0,'minimum_disk_available':shutil.disk_usage('/').free}
 with (O/'logs'/f'{name}.log').open('w') as log:
  p=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  while p.poll() is None:
   row['peak_process_tree_rss_bytes']=max(row['peak_process_tree_rss_bytes'],rss_tree(p.pid));row['minimum_disk_available']=min(row['minimum_disk_available'],shutil.disk_usage('/').free)
   if name=='build':row['peak_build_logical_bytes']=max(row['peak_build_logical_bytes'],size(R/'frontend/.next'))
   if time.monotonic()-start>300:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=10);break
   time.sleep(.5)
  row.update(exit_code=p.returncode,elapsed_seconds=round(time.monotonic()-start,2),disk_available_after=shutil.disk_usage('/').free)
 results[name]=row;print(json.dumps({'check':name,**row}),flush=True)
(O/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(any(r['exit_code']!=0 for r in results.values()))
