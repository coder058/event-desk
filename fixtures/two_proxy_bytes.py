"""Isolated real-proxy reproduction; deployed executables and receiver, no owner keys."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--runtime-dir", required=True, type=Path,
                    help="Private folder containing hashed deployed executables, libraries and source ZIP")
ROOT = parser.parse_args().runtime_dir.resolve()
SOURCE = ROOT / "deployed-source"
# SOURCE: exact deployed revision inspected for this incident; require its Git blobs, not a filename claim.
SOURCE_REVISION = "cee53c02fded1e65976b42936cf50fcef69422b0"
git = ["git", "-C", str(Path(__file__).resolve().parents[1])]
expected_names = set(subprocess.check_output(git + ["ls-tree", "-r", "--name-only", SOURCE_REVISION, "src"])
                     .decode().splitlines())
with zipfile.ZipFile(ROOT / "deployed-source.zip") as archive:
    assert {item.filename for item in archive.infolist() if not item.is_dir()} == expected_names
    for member in archive.namelist():
        destination = (SOURCE / member).resolve()
        if not destination.is_relative_to(SOURCE.resolve()):
            raise RuntimeError("Archive escaped fixture directory")
        if member in expected_names:
            assert archive.read(member) == subprocess.check_output(git + ["show", SOURCE_REVISION + ":" + member])
    archive.extractall(SOURCE)
sys.path.insert(0, str(SOURCE / "src"))

# SOURCE: import the archived deployed receiver after inserting its isolated source path.
import httpx  # noqa: E402
import uvicorn  # noqa: E402

from eventdesk.api import create_app  # noqa: E402
from eventdesk.config import Settings, Submission  # noqa: E402
from eventdesk.store import Store  # noqa: E402

# SOURCE: existing public signing test vector from fixtures/tls_mux.py, never an owner key.
SECRET = "whsec_dGVzdC1zZWNyZXQtMzItYnl0ZXMtZm9yLXRlc3R2ZWN0"
# GUESS: unused private loopback fixture ports, checked before launch. # UNCALIBRATED GUESS
APP_PORT, HTTP_PORT, MUX_PORT, TLS_PORT = 19000, 19080, 19081, 19443
# GUESS: bounded fixture startup budget, not a measured service guarantee. # UNCALIBRATED GUESS
STARTUP_SECONDS = 60


def main() -> None:
    for port in (APP_PORT, HTTP_PORT, MUX_PORT, TLS_PORT):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    for executable in (ROOT / "caddy", ROOT / "haproxy", ROOT / "lib/ld-musl-x86_64.so.1"):
        executable.chmod(executable.stat().st_mode | 0o111)  # SOURCE: Unix executable permission bits.
    manifest = json.loads((ROOT / "binary-manifest.json").read_text())
    for item in manifest:
        local = ROOT / ("lib/" + Path(item["path"]).name if item["path"].startswith(("/lib/", "/usr/lib/")) else Path(item["path"]).name)
        assert hashlib.sha256(local.read_bytes()).hexdigest() == item["sha256"]

    database = ROOT / ("fixture-" + str(time.time_ns()) + ".sqlite")
    store = Store("sqlite:///" + str(database))
    store.initialize_fixture()
    settings = Settings("sqlite:///" + str(database), ROOT / "unused-model.joblib",
                        {"s1": Submission("s1", "fixture-only", SECRET)}, True, frozenset())
    app = create_app(settings, store)
    captures = []

    async def capture(scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await app(scope, receive, send)
        chunks = []
        status = None

        async def read():
            message = await receive()
            if message["type"] == "http.request":
                chunks.append(message.get("body", b""))
            return message

        async def write(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await app(scope, read, write)
        captures.append({"raw": b"".join(chunks), "headers": {k: v for k, v in scope["headers"]
                          if k.startswith(b"webhook-")}, "status": status})

    config = (ROOT / "haproxy-original.cfg").read_text()
    config = config.replace("bind :80", f"bind 127.0.0.1:{MUX_PORT}")
    config = config.replace("server caddy caddy:443", f"server caddy 127.0.0.1:{TLS_PORT}")
    config = config.replace("server caddy caddy:8080", f"server caddy 127.0.0.1:{HTTP_PORT}")
    (ROOT / "haproxy.fixture.cfg").write_text(config)
    caddy_config = f"""{{
    admin off
    http_port {HTTP_PORT}
    local_certs
    skip_install_trust
}}
localhost:{TLS_PORT} {{
    bind 127.0.0.1
    reverse_proxy 127.0.0.1:{APP_PORT}
    header {{
        X-Content-Type-Options nosniff
        Referrer-Policy no-referrer
        -Server
    }}
}}
http://localhost:{HTTP_PORT} {{
    bind 127.0.0.1
    redir https://localhost:{MUX_PORT}{{uri}} 308
}}
"""
    (ROOT / "Caddyfile.fixture").write_text(caddy_config)
    env = dict(os.environ, XDG_DATA_HOME=str(ROOT / "caddy-data"), XDG_CONFIG_HOME=str(ROOT / "caddy-config"))
    # SOURCE: explicitly ignore proxy environment variables for the local-only comparison.
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(name, None)
    loader = [str(ROOT / "lib/ld-musl-x86_64.so.1"), "--library-path", str(ROOT / "lib"), str(ROOT / "haproxy")]
    subprocess.run(loader + ["-c", "-f", str(ROOT / "haproxy.fixture.cfg")], check=True, capture_output=True, env=env)
    server = uvicorn.Server(uvicorn.Config(capture, host="127.0.0.1", port=APP_PORT,
                                         access_log=False, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    processes = []
    logs = []
    thread.start()
    try:
        for name, command in (("caddy", [str(ROOT / "caddy"), "run", "--config", str(ROOT / "Caddyfile.fixture"), "--adapter", "caddyfile"]),
                              ("haproxy", loader + ["-db", "-f", str(ROOT / "haproxy.fixture.cfg")])):
            stream = (ROOT / (name + ".log")).open("wb")
            logs.append(stream)
            processes.append(subprocess.Popen(command, stdout=stream, stderr=stream, cwd=ROOT, env=env))
        deadline = time.monotonic() + STARTUP_SECONDS
        certificate = ROOT / "caddy-data/caddy/pki/authorities/local/root.crt"
        while not certificate.exists() or not server.started:
            if any(p.poll() is not None for p in processes) or time.monotonic() > deadline:
                raise RuntimeError("Fixture failed startup; private logs retained")
            time.sleep(0.1)  # GUESS: short local readiness poll, not service latency. # UNCALIBRATED GUESS
        context = ssl.create_default_context(cafile=str(certificate))
        origins = [f"https://localhost:{MUX_PORT}", f"https://localhost:{TLS_PORT}"]
        with httpx.Client(verify=context, trust_env=False, follow_redirects=False, timeout=5) as client:
            # GUESS: five-second local request bound; not measured market latency. # UNCALIBRATED GUESS
            for origin in origins:
                while True:
                    try:
                        response = client.get(origin + "/healthz")
                        assert response.status_code == 200  # SOURCE: existing healthy receiver response.
                        assert response.json()["fixture_mode"] is True
                        break
                    except httpx.HTTPError:
                        if time.monotonic() > deadline:
                            raise
                        time.sleep(0.1)
            delivery = "fixture-two-proxy-" + str(time.time_ns())
            # PLACEHOLDER: fictional event; Unicode, whitespace and escapes exercise byte transport only.
            body = json.dumps({"id": delivery, "event_id": delivery, "event_type": "EARNINGS_RELEASE",
                "knowledge_cutoff": "2026-01-01T00:00:00Z", "metadata": "naïve — 🚀\nexact whitespace",
                "focal_assets": [{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}]},
                ensure_ascii=False, indent=2).encode()
            timestamp = str(int(time.time()))
            key = base64.urlsafe_b64decode(SECRET.removeprefix("whsec_"))
            signature = base64.b64encode(hmac.new(key, delivery.encode() + b"." + timestamp.encode() + b"." + body,
                                                  hashlib.sha256).digest()).decode()
            headers = {"Webhook-Id": delivery, "Webhook-Timestamp": timestamp,
                       "Webhook-Signature": "v1," + signature, "Content-Type": "application/json"}
            expected = {k.lower().encode(): v.encode() for k, v in headers.items() if k.lower().startswith("webhook-")}
            statuses = [client.post(origin + "/competition/webhook", content=body, headers=headers).status_code for origin in origins]
            assert statuses == [200, 200]  # SOURCE: accepted original and deduplicated retry.
            assert len(captures) == len(origins)
            assert all(item["raw"] == body and item["headers"] == expected for item in captures)
            assert store.health()["states"] == {"pending": 1}  # SOURCE: one durable receipt, no worker/send.
            invalid = [client.post(origin + "/competition/webhook", content=body + b" ", headers=headers).status_code for origin in origins]
            assert invalid == [401, 401]  # SOURCE: unchanged signature over altered bytes must fail.
            from sqlalchemy.orm import Session
            with Session(store.engine) as session:
                from sqlalchemy import func, select

                from eventdesk.store import Delivery, Job
                delivery_count = session.scalar(select(func.count()).select_from(Delivery))
                job_count = session.scalar(select(func.count()).select_from(Job))
            assert delivery_count == job_count == 1
            result = {"checked_at": datetime.now(UTC).isoformat(), "kind": "isolated_real_two_proxy_fixture",
                "source_commit": SOURCE_REVISION, "binary_manifest": manifest,
                "archived_source_files_matched_git_blobs": len(expected_names),
                "receiver_api_sha256": hashlib.sha256((SOURCE / "src/eventdesk/api.py").read_bytes()).hexdigest(),
                "fixture_runtime_python": f"{sys.version_info.major}.{sys.version_info.minor}",
                "origins": origins, "signed_ack_statuses": statuses, "altered_body_statuses": invalid,
                "raw_body_sha256": hashlib.sha256(body).hexdigest(), "raw_body_exact_match_both_paths": True,
                "signing_header_exact_match_both_paths": True, "signing_header_names": sorted(k.decode() for k in expected),
                "durable_deliveries": delivery_count, "durable_jobs": job_count, "job_state": "pending",
                "ca_hostname_validation": True, "production_mutations": False, "official_requests": 0,
                "limits": "Local WSL loopback with copied deployed proxy executables and receiver source; local CA/ports/DNS and disposable SQLite differ from production. No public cloud ingress, failed portal payload, official delivery, PostgreSQL concurrency, worker, score or latency claim."}
            (ROOT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result))
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)  # GUESS: owned-child cleanup grace. # UNCALIBRATED GUESS
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        server.should_exit = True
        thread.join(timeout=5)  # GUESS: local fixture shutdown grace. # UNCALIBRATED GUESS
        assert not thread.is_alive(), "Owned fixture server did not stop"
        for stream in logs:
            stream.close()


if __name__ == "__main__":
    main()
    # SOURCE: successful cleanup must release every loopback port owned by this fixture.
    for port in (APP_PORT, HTTP_PORT, MUX_PORT, TLS_PORT):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    result_path = ROOT / "result.json"
    result = json.loads(result_path.read_text())
    result["fixture_listener_ports_released"] = True
    result["fixture_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result_path.write_text(json.dumps(result, indent=2) + "\n")
