"""Запуск Alembic upgrade (отдельный процесс — без конфликта с event loop uvicorn)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def upgrade_head() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade failed ({result.returncode}): {result.stderr or result.stdout}"
        )
