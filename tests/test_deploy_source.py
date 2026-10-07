import importlib
import io
import subprocess
import tarfile

import pytest


def test_source_bundle_uses_committed_bytes_and_excludes_ignored_private_data(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend("ops")
    deploy = importlib.import_module("deploy")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], stderr=subprocess.DEVNULL)
    git("init")
    git("config", "user.name", "Fixture")
    git("config", "core.autocrlf", "true")  # SOURCE: reproduce the observed Windows archive transformation on any CI host.
    git("config", "user.email", "fixture@example.test")  # PLACEHOLDER: local fixture identity, never a deployed contact.
    (tmp_path/".gitignore").write_text("private/\n")
    (tmp_path/"source.txt").write_text("committed source\n")
    (tmp_path/"private").mkdir()
    (tmp_path/"private/fixture.env").write_text("fictional ignored data")
    git("add", ".gitignore", "source.txt")
    git("commit", "-m", "fixture source")
    raw, revision = deploy.source_bundle(tmp_path)
    assert revision == git("rev-parse", "HEAD").decode().strip()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        assert set(archive.getnames()) == {".gitignore", "source.txt"}
        assert archive.extractfile("source.txt").read() == git("show", "HEAD:source.txt")
    (tmp_path/"source.txt").write_text("unreviewed change")
    with pytest.raises(RuntimeError, match="Commit and verify"):
        deploy.source_bundle(tmp_path)
    git("restore", "source.txt")
    (tmp_path/"untracked.py").write_text("unreviewed code")
    with pytest.raises(RuntimeError, match="Commit and verify"):
        deploy.source_bundle(tmp_path)
    (tmp_path/"untracked.py").unlink()
    (tmp_path/".git/info/attributes").write_text("source.txt export-ignore\n")
    with pytest.raises(RuntimeError, match="omitted"):
        deploy.source_bundle(tmp_path)
    (tmp_path/".git/info/attributes").write_text("source.txt text eol=crlf\n")
    with pytest.raises(RuntimeError, match="differ"):
        deploy.source_bundle(tmp_path)
