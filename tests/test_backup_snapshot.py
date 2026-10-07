import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

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


def test_complete_backup_sends_the_ciphertext_filename_and_preserves_research(tmp_path, monkeypatch):
    module = backup_module()
    # PLACEHOLDER: synthetic root/project files and mocked dump/encryption/SSH, no actual secret or host.
    def host_path(value):
        return tmp_path/str(value).lstrip("/")
    root = host_path("/var/lib/eventdesk")
    sources = {
        "/etc/eventdesk/backup.json": json.dumps({"recipient": "fixture", "destination": "fixture"}),
        "/etc/eventdesk/env": "fixture-only", "/etc/eventdesk/database.env": "fixture-only",
        "/etc/eventdesk/runtime.env": "fixture-only", "/var/lib/eventdesk/models/local-model.joblib": "synthetic model",
        "/srv/eventdesk/compose.production.yaml": "synthetic compose", "/srv/eventdesk/MODEL_CARD.md": "synthetic card",
        "/srv/eventdesk/ops/Caddyfile": "synthetic caddy", "/srv/eventdesk/ops/haproxy.cfg": "synthetic proxy",
        "/var/lib/eventdesk/research/evidence/llm-groq-2026Q3.jsonl": '{"synthetic":true}\n'}
    for name, raw in sources.items():
        path = host_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw)
    sent = []
    def command(args, **kwargs):
        if args[0] == "docker":
            kwargs["stdout"].write(b"synthetic database dump")
        elif args[0] == "age":
            Path(args[args.index("-o")+1]).write_bytes(b"synthetic encrypted bytes")
        elif args[0] == "ssh":
            assert re.fullmatch(r"receive eventdesk-\d{8}T\d{6}Z\.tar\.gz\.age", args[-1])
            raw = kwargs["stdin"].read()
            sent.append(args[-1].split(" ")[1])
            return SimpleNamespace(stdout=json.dumps({"bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest()}).encode())
        else:
            raise AssertionError("Unexpected external command in fixture")
        return SimpleNamespace(stdout=b"")
    monkeypatch.setattr(module, "Path", host_path)
    monkeypatch.setattr(module.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(module.subprocess, "run", command)
    result = module.run()
    assert result["file"] == sent[0]
    assert result["remote_receipt_verified"]
    assert json.loads((root/"backups/latest.json").read_text())["file"] == sent[0]
    assert host_path("/var/lib/eventdesk/research/evidence/llm-groq-2026Q3.jsonl").read_text() == '{"synthetic":true}\n'
