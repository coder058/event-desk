"""External verified-TLS probe, then retain its dated result for the host monitor."""
from __future__ import annotations

import json
import shlex
import socket
import ssl
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bootstrap import SSH

# SOURCE: reviewed production shared TLS listener; this is never an arbitrary caller-provided URL.
ORIGIN = "https://52.17.192.36.sslip.io:80"
# GUESS: external probe time budget, not a service-latency claim. # UNCALIBRATED GUESS
TIMEOUT = 8

REMOTE = '''
import json,os,sys,tempfile
from pathlib import Path
record=json.load(sys.stdin)
if record.get('origin')!='https://52.17.192.36.sslip.io:80': raise ValueError('Unexpected proof origin')
directory=Path('/var/lib/eventdesk/monitor');directory.mkdir(mode=0o700,parents=True,exist_ok=True)
descriptor,temporary=tempfile.mkstemp(prefix='.external-https-',dir=directory)
try:
 with os.fdopen(descriptor,'w') as stream:
  json.dump(record,stream,allow_nan=False);stream.flush();os.fsync(stream.fileno())
 os.chmod(temporary,0o600);os.replace(temporary,directory/'external-https.json')
finally:
 Path(temporary).unlink(missing_ok=True)
print(json.dumps({'dated_external_proof_retained':True,'verified':record['verified']}))
'''


def main() -> None:
    record: dict = {"origin": ORIGIN, "checked_at": datetime.now(UTC).isoformat(), "verified": False,
        "limits": "One external network observation; not portal delivery, continuous uptime or score eligibility"}
    try:
        # Standard CA/hostname validation remains enabled; environment proxies cannot change this probe.
        with httpx.Client(timeout=TIMEOUT, trust_env=False) as http:
            health = http.get(ORIGIN+"/healthz")
            health.raise_for_status()
            body = health.json()
            if (body.get("database") != "reachable" or body.get("fixture_mode") is not False
                    or body.get("worker", {}).get("state") != "recent_heartbeat"):
                raise ValueError("Production receiver/worker health not verified")
            page = http.get(ORIGIN+"/")
            page.raise_for_status()
            if "Event Desk" not in page.text:
                raise ValueError("Expected product page not found")
            unsigned = http.post(ORIGIN+"/competition/webhook", content=b"{}")
            redirect = http.get("http://52.17.192.36.sslip.io/healthz", follow_redirects=False)
            if (unsigned.status_code != 401 or redirect.status_code != 308
                    or redirect.headers.get("location") != ORIGIN+"/healthz"):
                raise ValueError("Signature gate/plaintext redirect not verified")
        context = ssl.create_default_context()
        # SOURCE: socket destination is the declared port; SNI/hostname verification is the public name.
        with socket.create_connection(("52.17.192.36.sslip.io", 80), timeout=TIMEOUT) as connection:
            with context.wrap_socket(connection, server_hostname="52.17.192.36.sslip.io") as tls:
                certificate = tls.getpeercert()
                assert certificate is not None
                record.update({"tls_version": tls.version(), "certificate_not_after": certificate["notAfter"]})
        record.update({"verified": True, "health_status": health.status_code,
            "unsigned_webhook_status": unsigned.status_code, "plaintext_redirect_status": redirect.status_code,
            "worker_state": body["worker"]["state"], "configuration_hash": body["worker"]["details"]["configuration_hash"]})
    except (httpx.HTTPError, OSError, ValueError, KeyError) as error:
        record["error_type"] = type(error).__name__  # Never retain request/exception text.
    Path("reports/external-https.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    result = subprocess.run(SSH+["sudo python3 -c "+shlex.quote(REMOTE)],
        input=json.dumps(record).encode(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Dated external probe could not be retained; output withheld")
    print(json.dumps(record))
    if not record["verified"]:
        raise RuntimeError("External HTTPS remains unverified")


if __name__ == "__main__":
    main()
