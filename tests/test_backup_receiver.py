import hashlib
import importlib.util
import io
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("backup_receiver", Path("ops/backup_receiver.py"))
assert spec is not None and spec.loader is not None
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


def test_restricted_backup_receiver_is_bounded_immutable_and_cannot_escape(tmp_path, monkeypatch):
    name = "eventdesk-20261005T000000Z.tar.gz.age"
    # PLACEHOLDER: fixture ciphertext bytes, not an encrypted production backup.
    payload = b"age-fixture-ciphertext"
    result = receiver.receive("receive " + name, io.BytesIO(payload), tmp_path)
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()
    assert (tmp_path / name).read_bytes() == payload
    with pytest.raises(FileExistsError):
        receiver.receive("receive " + name, io.BytesIO(b"changed"), tmp_path)
    assert (tmp_path / name).read_bytes() == payload
    for command in ("receive ../../identity.txt", "cat /etc/passwd", "receive x; echo evil", ""):
        with pytest.raises(ValueError):
            receiver.receive(command, io.BytesIO(payload), tmp_path)
    monkeypatch.setattr(receiver, "MAX_BYTES", len(payload) - 1)
    with pytest.raises(ValueError):
        receiver.receive("receive eventdesk-20261005T000001Z.tar.gz.age", io.BytesIO(payload), tmp_path)
    assert not list(tmp_path.glob(".incoming-*"))
