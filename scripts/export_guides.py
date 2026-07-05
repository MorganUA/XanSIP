#!/usr/bin/env python3
"""Export embedded guide data to data/guides/*.json (run after editing Python sources)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "guides"


def main() -> None:
    from services.operation_guides import (
        AUDIENCES,
        FEATURED_GUIDE_ID,
        GUIDES,
        WORKFLOW_ROADMAP,
        get_operation_guides,
    )
    from services.sip_integration_guides import CATEGORIES, GUIDES as SIP_GUIDES, get_sip_integration_guides

    OUT.mkdir(parents=True, exist_ok=True)

    ops = {
        "audiences": AUDIENCES,
        "featured_guide_id": FEATURED_GUIDE_ID,
        "workflow_roadmap": WORKFLOW_ROADMAP,
        "disclaimer": get_operation_guides()["disclaimer"],
        "guides": GUIDES,
    }
    (OUT / "operations.json").write_text(
        json.dumps(ops, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    sip = {
        "categories": CATEGORIES,
        "disclaimer": get_sip_integration_guides()["disclaimer"],
        "guides": SIP_GUIDES,
    }
    (OUT / "sip-integration.json").write_text(
        json.dumps(sip, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Exported {OUT / 'operations.json'} ({len(GUIDES)} guides)")
    print(f"Exported {OUT / 'sip-integration.json'} ({len(SIP_GUIDES)} guides)")


if __name__ == "__main__":
    main()
