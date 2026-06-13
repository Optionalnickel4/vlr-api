# DEPLOY — vlr-api on LXC 289 (Mewtwo / prox)

Container: 192.168.1.35, Debian 13. Postgres + Redis live in the same container.

## 0. (on prox) create the container if not done
See the pct create command you already have. Then `pct enter 289`.

## 1. (in container) base packages
```bash
apt update && apt -y upgrade
apt -y install python3 python3-venv python3-pip git curl postgresql redis-server
systemctl enable --now postgresql redis-server
```

## 2. Postgres db + user
```bash
sudo -u postgres psql <<'SQL'
CREATE USER vlr WITH PASSWORD 'CHANGEME';
CREATE DATABASE vlr OWNER vlr;
SQL
```

## 3. service user + code
```bash
adduser --system --group --home /opt/vlr-api vlr
# copy the project to /opt/vlr-api (git clone, scp, or rsync from your dev box)
cd /opt/vlr-api
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .
```

## 4. env
```bash
cp .env.example .env
# edit .env: set the real Postgres password to match step 2
chmod 600 .env
chown vlr:vlr .env
```

## 5. VERIFY SELECTORS against live vlr.gg (important)
The selectors were written without live access. Confirm they match real markup:
```bash
sudo -u vlr .venv/bin/python -m app.scrapers.verify
```
Expect "ALL SELECTORS MATCHED". If any entity reports 0, open
`app/scrapers/selectors.py`, fix the offending selector (compare to the live page
HTML via `curl -A "Mozilla/5.0" https://www.vlr.gg/matches/results | less`), and
re-run until green. Re-run the unit tests after edits: `.venv/bin/pytest -q`.

## 6. systemd
```bash
chown -R vlr:vlr /opt/vlr-api
cp deploy/vlr-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now vlr-api
systemctl status vlr-api --no-pager
```
(The scheduler runs inside the API by default. Only install vlr-scheduler.service
if you set VLR_ENABLE_SCHEDULER=false for multi-worker setups.)

## 7. smoke test
```bash
curl -s localhost:8000/health
curl -s localhost:8000/api/v1/rankings | head -c 400
# docs in a browser: http://192.168.1.35:8000/docs
```

## 8. reverse proxy (optional, matches your Caddy pattern)
Point Caddy at 192.168.1.35:8000, e.g. vlr.jushosting.dev.

## 9. frontend (Next.js) service — managed, not a dev process
The broadcast dashboard in `frontend/` runs as its own systemd unit on port 3000
(`next start`, the **production build** — never `next dev`). Server-side fetch only to
`http://127.0.0.1:8000/api/v1`; the browser never calls vlr-api directly. Confirm container
Node ≥ 18.18/20 for Next 16.

```bash
# Node (if not already present) — e.g. nodesource 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt -y install nodejs

# build as the service user (vlr must OWN the build output + node_modules)
chown -R vlr:vlr /opt/vlr-api/frontend
cd /opt/vlr-api/frontend
sudo -u vlr cp .env.example .env   # then edit: VLR_API_BASE + the Twitch creds (below)
sudo -u vlr chmod 640 .env         # Twitch secret: owner-rw, group-r, world-none
chown vlr:vlr .env
sudo -u vlr bash -lc 'cd /opt/vlr-api/frontend && npm ci && npm run build'
```

`frontend/.env` (gitignored — never committed). The featured-streamers bar needs a Twitch app
(client-credentials grant; the secret stays server-side, never shipped to the browser):
```
VLR_API_BASE=http://127.0.0.1:8000/api/v1
TWITCH_CLIENT_ID=<from dev.twitch.tv app>
TWITCH_CLIENT_SECRET=<from dev.twitch.tv app>
TWITCH_FEATURED=s0mcs,tarik,shanks_ttv,yinsu   # comma-sep custom handles (optional)
```

### systemd unit — lives OUTSIDE the repo, so it's reproduced here verbatim
The unit file at `/etc/systemd/system/vlr-frontend.service` cannot be tracked in the repo in
place. Recreate it exactly on a container rebuild:
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
# (paste the unit above, then:)
systemctl daemon-reload
systemctl enable --now vlr-frontend
systemctl status vlr-frontend --no-pager
# reach it directly (Caddy out of scope): http://192.168.1.35:3000
```

### operating both services — `start-services.sh` (repo root)
One entrypoint for the API + frontend pair (tracked in the repo):
```bash
./start-services.sh start     # start both
./start-services.sh stop      # stop both (web first, then api)
./start-services.sh restart   # rebuild frontend, then restart both
./start-services.sh build     # rebuild frontend + restart web only
./start-services.sh status    # show both
```

## Updating later
```bash
# API
cd /opt/vlr-api && git pull && .venv/bin/pip install -e .
systemctl restart vlr-api
# frontend (rebuild the production bundle, then restart the web unit)
./start-services.sh build      # == npm run build (as vlr) + systemctl restart vlr-frontend
```
