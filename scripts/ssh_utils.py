"""Shared SSH connection for deploy, backup, and remote QA."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import paramiko

from scripts.deploy_env import ROOT, load_deploy_env

HOST = os.environ.get("DEPLOY_HOST", "185.192.23.225")
USER = os.environ.get("DEPLOY_USER", "root")
PASSWORD = os.environ.get("DEPLOY_PASSWORD", "")
SSH_KEY = os.environ.get("DEPLOY_SSH_KEY", "")
SSH_KEY_PASSPHRASE = os.environ.get("DEPLOY_SSH_KEY_PASSPHRASE", "")

DEPLOY_DIR = ROOT / ".deploy"
KNOWN_HOSTS = DEPLOY_DIR / "known_hosts"

# Dedicated project key first, then common defaults.
DEFAULT_KEY_PATHS = (
    Path("~/.ssh/sipcrm_deploy_ed25519"),
    Path("~/.ssh/id_ed25519"),
    Path("~/.ssh/id_rsa"),
)


def deploy_config_summary() -> str:
    load_deploy_env()
    host = os.environ.get("DEPLOY_HOST", HOST)
    user = os.environ.get("DEPLOY_USER", USER)
    key = os.environ.get("DEPLOY_SSH_KEY", "")
    has_pw = bool(os.environ.get("DEPLOY_PASSWORD", ""))
    parts = [f"{user}@{host}"]
    if key:
        parts.append(f"key={key}")
    elif has_pw:
        parts.append("password=set")
    else:
        parts.append("auth=missing")
    return " ".join(parts)


def discover_ssh_key() -> Path | None:
    """Return first usable private key path."""
    load_deploy_env()
    explicit = os.environ.get("DEPLOY_SSH_KEY", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None

    for candidate in DEFAULT_KEY_PATHS:
        path = candidate.expanduser()
        if path.is_file():
            return path
    return None


def ensure_known_hosts(host: str, *, port: int = 22) -> Path:
    """Fetch host key via ssh-keyscan into .deploy/known_hosts."""
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    try:
        out = subprocess.run(
            ["ssh-keyscan", "-p", str(port), "-H", host],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "ssh-keyscan not found. Install OpenSSH client or set DEPLOY_SSH_KEY manually."
        ) from exc

    if out.returncode != 0 or not out.stdout.strip():
        raise SystemExit(
            f"Could not fetch host key for {host}:{port}. "
            f"Check network/firewall.\n{out.stderr.strip()}"
        )

    existing = KNOWN_HOSTS.read_text(encoding="utf-8") if KNOWN_HOSTS.is_file() else ""
    lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
    merged = existing
    for ln in lines:
        if ln not in existing:
            merged += ln + "\n"
    KNOWN_HOSTS.write_text(merged, encoding="utf-8")
    return KNOWN_HOSTS


def auth_methods_available() -> list[str]:
    load_deploy_env()
    methods: list[str] = []
    if discover_ssh_key():
        methods.append("ssh_key")
    if os.environ.get("DEPLOY_PASSWORD", ""):
        methods.append("password")
    if os.environ.get("SSH_AUTH_SOCK"):
        methods.append("ssh_agent")
    return methods


def connect_ssh(*, timeout: int = 30, host: str | None = None, user: str | None = None) -> paramiko.SSHClient:
    load_deploy_env()
    host = host or os.environ.get("DEPLOY_HOST", HOST)
    user = user or os.environ.get("DEPLOY_USER", USER)
    password = os.environ.get("DEPLOY_PASSWORD", PASSWORD)
    key_path = discover_ssh_key()
    passphrase = os.environ.get("DEPLOY_SSH_KEY_PASSPHRASE", SSH_KEY_PASSPHRASE)

    if not key_path and not password:
        _print_auth_help(host, user)
        raise SystemExit(1)

    try:
        ensure_known_hosts(host)
    except SystemExit:
        if not password:
            raise

    client = paramiko.SSHClient()
    if KNOWN_HOSTS.is_file():
        client.load_host_keys(str(KNOWN_HOSTS))
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict = {
        "hostname": host,
        "username": user,
        "timeout": timeout,
        "allow_agent": True,
        "look_for_keys": False,
    }

    auth_label = "unknown"
    if key_path:
        connect_kwargs["key_filename"] = str(key_path)
        if passphrase:
            connect_kwargs["passphrase"] = passphrase
        auth_label = f"key {key_path}"
    elif password:
        connect_kwargs["password"] = password
        auth_label = "password"

    print(f"Connecting to {user}@{host} ({auth_label})...")
    try:
        client.connect(**connect_kwargs)
    except paramiko.ssh_exception.SSHException as exc:
        _print_connect_error(host, user, exc)
        raise SystemExit(1) from exc
    except (socket.timeout, OSError) as exc:
        raise SystemExit(f"Network error connecting to {host}: {exc}") from exc

    return client


def test_connection(*, timeout: int = 15) -> tuple[bool, str]:
    try:
        client = connect_ssh(timeout=timeout)
        stdin, stdout, stderr = client.exec_command("echo ok", timeout=timeout)
        out = stdout.read().decode().strip()
        code = stdout.channel.recv_exit_status()
        client.close()
        if code == 0 and out == "ok":
            return True, f"SSH OK ({deploy_config_summary()})"
        return False, f"Unexpected response: {out!r} exit={code}"
    except SystemExit as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def _print_auth_help(host: str, user: str) -> None:
    print(
        f"\nNo SSH credentials for {user}@{host}.\n\n"
        "Recommended (one-time setup, key-based auth):\n"
        f"  python3 scripts/setup_deploy_ssh.py --password 'YOUR_ROOT_PASSWORD'\n\n"
        "Or manually:\n"
        f"  ssh-keygen -t ed25519 -f ~/.ssh/sipcrm_deploy_ed25519 -N '' -C sipcrm-deploy\n"
        f"  ssh-copy-id -i ~/.ssh/sipcrm_deploy_ed25519.pub {user}@{host}\n"
        "  echo 'DEPLOY_SSH_KEY=~/.ssh/sipcrm_deploy_ed25519' >> .env\n\n"
        "Alternative (less secure): add DEPLOY_PASSWORD=... to .env\n",
        file=sys.stderr,
    )


def _print_connect_error(host: str, user: str, exc: Exception) -> None:
    msg = str(exc).lower()
    print(f"\nSSH failed: {exc}", file=sys.stderr)
    if "authentication" in msg or "auth" in msg:
        print(
            "\nFix: run setup or install your public key on the server:\n"
            f"  python3 scripts/setup_deploy_ssh.py --password '...'\n"
            f"  # or: ssh-copy-id -i ~/.ssh/sipcrm_deploy_ed25519.pub {user}@{host}\n",
            file=sys.stderr,
        )
    elif "host key" in msg or "not found in known_hosts" in msg:
        print(
            f"\nFix: refresh host key — python3 scripts/setup_deploy_ssh.py --scan-only\n",
            file=sys.stderr,
        )
