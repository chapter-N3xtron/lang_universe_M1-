#!/bin/zsh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=(docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml")

case "${1:-}" in
  start)
    "${COMPOSE[@]}" up -d --build
    ;;
  stop)
    "${COMPOSE[@]}" down
    ;;
  restart-frontend)
    "${COMPOSE[@]}" restart frontend
    ;;
  status)
    "${COMPOSE[@]}" ps
    ;;
  logs)
    "${COMPOSE[@]}" logs -f "${2:-frontend}"
    ;;
  *)
    print "Usage: $0 {start|stop|restart-frontend|status|logs [service]}"
    exit 1
    ;;
esac
