"""Load guide bundles from data/guides/*.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GUIDES_DIR = Path(__file__).resolve().parents[1] / "data" / "guides"


def load_guide_bundle(name: str) -> dict[str, Any]:
    path = GUIDES_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Guide bundle not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
