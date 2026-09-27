#!/usr/bin/env python3
"""Run only inside bwrap: existing Node/Next, no backend/storage/network access."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

report={'passed':False,'external_network':False,'backend_or_storage_started':False}
node=None
try:
    env={'PATH':'/usr/bin:/bin','HOME':'/tmp','NODE_ENV':'production',
         'NEXT_TELEMETRY_DISABLED':'1','VLR_API_BASE':'http://127.0.0.1:9/api/v1',
         'TWITCH_CLIENT_ID':'','TWITCH_CLIENT_SECRET':'','TWITCH_FEATURED':''}
    with Path('/work/frontend.log').open('w') as log:
        node=subprocess.Popen(['/usr/bin/node','/frontend/node_modules/next/dist/bin/next','start','-H','127.0.0.1','-p','3000'],cwd='/frontend',env=env,stdout=log,stderr=subprocess.STDOUT)
    end=time.monotonic()+30
    while True:
        try:
            with urllib.request.urlopen('http://127.0.0.1:3000/',timeout=3) as response:
                body=response.read(2000000)
                assert response.status==200 and b'<html' in body
            break
        except Exception:
            if time.monotonic()>end or node.poll() is not None:raise
            time.sleep(.2)
    asset=min((p for p in Path('/frontend/.next/static').rglob('*.js') if p.is_file()),key=lambda p:p.stat().st_size)
    url='/_next/'+str(asset.relative_to('/frontend/.next'))
    with urllib.request.urlopen('http://127.0.0.1:3000'+url,timeout=5) as response:
        actual=response.read(2000000)
        assert response.status==200 and actual==asset.read_bytes()
    report.update(passed=True,build_id=Path('/frontend/.next/BUILD_ID').read_text().strip(),
                  homepage_http_status=200,homepage_bytes=len(body),asset=url,
                  asset_sha256=hashlib.sha256(actual).hexdigest(),asset_bytes=len(actual))
except Exception as exc:
    report['error']=type(exc).__name__+': '+str(exc)
finally:
    if node and node.poll() is None:
        node.terminate()
        try:node.wait(timeout=15)
        except subprocess.TimeoutExpired:
            node.kill();node.wait();report['passed']=False;report['forced_cleanup']=True
    report['private_frontend_stopped']=not node or node.poll() is not None
    if node:
        report['exit_code']=node.returncode
        report['passed']=report['passed'] and node.returncode in (0,143)
    Path('/work/result.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
