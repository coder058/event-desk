"""Explicit deployment settings; secret values never participate in logs."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Submission:
    slot: str
    api_key: str = field(repr=False)
    webhook_secret: str = field(repr=False)


@dataclass(frozen=True)
class Settings:
    database_url: str
    model_path: Path
    submissions: dict[str, Submission]
    fixture_mode: bool
    material_hosts: frozenset[str]

    @classmethod
    def from_env(cls) -> Settings:
        fixture = os.getenv("EVENTDESK_FIXTURE_MODE", "false").lower() == "true"
        submissions: dict[str, Submission] = {}
        # SOURCE: official rules permit at most five submissions for one account.
        for index in range(1, 6):
            suffix = "" if index == 1 else f"_S{index}"
            key, secret = os.getenv("EM_API_KEY" + suffix, ""), os.getenv("EM_WEBHOOK_SECRET" + suffix, "")
            if bool(key) != bool(secret):
                raise ValueError(f"Incomplete credentials for slot s{index}; values withheld")
            if key and secret:
                submissions[f"s{index}"] = Submission(f"s{index}", key, secret)
        if fixture and not submissions:
            # SOURCE: published official test vector, not an owner credential.
            submissions["s1"] = Submission("s1", "fixture-only", "whsec_dGVzdC1zZWNyZXQtMzItYnl0ZXMtZm9yLXRlc3R2ZWN0")
        if not submissions:
            raise ValueError("No submission configured")
        return cls(os.getenv("DATABASE_URL", "sqlite:///data/eventdesk.sqlite"),
                   Path(os.getenv("EVENTDESK_MODEL_PATH", "artifacts/local-model.joblib")),
                   submissions, fixture,
                   frozenset(host.strip() for host in os.getenv("EVENTDESK_MATERIAL_HOSTS", "").split(",") if host.strip()))


# SOURCE: official production competition API verified with the existing production key.
COMPETITION_ORIGIN = "https://api.explainingmarkets.ai/v1"
# SOURCE: official five-minute budget from ACK; receipt is a conservative earlier starting point.
PREDICTION_BUDGET_SECONDS = 300
# SOURCE: mission requires at least 30 seconds remaining for final submission.
SUBMISSION_RESERVE_SECONDS = 30
