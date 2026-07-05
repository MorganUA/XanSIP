"""Load DEPLOY_* variables from project .env into os.environ."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_PREFIX = "DEPLOY_"


def load_deploy_env(*, root: Path | None = None) -> dict[str, str]:
    """Populate os.environ from .env for DEPLOY_* keys (existing env wins)."""
    env_path = (root or ROOT) / ".env"
    loaded: dict[str, str] = {}
    if not env_path.is_file():
        return loaded

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key.startswith(DEPLOY_PREFIX):
            continue
        value = value.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = value
        loaded[key] = os.environ[key]
    return loaded
