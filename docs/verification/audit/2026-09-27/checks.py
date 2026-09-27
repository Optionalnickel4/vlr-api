import subprocess, concurrent.futures, pathlib, datetime, os, json
base=pathlib.Path('/tmp/vlr-audit')
commands={'backend':['/opt/vlr-api/.venv/bin/pytest','-q'],'tests':['npm','test'],'lint':['npm','run','lint'],'typescript':['./node_modules/.bin/tsc','--noEmit','--incremental','false'],'build':['npm','run','build','--','--webpack']}
def run(item):
 name,cmd=item;cwd='/tmp/vlr-preview/audit-delivery' if name=='build' else '/opt/vlr-api' if name=='backend' else '/opt/vlr-api/frontend'
 env=dict(os.environ,NO_COLOR='1',NEXT_TELEMETRY_DISABLED='1',VLR_API_BASE='http://127.0.0.1:8101/api/v1',TWITCH_CLIENT_ID='',TWITCH_CLIENT_SECRET='',TWITCH_FEATURED='')
 start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (base/'logs'/f'{name}.log').open('w') as log:
  log.write(f'UTC start: {start}\nCommand: {" ".join(cmd)}\nDirectory: {cwd}\n\n');log.flush()
  result=subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
  end=datetime.datetime.now(datetime.timezone.utc).isoformat();log.write(f'\nUTC end: {end}\nExit code: {result.returncode}\n')
 record=dict(command=cmd,directory=cwd,started=start,ended=end,exitCode=result.returncode);print(name,json.dumps(record),flush=True);return name,record
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=dict(pool.map(run,commands.items()))
(base/'check-results.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(any(r['exitCode'] for r in results.values()))
