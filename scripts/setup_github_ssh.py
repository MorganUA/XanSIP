#!/usr/bin/env python3
"""Generate SSH key for GitHub and configure ~/.ssh/config."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

KEY = Path("~/.ssh/sipcrm_github_ed25519")
HOST = "github.com"
REPO = "git@github.com:bakaidesign1-a11y/XanSIP.git"


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup SSH key for GitHub push/pull")
    parser.add_argument("--test", action="store_true", help="Test GitHub SSH auth")
    args = parser.parse_args()

    if args.test:
        r = subprocess.run(
            ["ssh", "-T", f"git@{HOST}"],
            capture_output=True,
            text=True,
        )
        out = (r.stdout + r.stderr).strip()
        print(out)
        return 0 if "successfully authenticated" in out.lower() else 1

    key_path = KEY.expanduser()
    pub_path = Path(str(key_path) + ".pub")

    if not key_path.is_file():
        key_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                str(key_path),
                "-N",
                "",
                "-C",
                "sipcrm-github",
            ],
            check=True,
        )
        print(f"Generated {key_path}")
    else:
        print(f"Key exists: {key_path}")

    _ensure_ssh_config(key_path)
    pubkey = pub_path.read_text(encoding="utf-8").strip()
    print("\n--- Add this public key to GitHub ---")
    print(pubkey)
    print("\n1. Open https://github.com/settings/ssh/new")
    print("2. Title: sipcrm-github")
    print("3. Paste the key above → Add SSH key")
    print(f"\n4. Test:  python3 scripts/setup_github_ssh.py --test")
    print(f"5. Push:   git push -u origin main")
    return 0


def _ensure_ssh_config(key_path: Path) -> None:
    cfg_path = Path("~/.ssh/config").expanduser()
    block = f"""
Host {HOST}
  HostName {HOST}
  User git
  IdentityFile {key_path}
  IdentitiesOnly yes
"""
    existing = cfg_path.read_text(encoding="utf-8") if cfg_path.is_file() else ""
    marker = f"IdentityFile {key_path}"
    if marker in existing:
        print(f"SSH config already has {HOST} → {key_path}")
        return
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("a", encoding="utf-8") as f:
        f.write(block)
    cfg_path.chmod(0o600)
    print(f"Updated {cfg_path}")


if __name__ == "__main__":
    raise SystemExit(main())
