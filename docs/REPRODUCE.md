# Reproduce Event Desk

## Keyless fixture environment

Prerequisites: Git, Docker Engine/Desktop with a running daemon and the Docker
Compose v2 plugin. The image uses Python 3.12; the host does not need owner
credentials, a fitted production artifact or a local Python installation for Compose.
Run from the repository root. Keep production environment files out of this checkout.

```sh
git clone https://github.com/coder058/event-desk.git
cd event-desk
docker version
docker compose version
docker compose up --build
```

The last command stays in the foreground. After migrations and fixture training
complete, open `http://127.0.0.1:8000`. It should report fixture mode and a synthetic
model. This is an isolated local simulator, not an official competition submission.
The Compose file uses separate fixture database/model volumes and a loopback port.

For the existing signed receipt/worker smoke, use a second terminal in the same root:

```sh
python -m pip install -c constraints.txt '.[dev]'
python fixtures/smoke.py
```

That second terminal needs Python >=3.11; CI uses 3.12. The smoke verifies fixture
mode before posting a public signed fixture and waits for its simulated result.
The existing 400-event replay runs inside the fixture container:

```sh
docker compose exec api python fixtures/load_test.py
```

Stop the foreground process with Ctrl+C. `docker compose down` removes those
containers/network while retaining fixture volumes. Do not substitute
`compose.production.yaml`, copy owner environment files or run deployment scripts
as part of local reproduction.

## Python development checks

A Python virtual environment is recommended before installing developer dependencies.
Activate it using your platform's normal command, then from the repository root:

```sh
python -m pip install -c constraints.txt '.[dev]'
python -m ruff check src research ops tests migrations fixtures
python -m mypy --strict src/eventdesk
python -m pytest -q -s
python ops/secret_scan.py
```

The dependency installation command above comes from CI. Installation into a new
virtual environment was not repeated in the audit below; Python checks used the
existing interpreter/dependencies against the clean checkout.

## Actual clean-checkout audit: 8 October 2026 (Madrid)

A new local Git clone, without hardlinks or ignored files, was made from commit
`3056926201d690263df37b956992a8263689cab4`. It contains the proposed local documentation
as well as the unchanged production source. This was not a fresh GitHub download:
those documentation commits have not been pushed.

| Step attempted | Actual observation | Limit |
| --- | --- | --- |
| Fresh local clone | Clone completed at the specified commit | Existing Python dependencies reused |
| README command `docker compose up --build` | PowerShell: `docker` not recognized | Docker CLI unavailable in this shell; no fixture container started |
| Ruff, same scope as CI | All checks passed | No lint fixes needed |
| Strict mypy | Success: no issues found in 23 source files | Same configured source scope as CI |
| Full pytest suite, clean clone | 1 failed, 172 passed, 1 skipped; 198.97 s | Failure described below; not a green gate |
| Isolated failed test, both parameter cases | 2 passed, 9 deselected; 2.87 s | Isolated success does not erase the full-run failure |
| Full suite rerun, source worktree | 173 passed, 1 skipped; 161.08 s | No test or production code changed; Windows symlink case skipped |
| Second full clean-clone run | 1 failed, 172 passed, 1 skipped; 151.83 s | Same old 50 ms setup failure, retained below |
| Transport fixture corrected, both cases | 2 passed, 9 deselected; 3.30 s | Only test setup changed; production source unchanged |
| Full suite after fixture correction | 173 passed, 1 skipped; 144.16 s | Windows symlink case skipped; no production source change |

The failing case was
`test_submission_entire_attempt_bounded_and_unknown_result_reuses_outbox[True]`.
Its injected 50 ms deadline starts before the final prediction persistence; the
mock POST list remained empty and the assertion raised `IndexError`. Source reads
show the worker checks expiry after persistence and can legitimately avoid POST
when that budget is gone. The observed failure is consistent with that path, but
this run did not record enough timing to prove the exact cause. No deadline,
assertion or production code was relaxed. The isolated retry exercised both the
stalled-header and stalled-body variants successfully; a complete rerun is retained
separately rather than replacing the failed observation.

After the second clean-clone failure, the test fixture was corrected to persist
the immutable outbox before starting its 50 ms HTTP budget. Its name now says
`submission_transport_attempt`, matching that scope. Both stalled-header and
stalled-body assertions remain; the production worker and real deadline were not
changed. The isolated corrected test passed both cases. This does not establish
a measured production latency or resolve the independent official 4xx incident.

The previously deployed `cee53c0` passed Linux CI 37696439274, including Compose
smoke and concurrency checks. That is separate evidence, not a successful local
Compose run for this clean-checkout audit. The README now states Docker prerequisites
explicitly. Production code and services were not changed to work around this host.

## Scripts without literal references: review, not proven dead code

An AST import scan of all 23 non-vendored source modules found static Python
importers for every module except the package marker `eventdesk.__init__`. Tests,
research and operational scripts count as importers; this does not prove every
module is exercised by the live worker. The package marker is retained.

A static scan of 38 Python scripts under `ops/` and `research/` found 19 whose basename
or path was not referenced by another tracked UTF-8 file at the audit commit.
Manual CLI tools need not be imported by application code. Reviewing their docstrings
and entry points did not establish that they are obsolete. No file was moved to
`archive/`; no archive CHANGELOG entry is warranted without a verified move.

| Candidate group | Scripts and actual purpose |
| --- | --- |
| Measurements | `benchmark_dublin.py`, `compare_explanations.py`, `profile_explanations.py`: separate inference/evidence measurements |
| Isolated replay/fault drills | `load_dublin_fixture.py`, `load_dublin_trained_fixture.py`, `material_outage_dublin.py`, `run_shadow_smoke.py` |
| Operational setup | `install_backup_helper.py`, `setup_monitor.py`: explicit manual service/helper installation |
| HTTPS inspection | `probe_https_mux.py`, `verify_https.py` |
| Read-only verification | `verify_official_dublin.py`, `verify_public_mcp.py`, `verify_shared_quotas.py`, `verify_source_dublin.py`, `verify_telemetry_dublin.py`, `mcp_smoke.py` |
| Private research evidence | `fetch_research_evidence.py`: fetches existing completed attempts |
| Provider inventory | `probe_providers.py`: calls provider APIs at module execution; not an import-safe library |

Their static metadata was inspected; these scripts were not run. Some create disposable databases, install services,
or call providers; none belongs in an automatic local fixture startup. The provider
inventory remains outside the frozen runtime, and this audit did not spend provider
quota. Zero files have been established as safely removable solely from the scan.

## Final consecutive clean-clone checks

A second new local clone at `514aa0b373ed82506187c3d337a95dbb68b18000` was tested
with two sequential full-suite invocations, stopping on any failed run. Both passed:

| Run | Actual result |
| --- | --- |
| First | 186 passed, 1 skipped; 107.80 s |
| Second | 186 passed, 1 skipped; 110.96 s |

The clone remained Git-clean at that exact commit. The single skip is the Windows
symlink case. This closes the requested consecutive Python-suite gate; it does not
turn the unavailable Docker fixture run into a pass or prove a fresh dependency
installation. The incident logging remains local and production remains cee53c0.
