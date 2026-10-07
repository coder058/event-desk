import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest


def verifier():
    spec = importlib.util.spec_from_file_location("backup_archive_fixture", Path("ops/backup_archive.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_plain_archive


def archive(tmp_path, *, damage=None):
    # PLACEHOLDER: plaintext synthetic backup/model/source, not owner data or actual encryption.
    model, raw = b"synthetic model", b"synthetic retained SEC bytes"
    digest = hashlib.sha256(raw).hexdigest()
    name = "evidence/objects/"+digest[:2]+"/"+digest
    if damage == "identity":
        name = "evidence/objects/"+"00"+"/"+"0"*64
    files = {"local-model.joblib": model, name: raw, "database.dump": b"synthetic dump"}
    manifest = {"files": {key: {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                          for key, value in files.items()}}
    if damage == "bytes":
        files[name] = b"changed source bytes"
    files["manifest.json"] = json.dumps(manifest).encode()
    path = tmp_path/"fixture.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for key, value in files.items():
            member = tarfile.TarInfo(key)
            member.size = len(value)
            tar.addfile(member, io.BytesIO(value))
        if damage == "duplicate":
            member = tarfile.TarInfo("database.dump")
            tar.addfile(member, io.BytesIO())
        elif damage == "link":
            member = tarfile.TarInfo("unsafe")
            member.type, member.linkname = tarfile.SYMTYPE, "/outside"
            tar.addfile(member)
    return path, hashlib.sha256(model).hexdigest(), digest


def test_decrypted_archive_verifies_source_object_identity_and_model_without_extraction(tmp_path):
    path, model, source = archive(tmp_path)
    proof = verifier()(path, model)
    assert proof["model_sha256"] == model and proof["raw_objects_sha256"] == [source]
    assert proof["archive_files_verified"] == 3
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("damage", ["identity", "bytes", "duplicate", "link"])
def test_invalid_source_bytes_identity_or_tar_structure_cannot_be_verified(tmp_path, damage):
    path, model, _ = archive(tmp_path, damage=damage)
    with pytest.raises(ValueError):
        verifier()(path, model)
    assert list(tmp_path.iterdir()) == [path]
