#!/usr/bin/env python3
"""Deploy sipcrm project to remote server via SFTP + docker compose."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import paramiko

from scripts.ssh_utils import connect_ssh

REMOTE_DIR = os.environ.get("DEPLOY_DIR", "/opt/sipcrm")

SKIP_DIRS = {
    ".git",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "backups",
    "extracted",
    ".unpack-tmp",
    "__MACOSX",
}

SKIP_FILES = {
    ".DS_Store",
    "sip-crm.zip",
    "main.env.zip",
    "readme.md",
}

SKIP_SUFFIXES = {".jpg", ".jpeg", ".png", ".zip"}


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = set(rel.parts)
    if parts & SKIP_DIRS:
        return True
    if path.name in SKIP_FILES:
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    if path.name == ".env":
        return True
    return False


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_file() and not should_skip(path):
            files.append(path)
    return files


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_path: str) -> None:
    parts = remote_path.strip("/").split("/")
    current = ""
    for part in parts:
        current += f"/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def upload_tree(sftp: paramiko.SFTPClient) -> None:
    ensure_remote_dir(sftp, REMOTE_DIR)
    for local_path in iter_files():
        rel = local_path.relative_to(ROOT).as_posix()
        remote_path = f"{REMOTE_DIR}/{rel}"
        ensure_remote_dir(sftp, os.path.dirname(remote_path))
        sftp.put(str(local_path), remote_path)
        if rel.endswith(".sh"):
            sftp.chmod(remote_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        print(f"uploaded {rel}")


def _env_lookup(lines: list[str], key: str) -> str | None:
    for item in lines:
        k, _, v = item.strip().partition("=")
        if k == key:
            return v
    return None


def build_redis_url_for_compose(lines: list[str]) -> str:
    password = _env_lookup(lines, "REDIS_PASSWORD") or os.getenv("REDIS_PASSWORD", "")
    if password:
        return f"redis://:{password}@redis:6379/0"
    return "redis://redis:6379/0"


def build_env_content() -> str:
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise SystemExit(".env not found locally")

    lines = env_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    redis_url_written = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        key, _, value = stripped.partition("=")
        if key == "DATABASE_URL":
            user = _env_lookup(lines, "POSTGRES_USER")
            password = _env_lookup(lines, "POSTGRES_PASSWORD")
            db = _env_lookup(lines, "POSTGRES_DB")
            out.append(
                f"DATABASE_URL=postgresql+asyncpg://{user}:{password}@postgres:5432/{db}"
            )
        elif key == "REDIS_URL":
            out.append(f"REDIS_URL={build_redis_url_for_compose(lines)}")
            redis_url_written = True
        else:
            out.append(line)

    if not redis_url_written:
        out.append(f"REDIS_URL={build_redis_url_for_compose(lines)}")

    return "\n".join(out) + "\n"


def run_remote(client: paramiko.SSHClient) -> None:
    commands = [
        f"cd {REMOTE_DIR} && docker compose down --remove-orphans 2>/dev/null || true",
        f"cd {REMOTE_DIR} && docker compose build bot api",
        f"cd {REMOTE_DIR} && docker compose up -d",
        f"cd {REMOTE_DIR} && sleep 8 && docker compose ps",
        f"cd {REMOTE_DIR} && docker compose logs --tail=30 bot",
        f"cd {REMOTE_DIR} && docker compose logs --tail=20 api",
    ]
    for cmd in commands:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)
        if code != 0:
            raise SystemExit(f"Command failed ({code}): {cmd}")


def wait_for_health(client: paramiko.SSHClient, *, attempts: int = 30, delay_sec: int = 2) -> None:
    cmd = (
        f"for i in $(seq 1 {attempts}); do "
        "curl -sf http://127.0.0.1:8000/api/health >/dev/null && exit 0; "
        f"sleep {delay_sec}; done; exit 1"
    )
    print("\n>>> Waiting for API health...")
    stdin, stdout, stderr = client.exec_command(f"cd {REMOTE_DIR} && {cmd}", get_pty=True)
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise SystemExit("API health check timed out after deploy")


def run_remote_qa(client: paramiko.SSHClient) -> None:
    wait_for_health(client)
    cmd = (
        f"cd {REMOTE_DIR} && "
        "docker compose exec -T bot python -c \"import bot.main\" && "
        "docker compose exec -T api python scripts/qa_ta_gate.py"
    )
    print("\n>>> QA gate: bot import + qa_ta_gate")
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    if code != 0:
        raise SystemExit(f"Post-deploy QA failed ({code})")


def main() -> None:
    from scripts.deploy_env import load_deploy_env

    load_deploy_env()
    client = connect_ssh()

    sftp = client.open_sftp()
    try:
        upload_tree(sftp)
        env_content = build_env_content()
        with sftp.file(f"{REMOTE_DIR}/.env", "w") as remote_env:
            remote_env.write(env_content)
        print("uploaded .env")
    finally:
        sftp.close()

    run_remote(client)
    run_remote_qa(client)
    client.close()
    print("\nDeploy finished successfully.")


if __name__ == "__main__":
    main()
