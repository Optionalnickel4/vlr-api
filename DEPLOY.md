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

## Updating later
```bash
cd /opt/vlr-api && git pull && .venv/bin/pip install -e .
systemctl restart vlr-api
```
