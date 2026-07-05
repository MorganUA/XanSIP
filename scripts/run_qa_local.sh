#!/bin/sh
# Local QA/TA gate: static checks + pytest (Docker API image when available).
set -eu
cd "$(dirname "$0")/.."

echo "== compileall =="
python3 -m compileall -q services api bot db scripts

run_pytest() {
  python3 -m pytest tests/ -q --tb=short "$@"
}

if command -v docker >/dev/null 2>&1 && [ -f docker-compose.yml ]; then
  echo "== pytest (docker compose run api) =="
  docker compose run --rm --no-deps api python -m pytest tests/ -q --tb=short
elif python3 -c "import asyncpg, itsdangerous" 2>/dev/null; then
  echo "== pytest (local venv) =="
  run_pytest
else
  echo "Install deps: pip install -r requirements-dev.txt"
  echo "Or run: docker compose run --rm api python -m pytest tests/"
  exit 1
fi

if [ "${QA_SKIP_LIVE:-0}" = "1" ]; then
  echo "== qa_deep skipped (QA_SKIP_LIVE=1) =="
  exit 0
fi

if command -v docker >/dev/null 2>&1 && docker compose ps api 2>/dev/null | grep -q Up; then
  echo "== qa_deep (docker api) =="
  docker compose exec -T api python scripts/qa_deep.py
elif python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" 2>/dev/null; then
  echo "== qa_deep (local API) =="
  QA_BASE_URL="${QA_BASE_URL:-http://127.0.0.1:8000}" python3 scripts/qa_deep.py
else
  echo "== qa_deep skipped (start stack: docker compose up -d) =="
fi

echo ""
echo "Tip: full gate with report — python3 scripts/qa_ta_gate.py"
echo "QA local gate passed."
