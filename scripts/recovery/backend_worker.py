"""Observe real lifespan; accelerate one real scheduled fixture refresh only."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

stage = os.environ['RECOVERY_STAGE']
root = Path(os.environ['RECOVERY_SOURCE']).resolve()
observed = set()


def profile(frame, event, arg):
    if event == 'call' and frame.f_code.co_name in ('init_db', 'run_migrations'):
        filename = Path(frame.f_code.co_filename).resolve()
        if filename.is_relative_to(root):
            if frame.f_code.co_name in ('init_db', 'run_migrations'):
                observed.add(frame.f_code.co_name)


sys.setprofile(profile)
import app.main
import app.core.db
import app.jobs.scheduler
import uvicorn
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

original = app.main.app.router.lifespan_context
require_original = app.main.init_db is app.core.db.init_db
if not require_original:
    raise RuntimeError('Application init_db identity differs from normal db.init_db')


def write(name, data):
    Path('/work', stage + '-' + name + '.json').write_text(json.dumps(data, indent=2))


@asynccontextmanager
async def lifespan(app):
    async with original(app):
        if observed != {'init_db', 'run_migrations'}:
            raise RuntimeError('Normal schema startup/migrations were not observed')
        sys.setprofile(None)
        # Parameter app is the ASGI object, not the imported package.
        from app.jobs.scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler is not app_main_scheduler() or not scheduler.running:
            raise RuntimeError('Expected exactly the application-owned scheduler')
        jobs = scheduler.get_jobs()
        if len(jobs) != 8 or any(j.max_instances != 1 for j in jobs):
            raise RuntimeError('Unexpected scheduler jobs/concurrency')
        # Hold unrelated jobs: no live source, cron timing or accidental fixture gaps.
        # The results job's callable, parser, cache/DB writes and tracker stay real.
        for job in jobs:
            scheduler.modify_job(job.id, next_run_time=None)
        def completed(event):
            write('scheduler', {'job': event.job_id, 'success': event.exception is None,
                                'scheduler_identity': id(scheduler)})
        scheduler.add_listener(completed, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        modules = {}
        for name, module in list(sys.modules.items()):
            path = getattr(module, '__file__', None)
            if path and (name.startswith('app.') or name in ('uvicorn', 'sqlalchemy', 'asyncpg', 'redis', 'httpx')):
                p = Path(path).resolve()
                if name.startswith('app.') and not p.is_relative_to(root):
                    raise RuntimeError('Application module escaped selected artifact')
                modules[name] = {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        write('identity', {'pid': os.getpid(), 'process_stat': Path('/proc/self/stat').read_text(),
                           'interpreter': sys.executable, 'prefix': sys.prefix,
                           'runtime_sha256': hashlib.sha256(Path('/proc/self/exe').read_bytes()).hexdigest(),
                           'modules': modules, 'normal_startup_calls': sorted(observed),
                           'scheduler_jobs': [j.id for j in jobs], 'scheduler_identity': id(scheduler)})
        scheduler.modify_job('results', next_run_time=datetime.now(timezone.utc))
        yield
    await asyncio.sleep(0)  # APScheduler schedules its shutdown callback on the loop.
    write('shutdown', {'lifespan_exited': True, 'scheduler_stopped': not scheduler.running})


def app_main_scheduler():
    import app.main
    return app.main._scheduler


app.main.app.router.lifespan_context = lifespan
uvicorn.run(app.main.app, host='127.0.0.1', port=8000, workers=1, loop='asyncio', log_level='info')
