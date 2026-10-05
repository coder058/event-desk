import hashlib
import json
from pathlib import Path

import pytest

from eventdesk.freeze import verify_freeze
from eventdesk.model import LocalModel


def test_freeze_blocks_unrecorded_artifact_blend_and_provider_changes(model, tmp_path):
    config = json.loads(Path("competition-config.json").read_text())
    # PLACEHOLDER: replace only the artifact hash with the synthetic test artifact; no model-quality claim.
    config["model_sha256"] = model.sha256
    path = tmp_path / "fixture-declaration.json"
    path.write_text(json.dumps(config))
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert verify_freeze(path, model, hybrid_enabled=False, provider_models={}) == expected
    with pytest.raises(ValueError, match="blend"):
        verify_freeze(path, model, hybrid_enabled=True)
    with pytest.raises(ValueError, match="provider"):
        verify_freeze(path, model, hybrid_enabled=False, provider_models={"groq": "undocumented"})
    config["feature_code_sha256"] = "0" * 64
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="feature"):
        verify_freeze(path, model, hybrid_enabled=False)


def test_declared_model_hash_is_checked_before_deserializing_joblib(model, tmp_path, monkeypatch):
    import eventdesk.model
    called = []
    monkeypatch.setattr(eventdesk.model.joblib, "load", lambda _: called.append(True))
    path = tmp_path / "not-a-trusted-model.joblib"
    path.write_bytes(b"fixture untrusted data")
    with pytest.raises(ValueError, match="hash"):
        LocalModel(path, expected_sha256=model.sha256)
    assert called == []
