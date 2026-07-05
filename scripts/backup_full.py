#!/usr/bin/env python3
"""Полный снимок SIP CRM: код, конфигурация, git-состояние, дамп PostgreSQL с сервера."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BACKUPS_ROOT = ROOT / "backups"
REMOTE_DIR = os.environ.get("DEPLOY_DIR", "/opt/sipcrm")

# По умолчанию секреты не попадают в архив (BACKUP_INCLUDE_SECRETS=1 для полного снимка)
INCLUDE_SECRETS = os.environ.get("BACKUP_INCLUDE_SECRETS", "0").strip().lower() in ("1", "true", "yes")
GPG_PASSPHRASE = os.environ.get("BACKUP_GPG_PASSPHRASE", "")

SKIP_DIRS = {
    ".git",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "backups",
    "extracted",
    ".unpack-tmp",
    "__MACOSX",
    "node_modules",
}

SKIP_FILES = {".DS_Store", "sip-crm.zip", "main.env.zip"}
SKIP_SUFFIXES = {".pyc", ".zip", ".jpg", ".jpeg", ".png"}


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(p in SKIP_DIRS for p in rel.parts):
        return True
    if path.name in SKIP_FILES:
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def collect_git_info(dest: Path) -> dict:
    info: dict = {}
    try:
        for key, cmd in {
            "branch": ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            "commit": ["git", "rev-parse", "HEAD"],
            "commit_short": ["git", "rev-parse", "--short", "HEAD"],
            "status_porcelain": ["git", "status", "--porcelain"],
            "last_commit": ["git", "log", "-1", "--format=%h %s (%an, %ci)"],
        }.items():
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
            info[key] = (r.stdout or r.stderr).strip() if r.returncode == 0 else None
    except Exception as e:
        info["error"] = str(e)
    dest.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def archive_project_code(dest_tar: Path, *, include_secrets: bool) -> int:
    count = 0
    with tarfile.open(dest_tar, "w:gz") as tar:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or _should_skip(path):
                continue
            arcname = path.relative_to(ROOT).as_posix()
            tar.add(path, arcname=arcname)
            count += 1
        if include_secrets:
            env_path = ROOT / ".env"
            if env_path.is_file():
                tar.add(env_path, arcname=".env")
                count += 1
    return count


def ssh_client() -> paramiko.SSHClient:
    from scripts.ssh_utils import connect_ssh

    return connect_ssh()


def run_ssh(client: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def backup_server(dest_dir: Path, *, include_secrets: bool) -> dict:
    client = ssh_client()
    from scripts.ssh_utils import HOST

    result: dict = {"host": HOST, "remote_dir": REMOTE_DIR, "steps": []}

    try:
        code, out, err = run_ssh(
            client,
            f"cd {REMOTE_DIR} && docker compose ps -a 2>&1",
        )
        (dest_dir / "docker-ps.txt").write_text(out or err, encoding="utf-8")
        result["steps"].append({"docker_ps": code == 0})

        code, out, err = run_ssh(client, f"cat {REMOTE_DIR}/.env 2>/dev/null")
        if include_secrets and code == 0 and out.strip():
            (dest_dir / "server.env").write_text(out, encoding="utf-8")
            result["steps"].append({"server_env": True})
        else:
            result["steps"].append({"server_env": include_secrets and code == 0, "skipped": not include_secrets})

        dump_cmd = (
            f"cd {REMOTE_DIR} && docker compose exec -T postgres "
            f'sh -c \'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" --no-owner --no-acl\''
        )
        code, out, err = run_ssh(client, dump_cmd, timeout=600)
        sql_path = dest_dir / "postgres.sql"
        if code == 0 and out.strip():
            sql_path.write_text(out, encoding="utf-8")
            import gzip

            with gzip.open(dest_dir / "postgres.sql.gz", "wt", encoding="utf-8") as gz:
                gz.write(out)
            result["steps"].append({
                "postgres_dump": True,
                "bytes": len(out.encode()),
                "lines": out.count("\n"),
            })
        else:
            result["steps"].append({"postgres_dump": False, "error": (err or out)[:500]})

        code, health, _ = run_ssh(client, "curl -s --max-time 5 http://127.0.0.1:8000/api/health")
        result["api_health"] = health.strip() if code == 0 else None

        code, out, _ = run_ssh(
            client,
            f"cd {REMOTE_DIR} && docker compose exec -T redis redis-cli DBSIZE 2>/dev/null",
        )
        result["redis_keys"] = out.strip() if code == 0 else None

    finally:
        client.close()

    return result


def export_documentation(docs_dir: Path) -> dict:
    """Экспорт справочников и проектной документации в читаемом виде."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    stats: dict = {"files": []}

    readme = ROOT / "readme.md"
    if readme.is_file():
        shutil.copy2(readme, docs_dir / "readme.md")
        stats["files"].append("readme.md")

    env_example = ROOT / ".env.example"
    if env_example.is_file():
        shutil.copy2(env_example, docs_dir / "env.example")
        stats["files"].append("env.example")

    for name, src in (
        ("pytest.ini", ROOT / "pytest.ini"),
        ("docker-compose.yml", ROOT / "docker-compose.yml"),
    ):
        if src.is_file():
            shutil.copy2(src, docs_dir / name)
            stats["files"].append(name)

    try:
        sys.path.insert(0, str(ROOT))
        from services.operation_guides import get_operation_guides
        from services.sip_integration_guides import get_sip_integration_guides

        op = get_operation_guides()
        (docs_dir / "operation-guides.json").write_text(
            json.dumps(op, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        stats["files"].append("operation-guides.json")
        stats["operation_guides_count"] = len(op.get("guides", []))

        sip = get_sip_integration_guides()
        (docs_dir / "sip-integration-guides.json").write_text(
            json.dumps(sip, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        stats["files"].append("sip-integration-guides.json")
        stats["sip_guides_count"] = len(sip.get("guides", []))
    except Exception as e:
        stats["guides_export_error"] = str(e)

    index_lines = [
        "# SIP CRM — индекс документации в снимке",
        "",
        f"Создан: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Файлы в docs/",
        "",
    ]
    for f in sorted(docs_dir.iterdir()):
        if f.is_file():
            index_lines.append(f"- `{f.name}` ({f.stat().st_size} bytes)")
    index_lines.extend([
        "",
        "## Исходники",
        "",
        "Полный код — `code/project.tar.gz` (включая `services/operation_guides.py`,",
        "`services/sip_integration_guides.py`, Web CRM static, bot handlers).",
        "",
        "## Восстановление",
        "",
        "1. Распаковать `code/project.tar.gz` в рабочую папку",
        "2. Скопировать `local.env` или `server/server.env` в `.env`",
        "3. `docker compose up -d --build`",
        "4. БД: `gunzip -c server/postgres.sql.gz | docker compose exec -T postgres psql -U $USER $DB`",
    ])
    (docs_dir / "INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")
    stats["files"].append("INDEX.md")
    return stats


def write_manifest(backup_dir: Path, meta: dict) -> None:
    manifest = {
        "project": "SIP CRM",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backup_dir": backup_dir.name,
        "local_root": str(ROOT),
        **meta,
    }
    (backup_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "SIP CRM — полный снимок",
        f"Создан: {manifest['created_at']}",
        f"Папка: {backup_dir.name}",
        "",
        "Содержимое:",
        "  code/project.tar.gz     — исходники" + (" (+ .env)" if INCLUDE_SECRETS else " (без .env)"),
        "  docs/                   — readme, guides JSON, INDEX.md, env.example",
        "  git-info.json           — ветка, коммит, статус",
        "  server/postgres.sql     — дамп PostgreSQL с продакшена",
        "  server/postgres.sql.gz  — сжатый дамп",
    ]
    if INCLUDE_SECRETS:
        lines.append("  server/server.env       — .env с сервера")
    else:
        lines.append("  (server.env пропущен — BACKUP_INCLUDE_SECRETS=0)")
    lines.extend([
        "  server/docker-ps.txt    — состояние контейнеров",
        "",
        "Восстановление БД:",
        "  gunzip -c postgres.sql.gz | docker compose exec -T postgres psql -U USER DB",
    ])
    (backup_dir / "README.txt").write_text("\n".join(lines), encoding="utf-8")


def zip_backup(backup_dir: Path) -> Path:
    zip_path = backup_dir.parent / f"{backup_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in backup_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(backup_dir.parent).as_posix())
    return zip_path


def maybe_gpg_encrypt(zip_path: Path) -> Path | None:
    if not GPG_PASSPHRASE:
        return None
    out_path = zip_path.with_suffix(zip_path.suffix + ".gpg")
    proc = subprocess.run(
        [
            "gpg",
            "--batch",
            "--yes",
            "--passphrase",
            GPG_PASSPHRASE,
            "--symmetric",
            "--cipher-algo",
            "AES256",
            "-o",
            str(out_path),
            str(zip_path),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise SystemExit(f"GPG encryption failed: {proc.stderr[:300]}")
    zip_path.unlink(missing_ok=True)
    return out_path


def main() -> int:
    stamp = _ts()
    backup_dir = BACKUPS_ROOT / f"sipcrm-full-{stamp}"
    code_dir = backup_dir / "code"
    server_dir = backup_dir / "server"
    code_dir.mkdir(parents=True)
    server_dir.mkdir(parents=True)

    print(f"Backup directory: {backup_dir}")

    git_info = collect_git_info(backup_dir / "git-info.json")
    print(f"Git: {git_info.get('branch')} @ {git_info.get('commit_short')}")

    tar_path = code_dir / "project.tar.gz"
    file_count = archive_project_code(tar_path, include_secrets=INCLUDE_SECRETS)
    print(f"Archived {file_count} files -> {tar_path.name} ({tar_path.stat().st_size // 1024} KB)")

    local_env = ROOT / ".env"
    if INCLUDE_SECRETS and local_env.is_file():
        shutil.copy2(local_env, backup_dir / "local.env")
    elif local_env.is_file():
        print("Skipped local.env (BACKUP_INCLUDE_SECRETS=0)")

    docs_meta = export_documentation(backup_dir / "docs")
    print(f"Documentation: {docs_meta.get('files', [])}")

    server_meta = backup_server(server_dir, include_secrets=INCLUDE_SECRETS)
    print(f"Server backup: {json.dumps(server_meta.get('steps', []), ensure_ascii=False)}")

    meta = {
        "git": git_info,
        "files_archived": file_count,
        "code_archive_kb": tar_path.stat().st_size // 1024,
        "include_secrets": INCLUDE_SECRETS,
        "documentation": docs_meta,
        "server": server_meta,
    }
    write_manifest(backup_dir, meta)

    zip_path = zip_backup(backup_dir)
    encrypted = maybe_gpg_encrypt(zip_path)
    final_path = encrypted or zip_path
    final_mb = final_path.stat().st_size / (1024 * 1024)
    print(f"\nArchive: {final_path} ({final_mb:.2f} MB)")
    if encrypted:
        print("Plain ZIP removed after GPG encryption.")
    print("Backup completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
