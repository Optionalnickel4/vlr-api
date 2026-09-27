"""Runs only inside the disposable bubblewrap namespace."""
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import threading
import time
import urllib.request
import uuid

W = Path('/work')
PG = '/usr/lib/postgresql/17/bin/'
processes = []
report = {'passed': False, 'stages': [], 'normal_schema_startup_required': True}
fixture_calls = []
marker = 'Recovery' + uuid.uuid4().hex


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def run(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=30).strip()


def start(args, name, env=None, cwd=W):
    with (W / (name + '.log')).open('w') as log:
        p = subprocess.Popen(args, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
    processes.append((name, p))
    return p


def stop(p, codes=(0, -signal.SIGTERM)):
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=15)
    report.setdefault('service_exits', []).append({'pid': p.pid, 'code': p.returncode})
    require(p.returncode in codes, 'Non-graceful service exit: ' + str(p.returncode))


def wait(check, seconds=40):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            value = check()
            if value:
                return value
        except (OSError, ValueError, subprocess.CalledProcessError):
            pass
        time.sleep(.1)
    raise RuntimeError('Readiness/acceptance deadline exceeded')


def get(url, json_body=True):
    with urllib.request.urlopen(url, timeout=5) as r:
        body = r.read(2_000_001)
        require(len(body) <= 2_000_000, 'Response too large')
        return json.loads(body) if json_body else body.decode()


def sql(query):
    return run([PG + 'psql', '-h', '/work/socket', '-U', 'builder', '-d', 'recovery', '-At', '-v', 'ON_ERROR_STOP=1', '-c', query])


def redis(*args):
    return run(['redis-cli', '-s', '/work/redis.sock', *args])


def fingerprint():
    result = {}
    for table in ('match_results', 'player_snapshots', 'ranking_snapshots', 'team_snapshots'):
        rows = sql(f'SELECT row_to_json(t)::text FROM {table} t ORDER BY id')
        result[table] = {'sha256': hashlib.sha256(rows.encode()).hexdigest(),
                         'rows': int(sql(f'SELECT count(*) FROM {table}'))}
    return result


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        fixture_calls.append(self.path)
        if self.path != '/matches/results':
            self.send_error(404)
            return
        body = Path('/runner/results.html').read_text().replace('Team Alpha', marker).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    require(Path('/artifacts').is_dir() and not Path('/opt/vlr-api').exists(), 'Missing mount isolation')
    require(socket.if_nameindex() == [(1, 'lo')], 'Unexpected network interface')
    # Bubblewrap already brings up namespace-local loopback. Verify it without
    # privileged network mutation (some LXC policies reject SIOCSIFFLAGS).
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        flags = struct.unpack('16sH14s', fcntl.ioctl(sock, 0x8913, struct.pack('16sH14s', b'lo', 0, b'')))[1]
        require(flags & 0x1, 'Private loopback is down')
    report['network_interfaces'] = socket.if_nameindex()
    report['routes'] = Path('/proc/net/route').read_text()
    data = json.loads((W / 'input.json').read_text())
    server = ThreadingHTTPServer(('127.0.0.1', 8120), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (W / 'socket').mkdir()
    run([PG + 'initdb', '-D', '/work/pg', '-U', 'builder', '--encoding=UTF8', '--locale=C', '--auth=trust'])
    pg = start([PG + 'postgres', '-D', '/work/pg', '-k', '/work/socket', '-h', '',
                '-c', 'log_statement=ddl'], 'postgres')
    wait(lambda: run([PG + 'psql', '-h', '/work/socket', '-U', 'builder', '-d', 'postgres', '-Atc', 'SELECT 1']) == '1')
    run([PG + 'createdb', '-h', '/work/socket', '-U', 'builder', 'recovery'])
    cache = start(['redis-server', '--port', '0', '--unixsocket', '/work/redis.sock',
                   '--unixsocketperm', '700', '--save', '', '--appendonly', 'no'], 'redis')
    wait(lambda: redis('PING') == 'PONG')
    report['storage_pids'] = {'postgres': pg.pid, 'redis': cache.pid}
    preserved = None
    report['strategy'] = data.get('strategy', 'historical-recovery')
    report['purpose'] = data.get('purpose', 'historical-recovery')
    for stage in data.get('stages', ['candidate', 'historical']):
        backend = data[stage + '_backend']
        frontend = data[stage + '_frontend']
        b = Path(backend['root'])
        source = b / backend['source']
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/work', 'LANG': 'C.UTF-8',
               'PYTHONHOME': str(b / backend['runtime_home']),
               'PYTHONPATH': str(source) + ':' + str(b / backend['runtime_home'] / 'lib/python3.13/site-packages'),
               'PYTHONDONTWRITEBYTECODE': '1', 'RECOVERY_STAGE': stage, 'RECOVERY_SOURCE': str(source),
               'VLR_DATABASE_URL': 'postgresql+asyncpg://builder@/recovery?host=/work/socket',
               'VLR_REDIS_URL': 'unix:///work/redis.sock', 'VLR_BASE_URL': 'http://127.0.0.1:8120',
               'VLR_ENABLE_SCHEDULER': 'true', 'VLR_MIN_REQUEST_INTERVAL': '0.01',
               'VLR_MAX_RETRIES': '1', 'VLR_REQUEST_TIMEOUT': '2'}
        redis('DEL', 'vlr:lastrun:results')
        calls_before = len(fixture_calls)
        api = start([str(b / backend['python']), '/runner/backend_worker.py'], stage + '-api', env, source)
        wait(lambda: get('http://127.0.0.1:8000/health') == {'status': 'ok'})
        scheduled = W / (stage + '-scheduler.json')
        wait(lambda: scheduled.exists() and redis('GET', 'vlr:lastrun:results'))
        require(json.loads(scheduled.read_text())['success'], 'Scheduler refresh failed')
        require(len(fixture_calls) > calls_before, 'Scheduler did not fetch fixture')
        status = get('http://127.0.0.1:8000/api/v1/status')
        require(status['checks'] == {'postgres': True, 'redis': True}, 'Storage readiness failed')
        results = get('http://127.0.0.1:8000/api/v1/matches/results')
        require(marker in json.dumps(results), 'Real fixture parser/cache/API path not populated')
        require(marker in sql('SELECT team_a FROM match_results'), 'Scheduler did not persist results')
        require(sql("SELECT count(*) FROM information_schema.columns WHERE table_name='match_results' AND column_name IN ('team_a_id','team_b_id')") == '2', 'Migration columns absent')
        if preserved is not None:
            require(fingerprint() == preserved, 'History changed across normal historical startup/refresh')
        # Next may write its runtime cache; each selected frontend is copied to a
        # separate sandbox-only working directory; the verified artifact is RO.
        import shutil
        webroot = W / (stage + '-frontend')
        shutil.copytree(frontend['root'], webroot)
        for directory in [webroot, *webroot.rglob('*')]:
            if directory.is_dir():
                directory.chmod(directory.stat().st_mode | 0o200)
        webenv = {'PATH': '/usr/bin:/bin', 'HOME': '/work', 'NODE_ENV': 'production',
                  'NEXT_TELEMETRY_DISABLED': '1', 'VLR_API_BASE': 'http://127.0.0.1:8000/api/v1'}
        node = str(webroot / 'node') if (webroot / 'node').is_file() else '/usr/bin/node'
        web = start([node, str(webroot / 'node_modules/next/dist/bin/next'), 'start',
                     '-H', '127.0.0.1', '-p', '3000'], stage + '-frontend', webenv, webroot)
        page = wait(lambda: get('http://127.0.0.1:3000/results', False))
        require(marker in page, 'Frontend route does not contain runtime fixture data')
        build_id = (webroot / '.next/BUILD_ID').read_text().strip()
        require(build_id == frontend['build_id'], 'Restored frontend BUILD_ID mismatch')
        if stage == 'candidate':
            # Newer than initial schema/fixture data, and before the artifact switch.
            sql("INSERT INTO match_results(vlr_id,team_a,captured_at) VALUES ('gate2-newer','newer-history',now()); "
                "INSERT INTO player_snapshots(player_id,alias,agent_stats,captured_at) VALUES ('gate2','newer-player','[]',now()); "
                "INSERT INTO ranking_snapshots(team_id,team,captured_at) VALUES ('gate2','newer-ranking',now()); "
                "INSERT INTO team_snapshots(team_id,name,roster,captured_at) VALUES ('gate2','newer-team','[]',now())")
            redis('SET', 'review:gate2:newer', marker)
            redis('SET', 'review:gate2:lease', marker, 'EX', '600')
            preserved = fingerprint()
            report['before_switch'] = preserved
        require(redis('GET', 'review:gate2:newer') == marker, 'Persistent cache sentinel lost')
        require(redis('GET', 'review:gate2:lease') == marker and int(redis('TTL', 'review:gate2:lease')) > 0, 'Cache lease lost')
        require(pg.poll() is None and cache.poll() is None, 'Storage restarted or exited')
        identity = json.loads((W / (stage + '-identity.json')).read_text())
        require(Path(f'/proc/{web.pid}/cwd').resolve() == webroot, 'Frontend working directory mismatch')
        require(identity['pid'] == api.pid, 'API process identity mismatch')
        require(identity['runtime_sha256'] == backend['files'][backend['python']], 'Runtime hash mismatch')
        report['stages'].append({'stage': stage, 'selected_backend': backend['root'], 'selected_frontend': frontend['root'], 'api': identity, 'frontend_pid': web.pid,
                                'frontend_process_stat': Path(f'/proc/{web.pid}/stat').read_text(),
                                'node_sha256': hashlib.sha256(Path(f'/proc/{web.pid}/exe').read_bytes()).hexdigest(),
                                'frontend_build_id': build_id, 'fixture_marker_rendered': True,
                                'scheduler': json.loads(scheduled.read_text()), 'history': fingerprint()})
        # Next 16.2.7 exits 143 after its awaited SIGTERM cleanup, by design.
        stop(web, (0, 143))
        stop(api)
        shutdown = json.loads((W / (stage + '-shutdown.json')).read_text())
        require(shutdown == {'lifespan_exited': True, 'scheduler_stopped': True}, 'Lifespan/scheduler shutdown incomplete')
        report['stages'][-1]['shutdown'] = shutdown
    report['after_switch'] = fingerprint()
    require(report['after_switch'] == report['before_switch'], 'Final history mismatch')
    require(all(path == '/matches/results' for path in fixture_calls), 'Unexpected fixture request')
    report['fixture_requests'] = fixture_calls
    stop(cache)
    stop(pg)
    server.shutdown()
    report['passed'] = True


try:
    main()
except Exception as exc:
    report['error'] = type(exc).__name__ + ': ' + str(exc)
finally:
    for name, process in reversed(processes):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                report['passed'] = False
                report.setdefault('forced_cleanup', []).append(name)
    report['private_processes_stopped'] = all(p.poll() is not None for _, p in processes)
    (W / 'result.json').write_text(json.dumps(report, indent=2))
raise SystemExit(0 if report['passed'] else 1)
