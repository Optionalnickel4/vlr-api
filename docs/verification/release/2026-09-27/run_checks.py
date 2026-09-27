import concurrent.futures,datetime,json,os,pathlib,subprocess
root=pathlib.Path('/home/builder/vlr-release-review-9301682'); logs=pathlib.Path('/opt/vlr-api/docs/verification/release/2026-09-27')
def run(name,cmd,cwd):
 env=dict(os.environ,PYTHONPATH=str(root),VLR_ENABLE_SCHEDULER='false',VLR_DATABASE_URL='postgresql+asyncpg://invalid:invalid@127.0.0.1:1/invalid',VLR_REDIS_URL='redis://127.0.0.1:1/0',VLR_BASE_URL='http://127.0.0.1:1',VLR_API_BASE='http://127.0.0.1:9/api/v1',TWITCH_CLIENT_ID='',TWITCH_CLIENT_SECRET='',TWITCH_FEATURED='',NO_COLOR='1',NEXT_TELEMETRY_DISABLED='1')
 start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (logs/(name+'-final.log')).open('w') as f:
  f.write(f'Commit: 9301682c4165d7507e49d6ad7678d14ca9df377e\nCommand: {cmd}\nStarted: {start}\n');f.flush()
  try:r=subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=360); code=r.returncode
  except subprocess.TimeoutExpired:code=124
  f.write(f'\nExit code: {code}\n')
 row=dict(command=cmd,started=start,ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit_code=code);print(name,code,flush=True);return name,row
jobs=[('backend',['/opt/vlr-api/.venv/bin/python','-m','pytest','-q'],root),('frontend',['npm','test'],root/'frontend'),('lint',['npm','run','lint'],root/'frontend')]
rows={}
for job in jobs:
 k,v=run(*job);rows[k]=v
for job in [('build',['npm','run','build','--','--webpack'],root/'frontend'),('typescript',['./node_modules/.bin/tsc','--noEmit','--incremental','false'],root/'frontend')]:
 k,v=run(*job);rows[k]=v
(logs/'checks-final.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(any(x['exit_code'] for x in rows.values()))
