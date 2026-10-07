import importlib.util
from pathlib import Path

import pytest


def backup_module():
    spec = importlib.util.spec_from_file_location("eventdesk_backup_helper", Path("ops/backup.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_manifest_describes_frozen_bytes_not_a_later_append(tmp_path):
    module = backup_module()
    original, frozen = tmp_path/"source.jsonl", tmp_path/"private/frozen.jsonl"
    original.write_bytes(b'{"synthetic":true}\n')
    module.snapshot_regular_file(original, frozen)
    digest = module.file_hash(frozen)
    original.write_bytes(b'{"synthetic":true}\n{"later":true}\n')
    assert frozen.read_bytes() == b'{"synthetic":true}\n'
    assert module.file_hash(frozen) == digest != module.file_hash(original)


def test_mutation_while_snapshotting_is_rejected_not_silently_backed_up(tmp_path, monkeypatch):
    module = backup_module()
    original, frozen = tmp_path/"source.jsonl", tmp_path/"private/frozen.jsonl"
    original.write_bytes(b'{"synthetic":true}\n')
    copy = module.shutil.copyfileobj
    def mutate(reader, writer):
        copy(reader, writer)
        original.write_bytes(b'{"changed":true}\n')
    monkeypatch.setattr(module.shutil, "copyfileobj", mutate)
    with pytest.raises(ValueError, match="changed"):
        module.snapshot_regular_file(original, frozen)
    assert not frozen.exists()


def test_atomic_backup_state_can_be_replaced_without_reusing_partial_bytes(tmp_path):
    module = backup_module()
    target = tmp_path/"latest.json"
    module.atomic_json(target, {"synthetic": True})
    module.atomic_json(target, {"synthetic": False})
    assert target.read_text() == '{"synthetic": false}\n'
    assert list(tmp_path.iterdir()) == [target]
