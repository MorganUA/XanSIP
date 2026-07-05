#!/usr/bin/env python3
"""
One-time SSH setup for deploy/backup/remote QA.

Preferred flow (generates dedicated key, installs on server, writes .env):

  python3 scripts/setup_deploy_ssh.py --password 'ROOT_PASSWORD'

After setup, deploy works without password:

  python3 scripts/deploy_server.py

Other modes:
  --scan-only     Refresh .deploy/known_hosts only
  --test          Test current credentials from .env
  --print-pubkey  Show public key to paste into server authorized_keys
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import paramiko

from scripts.deploy_env import load_deploy_env
from scripts.ssh_utils import (
    KNOWN_HOSTS,
    discover_ssh_key,
    ensure_known_hosts,
    test_connection,
)

DEFAULT_KEY = Path("~/.ssh/sipcrm_deploy_ed25519")


def _env_path() -> Path:
    return ROOT / ".env"


def _read_env_lines() -> list[str]:
    path = _env_path()
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _upsert_env(keys: dict[str, str]) -> None:
    """Merge keys into .env; never print secret values."""
    path = _env_path()
    lines = _read_env_lines()

    for key, value in keys.items():
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"{key}={value}")

    if not path.is_file():
        example = ROOT / ".env.example"
        if example.is_file():
            lines = example.read_text(encoding="utf-8").splitlines()
            for key, value in keys.items():
                replaced = False
                for i, line in enumerate(lines):
                    if line.strip().startswith(f"{key}=") or line.strip().startswith(f"# {key}="):
                        lines[i] = f"{key}={value}"
                        replaced = True
                        break
                if not replaced:
                    lines.append(f"{key}={value}")
        else:
            lines = [f"{k}={v}" for k, v in keys.items()]

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Updated {_env_path().name}: {', '.join(keys.keys())}")


def generate_key(key_path: Path) -> tuple[Path, Path]:
    key_path = key_path.expanduser()
    pub_path = Path(str(key_path) + ".pub")
    if key_path.is_file():
        print(f"Key already exists: {key_path}")
        return key_path, pub_path

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
            "sipcrm-deploy",
        ],
        check=True,
    )
    print(f"Generated {key_path}")
    return key_path, pub_path


def install_pubkey_with_password(
    host: str,
    user: str,
    password: str,
    pub_path: Path,
) -> None:
    pubkey = pub_path.read_text(encoding="utf-8").strip()
    if not pubkey:
        raise SystemExit(f"Empty public key: {pub_path}")

    ensure_known_hosts(host)
    client = paramiko.SSHClient()
    client.load_host_keys(str(KNOWN_HOSTS))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    print(f"Installing public key on {user}@{host} (password bootstrap)...")
    client.connect(
        hostname=host,
        username=user,
        password=password,
        timeout=30,
        look_for_keys=False,
        allow_agent=False,
    )
    try:
        cmd = (
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            f"grep -qxF '{pubkey}' ~/.ssh/authorized_keys 2>/dev/null || "
            f"echo '{pubkey}' >> ~/.ssh/authorized_keys && "
            "chmod 600 ~/.ssh/authorized_keys"
        )
        stdin, stdout, stderr = client.exec_command(cmd)
        code = stdout.channel.recv_exit_status()
        err = stderr.read().decode().strip()
        if code != 0:
            raise SystemExit(f"authorized_keys install failed ({code}): {err}")
        print("Public key installed on server.")
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup SSH key auth for SIP CRM deploy")
    parser.add_argument("--host", default=os.environ.get("DEPLOY_HOST", "185.192.23.225"))
    parser.add_argument("--user", default=os.environ.get("DEPLOY_USER", "root"))
    parser.add_argument(
        "--key",
        default=str(DEFAULT_KEY),
        help=f"Private key path (default: {DEFAULT_KEY})",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("DEPLOY_PASSWORD", ""),
        help="Root password for one-time bootstrap (not saved unless already in .env)",
    )
    parser.add_argument("--scan-only", action="store_true", help="Only refresh known_hosts")
    parser.add_argument("--test", action="store_true", help="Test SSH with current .env")
    parser.add_argument("--print-pubkey", action="store_true", help="Print public key")
    args = parser.parse_args()

    load_deploy_env()

    if args.test:
        ok, msg = test_connection()
        print(msg)
        return 0 if ok else 1

    if args.scan_only:
        path = ensure_known_hosts(args.host)
        print(f"Known hosts updated: {path}")
        return 0

    key_path, pub_path = generate_key(Path(args.key))

    if args.print_pubkey:
        print(pub_path.read_text(encoding="utf-8").strip())
        return 0

    ensure_known_hosts(args.host)

    if args.password:
        install_pubkey_with_password(args.host, args.user, args.password, pub_path)
    elif not discover_ssh_key():
        print(
            "\nNo --password given and key not yet on server.\n"
            "Either:\n"
            f"  python3 scripts/setup_deploy_ssh.py --password 'ROOT_PASSWORD'\n"
            f"  ssh-copy-id -i {pub_path} {args.user}@{args.host}\n"
        )
        _upsert_env(
            {
                "DEPLOY_HOST": args.host,
                "DEPLOY_USER": args.user,
                "DEPLOY_SSH_KEY": str(key_path.expanduser()),
            }
        )
        return 1

    _upsert_env(
        {
            "DEPLOY_HOST": args.host,
            "DEPLOY_USER": args.user,
            "DEPLOY_SSH_KEY": str(key_path.expanduser()),
        }
    )

    os.environ["DEPLOY_SSH_KEY"] = str(key_path.expanduser())
    os.environ.pop("DEPLOY_PASSWORD", None)

    ok, msg = test_connection()
    print(msg)
    if ok:
        print("\nReady. Deploy with: python3 scripts/deploy_server.py")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
