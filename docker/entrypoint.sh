#!/bin/sh
set -e

echo "[entrypoint] Waiting for database..."
until python - <<'PY'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from core.config import settings

async def check():
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    finally:
        await engine.dispose()

asyncio.run(check())
PY
do
  echo "[entrypoint] Database not ready, retry in 2s..."
  sleep 2
done

echo "[entrypoint] Starting application..."
exec "$@"
