#!/usr/bin/env python3
"""
Unified QA/TA gate: compileall + pytest + bot import + qa_deep with combined report.

Usage:
  python scripts/qa_ta_gate.py              # full gate (needs deps / Docker)
  python scripts/qa_ta_gate.py --unit-only    # pytest only
  python scripts/qa_ta_gate.py --live-only  # qa_deep only
  python scripts/qa_ta_gate.py --strict     # qa_deep treats WARN as FAIL
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(cwd or ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="SIP CRM QA/TA gate")
    parser.add_argument("--unit-only", action="store_true", help="Run pytest only")
    parser.add_argument("--live-only", action="store_true", help="Run qa_deep only")
    parser.add_argument("--skip-compile", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Pass --strict to qa_deep (WARN=FAIL)")
    parser.add_argument("--skip-bot-import", action="store_true", help="Skip import bot.main smoke")
    args = parser.parse_args()

    rc = 0

    if not args.live_only and not args.skip_compile:
        rc |= run(
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "services",
                "api",
                "bot",
                "db",
                "scripts",
                "tests",
            ]
        )
        if rc:
            return rc

    if not args.live_only:
        rc |= run([sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"])
        if args.unit_only:
            return rc

    if not args.unit_only and not args.skip_bot_import:
        try:
            import aiohttp  # noqa: F401
        except ImportError:
            print("\n>>> skip import bot.main (run in bot container or install aiohttp)")
        else:
            rc |= run([sys.executable, "-c", "import bot.main"])
            if rc:
                return rc

    if not args.unit_only:
        qa_cmd = [sys.executable, str(ROOT / "scripts" / "qa_deep.py")]
        if args.strict:
            qa_cmd.append("--strict")
        rc |= run(qa_cmd)

    print("\n" + "=" * 60)
    print("QA/TA GATE:", "PASS" if rc == 0 else "FAIL")
    print("=" * 60)
    return rc


if __name__ == "__main__":
    sys.exit(main())
