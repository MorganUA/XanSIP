#!/usr/bin/env python3
"""Build GitHub Pages bundle for Telegram Mini App (docs/mini/)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "api" / "static" / "mini"
OUT = ROOT / "docs" / "mini"
API_URL = os.environ.get("MINI_API_URL", "https://185.192.23.225").rstrip("/")


def main() -> int:
    if not SRC.is_dir():
        print(f"Missing source: {SRC}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("mini.css", "mini.js", "softphone.mjs"):
        shutil.copy2(SRC / name, OUT / name)

    html = (SRC / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="/static/mini/mini.css"', 'href="./mini.css"')
    html = html.replace('src="/static/mini/mini.js"', 'src="./mini.js"')
    if 'name="mini-api"' not in html:
        html = html.replace(
            "<title>",
            f'<meta name="mini-api" content="{API_URL}">\n  <title>',
            1,
        )
    (OUT / "index.html").write_text(html, encoding="utf-8")

    docs_root = ROOT / "docs"
    docs_root.mkdir(exist_ok=True)
    (docs_root / ".nojekyll").touch()
    (docs_root / "index.html").write_text(
        '<!DOCTYPE html><html><head>'
        '<meta http-equiv="refresh" content="0;url=mini/">'
        '<link rel="canonical" href="mini/">'
        "</head><body></body></html>",
        encoding="utf-8",
    )

    print(f"Built {OUT} (API → {API_URL})")
    print(f"Pages URL: https://bakaidesign1-a11y.github.io/XanSIP/mini/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
