#!/bin/sh
set -e
cd "$(dirname "$0")/.."

case "$1" in
  up)
    docker compose up -d --build
    ;;
  down)
    docker compose down
    ;;
  restart)
    docker compose restart bot api
    ;;
  logs)
    docker compose logs -f --tail=100 bot
    ;;
  logs-api)
    docker compose logs -f --tail=100 api
    ;;
  ps)
    docker compose ps
    ;;
  migrate)
    docker compose exec bot python -m alembic upgrade head
    ;;
  *)
    echo "Usage: $0 {up|down|restart|logs|ps|migrate}"
    exit 1
    ;;
esac
