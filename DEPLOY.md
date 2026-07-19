# DEPLOY — vlr-api + frontend

Environment-agnostic deployment guide. It targets a single Linux host (Debian/Ubuntu
assumed) running Postgres + Redis locally alongside the API and the Next.js frontend.
There is nothing machine-specific hardcoded — set the variables below once and the rest
of the commands follow. It also runs fine on WSL2 with systemd enabled.

## 0. Parameters — set these to match your host

```bash
export VLR_USER=vlr                       # service account the units run as
export VLR_HOME=/opt/vlr-api              # install dir (repo checkout)
export VLR_DB=vlr                         # postgres database + role name
export VLR_DB_PASS='change-me'            # postgres role password
export PG_VER=16                          # your postgres major version (see: pg_lsclusters)
```

Everywhere below that says `$VLR_HOME`, `$VLR_USER`, etc. is those values.

## 1. Base packages

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install python3 python3-venv python3-pip git curl postgresql redis-server
sudo systemctl enable --now postgresql redis-server
```

For the frontend you also need Node ≥ 20 (Next 16):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt -y install nodejs
```

## 2. Postgres — MUST be UTF-8

> ⚠️ **Critical.** A `SQL_ASCII` cluster throws `asyncpg.UntranslatableCharacterError`
> on accented player/team names (`LEVIATÁN`, `Türkiye`, `Ričardas Lukaševičius`) and
> **silently drops those records** — and because refresh writes cache before DB, they
> appear to self-heal on retry, masking the loss. A per-database `ENCODING 'UTF8'` is
> NOT enough: `template1` inherits the cluster encoding and keeps minting broken DBs.

Verify first:

```bash
sudo -u postgres psql -c "SHOW server_encoding;"   # expect UTF8
sudo -u postgres psql -c "\l"                        # check template1's Encoding
```

If it's `SQL_ASCII`, recreate the cluster (this destroys existing cluster data — back up first if it holds anything you care about):

```bash
locale -a | grep -i utf || sudo locale-gen en_US.UTF-8
sudo systemctl stop postgresql
sudo pg_dropcluster $PG_VER main --stop
sudo pg_createcluster $PG_VER main --locale=en_US.UTF-8 --start
```

Then create the role + database:

```bash
sudo -u postgres psql <<SQL
CREATE USER $VLR_DB WITH PASSWORD '$VLR_DB_PASS';
CREATE DATABASE $VLR_DB OWNER $VLR_DB ENCODING 'UTF8';
SQL
```

## 3. Service user + code

```bash
sudo adduser --system --group --home $VLR_HOME $VLR_USER
# place the repo at $VLR_HOME (git clone / scp / rsync from your dev box)
cd $VLR_HOME
sudo -u $VLR_USER python3 -m venv .venv
sudo -u $VLR_USER .venv/bin/pip install -U pip
sudo -u $VLR_USER .venv/bin/pip install -e .
```

## 4. Environment

```bash
cp .env.example .env
# edit .env: set VLR_DATABASE_URL to the UTF-8 db/role from step 2
chmod 600 .env
sudo chown $VLR_USER:$VLR_USER .env
```

`VLR_DATABASE_URL` should be
`postgresql+asyncpg://$VLR_DB:$VLR_DB_PASS@localhost:5432/$VLR_DB`.

## 5. VERIFY SELECTORS against live vlr.gg (important)

The selectors are checked against real markup, not assumed. On this host (which has
internet), run:

```bash
sudo -u $VLR_USER .venv/bin/python -m app.scrapers.verify
```

Expect **`ALL SELECTORS MATCHED`**. If any entity reports 0 rows (or a semantic check
fails), vlr changed its markup — fix `app/scrapers/selectors.py`, re-run until green,
then re-run the unit tests: `sudo -u $VLR_USER .venv/bin/pytest -q`.

## 6. API systemd unit

`deploy/vlr-api.service` is a template that assumes `User=vlr` and
`/opt/vlr-api`. **If you changed `$VLR_USER` or `$VLR_HOME`, adapt the `User=`,
`WorkingDirectory=`, `EnvironmentFile=`, and `ExecStart=` paths accordingly** before
installing.

```bash
sudo chown -R $VLR_USER:$VLR_USER $VLR_HOME
sudo cp deploy/vlr-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vlr-api
sudo systemctl status vlr-api --no-pager
```

The scraping scheduler runs inside the API by default (`VLR_ENABLE_SCHEDULER=true`).
Only install `deploy/vlr-scheduler.service` (adapting its paths the same way) if you set
`VLR_ENABLE_SCHEDULER=false` for a multi-worker setup where scraping must not be
duplicated per worker.

## 7. Smoke test

```bash
curl -s localhost:8000/health
curl -s localhost:8000/api/v1/rankings | head -c 400
# interactive docs in a browser: http://<host>:8000/docs
```

## 8. Reverse proxy (optional)

Put the API and/or frontend behind your reverse proxy of choice (Caddy, nginx, …).
The API needs no CORS — the frontend fetches it server-side, and the browser never
calls it directly.

## 9. Frontend (Next.js) service

Runs as its own unit on port 3000 (`next start` — the **production build**, never
`next dev`). Server-side fetch only to `http://127.0.0.1:8000/api/v1`.

```bash
sudo chown -R $VLR_USER:$VLR_USER $VLR_HOME/frontend
cd $VLR_HOME/frontend
sudo -u $VLR_USER cp .env.example .env    # then edit: VLR_API_BASE (+ optional Twitch creds)
sudo -u $VLR_USER chmod 640 .env          # Twitch secret: owner-rw, group-r, world-none
sudo -u $VLR_USER bash -lc "cd $VLR_HOME/frontend && npm ci && npm run build"
```

`frontend/.env` (gitignored). The featured-streamers bar is optional — without the
Twitch vars the bar just renders empty:

```
VLR_API_BASE=http://127.0.0.1:8000/api/v1
TWITCH_CLIENT_ID=<from dev.twitch.tv app>
TWITCH_CLIENT_SECRET=<from dev.twitch.tv app>
TWITCH_FEATURED=handle1,handle2           # comma-sep custom handles (optional)
```

The frontend systemd unit lives at `/etc/systemd/system/vlr-frontend.service` (outside
the repo). Adapt `User=`/`WorkingDirectory=` to your `$VLR_USER`/`$VLR_HOME`:

```ini
[Unit]
Description=vlr-api frontend (Next.js)
After=network-online.target vlr-api.service
Wants=network-online.target
[Service]
Type=simple
User=vlr
WorkingDirectory=/opt/vlr-api/frontend
ExecStart=/usr/bin/npm run start
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vlr-frontend
sudo systemctl status vlr-frontend --no-pager
```

### Operator wrapper (recommended pattern)

A thin script that maps `start` / `stop` / `restart` / `rebuild` / `status` / `logs`
onto these units saves a lot of typing. The one non-negotiable rule: **the frontend must
be rebuilt (`npm run build`) before its service restarts** — `next start` serves the
compiled `.next/`, so a restart without a rebuild silently serves stale UI. Make the
`rebuild` verb build *then* restart the web unit. (This repo carries such a wrapper for
its own machine; it's gitignored as environment-specific.)

## WSL2 note

The whole stack runs on WSL2 with systemd enabled. Add to `/etc/wsl.conf` and restart
the distro (`wsl --shutdown` from Windows):

```ini
[boot]
systemd=true
```

## Updating later

```bash
# API
cd $VLR_HOME && git pull && sudo -u $VLR_USER .venv/bin/pip install -e .
sudo systemctl restart vlr-api

# frontend — REBUILD before restart (next start serves the compiled build)
cd $VLR_HOME/frontend && sudo -u $VLR_USER bash -lc "npm ci && npm run build"
sudo systemctl restart vlr-frontend
```
