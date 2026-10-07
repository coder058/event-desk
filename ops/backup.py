"""Root-only encrypted PostgreSQL/model/config backup to the existing Frankfurt VPS."""
# SOURCE: this host helper runs on Dublin's Python 3.10; application containers use Python 3.12.
# ruff: noqa: UP017
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        # GUESS: same 64 KiB buffer as the receiver; do not load growing database dumps in RAM.
        while chunk := stream.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_regular_file(source: Path, destination: Path) -> None:
    """Hash/archive only this completed private copy; reject mutation or a linked source."""
    if source.is_symlink():
        raise ValueError("Backup source cannot be a symlink")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # SOURCE: O_NOFOLLOW rejects a raced symlink on the actual Linux backup host;
    # zero is the neutral fallback for platforms used by the synthetic unit tests.
    descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        with os.fdopen(descriptor, "rb") as original:
            before = os.fstat(original.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("Backup requires a regular source file")
            with destination.open("xb") as snapshot:
                shutil.copyfileobj(original, snapshot)
                snapshot.flush()
                os.fsync(snapshot.fileno())
            after, current = os.fstat(original.fileno()), source.stat(follow_symlinks=False)
            def identity(state):
                return state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns
            if identity(before) != identity(after) or identity(before) != identity(current):
                raise ValueError("Backup source changed during capture")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    os.chmod(destination, 0o600)


def atomic_json(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".backup-state-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def run() -> dict[str, object]:
    if os.geteuid() != 0:
        raise RuntimeError("Backup requires root for existing secret-file access")
    os.umask(0o077)
    config = json.loads(Path("/etc/eventdesk/backup.json").read_text())
    backup_root = Path("/var/lib/eventdesk/backups")
    backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = "eventdesk-" + stamp + ".tar.gz.age"
    encrypted = backup_root / name
    if encrypted.exists():
        raise FileExistsError("Backup filename already exists")
    with tempfile.TemporaryDirectory(prefix="staging-", dir=backup_root) as temporary:
        stage = Path(temporary)
        dump = stage / "database.dump"
        with dump.open("wb") as output:
            subprocess.run(["docker", "exec", "eventdesk-db-1", "pg_dump", "-U", "eventdesk",
                            "-d", "eventdesk", "-Fc"], stdout=output, stderr=subprocess.PIPE, check=True)
        model = Path("/var/lib/eventdesk/models/local-model.joblib")
        source = Path("/srv/eventdesk")
        files = {"database.dump": dump, "local-model.joblib": model,
            "secrets/env": Path("/etc/eventdesk/env"),
            "secrets/database.env": Path("/etc/eventdesk/database.env"),
            "secrets/runtime.env": Path("/etc/eventdesk/runtime.env"),
            "source/compose.production.yaml": source / "compose.production.yaml",
            "source/MODEL_CARD.md": source / "MODEL_CARD.md"}
        for optional in ("competition-config.json", "PREREGISTRATION.md", "deployment.json"):
            if (source / optional).is_file():
                files["source/" + optional] = source / optional
        # SOURCE: both files are required to reconstruct the deployed TLS routing.
        for ingress_name in ("Caddyfile", "haproxy.cfg"):
            files["source/ops/"+ingress_name] = source/"ops"/ingress_name
        # SOURCE: only this project's known research artifacts; no broad host/home scan.
        research = Path("/var/lib/eventdesk/research")
        for research_name in ("quota-source-sealed.json", "archive/2026Q2.jsonl.gz", "archive/2026Q3.jsonl.gz",
                     "evidence/llm-groq-2026Q2.jsonl", "evidence/llm-groq-2026Q3.jsonl",
                     "evidence/llm-gemini-2026Q2.jsonl", "evidence/llm-gemini-2026Q3.jsonl"):
            path = research/research_name
            if path.exists():
                files["research/"+research_name] = path
        # Snapshot sources before computing hashes. A later append/deploy cannot produce
        # an archive whose bytes disagree with the manifest that described live files.
        snapshots = {}
        for archive_name, path in files.items():
            target = stage/"snapshot"/archive_name
            snapshot_regular_file(path, target)
            snapshots[archive_name] = target
        files = snapshots
        manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "database_format": "pg_dump_custom",
            "files": {name: {"sha256": file_hash(path),
                              "bytes": path.stat().st_size} for name, path in files.items()}}
        manifest_path = stage / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        files["manifest.json"] = manifest_path
        archive = stage / "backup.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for archive_name, path in files.items():
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Backup source must be a regular trusted file")
                tar.add(path, arcname=archive_name, recursive=False)
        subprocess.run(["age", "-r", config["recipient"], "-o", str(encrypted), str(archive)],
                       capture_output=True, check=True)
    # The only bytes transmitted by the restricted project key are already age-encrypted.
    ssh = ["ssh", "-T", "-i", "/etc/eventdesk/backup_ed25519", "-oBatchMode=yes",
        "-oIdentitiesOnly=yes", "-oStrictHostKeyChecking=yes",
        "-oUserKnownHostsFile=/etc/eventdesk/backup_known_hosts",
        # GUESS: fail connection after fifteen seconds; never wait for an interactive auth prompt.
        "-oConnectTimeout=15", config["destination"], "receive " + name]
    with encrypted.open("rb") as stream:
        result = subprocess.run(ssh, stdin=stream, capture_output=True, check=True)
    receipt = json.loads(result.stdout)
    digest = file_hash(encrypted)
    if receipt.get("sha256") != digest or receipt.get("bytes") != encrypted.stat().st_size:
        raise RuntimeError("Remote ciphertext receipt mismatch")
    report: dict[str, object] = {"created_at": manifest["created_at"], "file": name,
        "encrypted_bytes": encrypted.stat().st_size, "ciphertext_sha256": digest,
        "model_sha256": manifest["files"]["local-model.joblib"]["sha256"],
        "remote_receipt_verified": True, "restore_verified": False}
    atomic_json(backup_root/"latest.json", report)
    return report


if __name__ == "__main__":
    try:
        print(json.dumps(run()))
    except Exception as exc:
        print(json.dumps({"backup_failed": True, "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
