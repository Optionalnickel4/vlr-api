#!/usr/bin/env bash
set -euo pipefail

API=vlr-api
WEB=vlr-frontend
FRONTEND_DIR=/opt/vlr-api/frontend

build_frontend() {
  echo "==> Building frontend (npm run build)…"
  sudo -u vlr bash -lc "cd $FRONTEND_DIR && npm run build"
}

case "${1:-}" in
  start)
    systemctl start $API $WEB
    ;;
  stop)
    systemctl stop $WEB $API
    ;;
  restart)
    build_frontend
    systemctl restart $API $WEB
    ;;
  build)
    build_frontend
    systemctl restart $WEB
    ;;
  status)
    systemctl status $API $WEB --no-pager
    ;;
  *)
    echo "usage: $0 {start|stop|restart|build|status}"
    echo "  start    — start both services"
    echo "  stop     — stop both (web first, then api)"
    echo "  restart  — rebuild frontend, then restart both"
    echo "  build    — rebuild frontend + restart web only"
    echo "  status   — show both"
    exit 1
    ;;
esac
