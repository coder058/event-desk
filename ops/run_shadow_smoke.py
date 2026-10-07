"""Run one bounded isolated evidence smoke on Dublin; retain safe fictional proof locally."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH


def main() -> None:
    # SOURCE: deployed worker image/network and existing root-owned provider/database environment.
    command = ["sudo", "docker", "run", "--rm", "--network", "eventdesk_default",
        "--env-file", "/etc/eventdesk/env", "--env-file", "/etc/eventdesk/runtime.env",
        "--env", "EVENTDESK_ALLOW_REAL_PROVIDER_SMOKE=true", "--env", "EVENTDESK_LLM_ENABLED=true",
        "--env", "EVENTDESK_BLEND_PATH=", "--volume", "/var/lib/eventdesk/models:/models:ro",
        # GUESS: same 512 MiB ceiling as the production trained-model worker. # UNCALIBRATED GUESS
        "--memory", "512m", "--read-only", "--tmpfs", "/tmp", "eventdesk-worker",
        "python", "research/shadow_smoke.py"]
    result = subprocess.run(SSH+[shlex.join(command)], capture_output=True)
    if result.returncode:
        raise RuntimeError("Isolated shadow smoke failed; remote output withheld")
    proof = json.loads(result.stdout)
    if (proof.get("schema_version") != "eventdesk-shadow-smoke-v1" or proof.get("fixture_only") is not True
            or proof.get("prediction_unchanged") is not True or proof.get("external_official_requests") != 0):
        raise ValueError("Expected isolated unchanged-prediction proof")
    Path("reports/shadow-provider-smoke.json").write_text(json.dumps(proof, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"shadow_state": proof["shadow_state"], "actual_provider_requests": proof["actual_provider_requests"],
        "prediction_unchanged": proof["prediction_unchanged"], "external_official_requests": proof["external_official_requests"]}))


if __name__ == "__main__":
    main()
