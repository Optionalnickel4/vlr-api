import concurrent.futures,datetime,json,os,pathlib,shutil,subprocess,tempfile
root=pathlib.Path('/opt/vlr-api'); dest=pathlib.Path(tempfile.mkdtemp(prefix='vlr-probe-build-'))
shutil.copytree(root/'frontend',dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('node_modules','.next','.env*','*.tsbuildinfo'))
(dest/'node_modules').symlink_to(root/'frontend/node_modules',target_is_directory=True)
logs=root/'docs/verification/probe/2026-09-27/logs';logs.mkdir(exist_ok=True)
commands={'backend':([str(root/'.venv/bin/pytest'),'-q'],root),'frontend':(['npm','test'],root/'frontend'),'lint':(['npm','run','lint'],root/'frontend'),'typescript':(['./node_modules/.bin/tsc','--noEmit','--incremental','false'],root/'frontend'),'build':(['npm','run','build','--','--webpack'],dest)}
def run(item):
 name,(cmd,cwd)=item; start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 env=dict(os.environ,NO_COLOR='1',NEXT_TELEMETRY_DISABLED='1',VLR_API_BASE='http://127.0.0.1:9/api/v1',TWITCH_CLIENT_ID='',TWITCH_CLIENT_SECRET='',TWITCH_FEATURED='')
 with (logs/(name+'.log')).open('w') as f:
  f.write(f'UTC start: {start}\nCommand: {cmd}\nDirectory: {cwd}\n');f.flush()
  try: result=subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300);code=result.returncode
  except subprocess.TimeoutExpired: code=124
  end=datetime.datetime.now(datetime.timezone.utc).isoformat();f.write(f'\nUTC end: {end}\nExit code: {code}\n')
 row=dict(command=cmd,directory=str(cwd),started=start,ended=end,exit_code=code); print(name,code,flush=True);return name,row
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=dict(pool.map(run,commands.items()))
(root/'docs/verification/probe/2026-09-27/checks.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(any(r['exit_code'] for r in results.values()))
