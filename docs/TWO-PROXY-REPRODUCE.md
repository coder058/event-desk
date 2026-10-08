# Reproduce signed bytes through both proxy routes

Scope: the same synthetic signed request goes through HAProxy TCP passthrough →
Caddy → the archived receiver, then directly through Caddy → that receiver.
The application wrapper compares the entire body and all signing-header values.
Both ACKs must succeed, one SQLite delivery/job must remain, and altered bytes
under the original signature must be rejected through both paths.

This is a diagnostic fixture, not a product feature or a production replay.
No owner signing secret, model, worker, provider call or official POST is used.
[Actual result and executable hashes](../reports/two-proxy-bytes-20261008.json),
[runnable fixture](../fixtures/two_proxy_bytes.py).

## Actual run

The Windows Docker CLI was unavailable. WSL Ubuntu had Python/pip but neither
Docker nor these proxies. Public executable/library bytes were read from the
existing Event Desk containers through SSH, then compared to remote SHA-256.
No container, service, cloud rule or file was changed on either VPS.

The local environment used Python 3.14 and the dependencies pinned in the report;
production's Dockerfile uses Python 3.12. Its receiver source was extracted from
cee53c02fded1e65976b42936cf50fcef69422b0. All archived source files and installed
API-package files matched that revision. The local ports, hostname, internal CA
and SQLite differ from production. CA/hostname validation remained enabled;
Caddy's trust-store installation was disabled and its data directory was private.

The first private helper reached the transport assertions but failed its final
row-count check because it called a nonexistent Store.transaction method. That
was a fixture error, not a production receiver error. It was corrected to use
SQLAlchemy Session; the corrected private run and the repository runner both
passed. All owned proxy/API processes stopped and listener ports were released.

## Independent replay without owner credentials

Use a Linux environment with Git, Python, pip and Docker available. Docker here is
only a way to extract public executable bytes from the exact recorded images;
the actual comparison runs native processes. Alternatively use already copied
and hash-verified executable/library files, as the actual WSL run did.
These commands are instructions, not a claim that this independent image-download
path was executed on this host.

From this repository's root:

```sh
runtime_dir="$PWD/private/two-proxy-replay"
mkdir -p "$runtime_dir"
git archive --format=zip --output="$runtime_dir/deployed-source.zip" cee53c0 src
git show cee53c0:ops/haproxy.cfg > "$runtime_dir/haproxy-original.cfg"
```

Populate the private runtime directory with the executable names expected by
the fixture. This keyless helper refuses bytes that differ from the recorded
hashes. Its temporary extraction containers have no network, ports or volumes:

```sh
python3 - "$runtime_dir" <<'PY'
from pathlib import Path
import hashlib, json, subprocess, sys

root = Path(sys.argv[1])
proof = json.loads(Path('reports/two-proxy-bytes-20261008.json').read_text())
identities = proof['deployed_image_identities']
manifest = []
for item in proof['binary_manifest']:
    image = identities[item['container']]['repo_digests'][0]
    raw = subprocess.check_output([
        'docker', 'run', '--rm', '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--entrypoint', 'cat', image, item['path']])
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
    name = Path(item['path']).name
    target = root / ('lib/' + name if '/lib/' in item['path'] else name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    manifest.append({**item, 'copy_source': 'recorded official image digest'})
(root / 'binary-manifest.json').write_text(json.dumps(manifest, indent=2))
(root / 'fixture-requirements.txt').write_text(
    '\n'.join(proof['fixture_requirements']) + '\n')
PY
```

Install only into the private environment, then run the actual comparison:

```sh
python3 -m venv --without-pip "$runtime_dir/venv"
python3 -m pip --python "$runtime_dir/venv/bin/python3" install \
  --requirement "$runtime_dir/fixture-requirements.txt"
"$runtime_dir/venv/bin/python3" fixtures/two_proxy_bytes.py \
  --runtime-dir "$runtime_dir"
```

The runner refuses occupied loopback ports before starting. It writes result.json
only in that directory; the final file also records its script hash and cleanup
check. The source archive is compared with the exact Git blobs before importing
the receiver. A deliberately modified API archive was rejected before extraction
or database creation in the recorded negative control.
Keep executables, libraries, CA, logs and database ignored/private. Review
the result rather than publishing arbitrary runtime contents.

## Evidence boundary

The recorded run establishes this local transport comparison, with the original
body, signing-header values, real deployed proxy executables and archived receiver.
It does not establish the cloud firewall path, the failed portal payloads or their
timestamp, production PostgreSQL concurrency, a signed official TEST through 443,
latency, scoring or the incident's root cause. It also does not replace the complete
Docker/Compose reproduction gate. [Original limits](REPRODUCE.md).
