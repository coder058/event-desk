"""Read/hash-check an isolated decrypted project archive without extracting files.

This module is also transferred as source to the existing Frankfurt verifier;
it has only Python standard-library dependencies and supports host Python 3.10.
"""
from __future__ import annotations

import hashlib
import json
import re
import tarfile
from pathlib import Path


def verify_plain_archive(path: Path, expected_model: str) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{64}", expected_model) is None:
        raise ValueError("Expected model identity is invalid")
    with tarfile.open(path, "r:gz") as tar:
        members = tar.getmembers()
        if any(not member.isfile() or member.name.startswith("/") or ".." in Path(member.name).parts
               for member in members) or len({member.name for member in members}) != len(members):
            raise ValueError("Unsafe or duplicate archive member")
        stream = tar.extractfile("manifest.json")
        if stream is None:
            raise ValueError("Backup manifest unavailable")
        with stream:
            manifest = json.load(stream)
        if {member.name for member in members} != set(manifest["files"]) | {"manifest.json"}:
            raise ValueError("Archive and manifest membership disagree")
        raw_objects = set()
        for name, metadata in manifest["files"].items():
            digest, size = hashlib.sha256(), 0
            stream = tar.extractfile(name)
            if stream is None:
                raise ValueError("Manifest member unavailable")
            with stream:
                # GUESS: streaming buffer, not a market parameter or memory-capacity benchmark. # UNCALIBRATED GUESS
                while chunk := stream.read(64 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
            if digest.hexdigest() != metadata["sha256"] or size != metadata["bytes"]:
                raise ValueError("Backup member hash or byte count mismatch")
            if name.startswith("evidence/objects/"):
                matched = re.fullmatch(r"evidence/objects/([0-9a-f]{2})/([0-9a-f]{64})", name)
                if (matched is None or not matched.group(2).startswith(matched.group(1))
                        or matched.group(2) != digest.hexdigest()):
                    raise ValueError("Archived source object identity mismatch")
                raw_objects.add(matched.group(2))
        if manifest["files"]["local-model.joblib"]["sha256"] != expected_model:
            raise ValueError("Archived model identity mismatch")
    return {"archive_files_verified": len(manifest["files"]), "model_sha256": expected_model,
            "raw_objects_sha256": sorted(raw_objects)}
