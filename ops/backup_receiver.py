"""Restricted SSH receive-only endpoint: stores ciphertext, never extracts or runs it."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO

# GUESS: 2 GiB ciphertext ceiling prevents an unlimited upload; not a measured retention requirement.
MAX_BYTES = 2 * 1024 * 1024 * 1024
# GUESS: 64 KiB streaming buffer avoids retaining the backup in memory.
CHUNK_BYTES = 64 * 1024


def receive(command: str, stream: BinaryIO, directory: Path) -> dict[str, object]:
    match = re.fullmatch(r"receive (eventdesk-\d{8}T\d{6}Z\.tar\.gz\.age)", command)
    if match is None:
        raise ValueError("Only a named encrypted upload is allowed")
    name = match[1]
    fd, temporary_name = tempfile.mkstemp(prefix=".incoming-", dir=directory)
    temporary = Path(temporary_name)
    total = 0
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as target:
            while chunk := stream.read(CHUNK_BYTES):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("Upload exceeds ciphertext ceiling")
                target.write(chunk)
                digest.update(chunk)
            if total == 0:
                raise ValueError("Empty ciphertext rejected")
            target.flush()
            os.fsync(target.fileno())
        # SOURCE: hard-link creation refuses an existing filename atomically; no overwrite or extraction.
        os.link(temporary, directory / name)
        # SOURCE: directory fsync is available on the POSIX deployment, not Windows fixture hosts.
        if os.name == "posix":
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        return {"file": name, "bytes": total, "sha256": digest.hexdigest()}
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        result = receive(os.getenv("SSH_ORIGINAL_COMMAND", ""), sys.stdin.buffer,
                         Path("/home/ubuntu/eventdesk-backups"))
        print(json.dumps(result))
    except Exception as exc:
        # Contents and exception strings must never expose credentials or decrypted backup material.
        print(json.dumps({"error_type": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1) from None
