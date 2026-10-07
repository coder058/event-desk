"""Refuse undocumented competition prediction changes; credentials never enter this manifest."""
from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from eventdesk import materials
from eventdesk.config import COMPETITION_ORIGIN, PREDICTION_BUDGET_SECONDS, SUBMISSION_RESERVE_SECONDS
from eventdesk.llm import PROMPT_HASH
from eventdesk.model import LocalModel

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class CompetitionFreeze(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["eventdesk-competition-freeze-v1"]
    declared_at: AwareDatetime
    method: Literal["facts_tfidf_ridge"]
    model_sha256: Digest
    prediction_code_sha256: Digest
    feature_code_sha256: Digest
    scorer_sha256: Digest
    scorer_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    prompt_sha256: Digest
    train_quarters: list[str]
    validation_quarter: str
    validation_limits: str
    provider_models: dict[str, str]
    submission_origin: str
    prediction_budget_seconds: int
    submission_reserve_seconds: int
    llm_affects_prediction: Literal[False]
    post_submission_evidence_allowed: bool
    parameter_source: str


def code_hashes() -> dict[str, str]:
    def digest(source: str) -> str:
        return hashlib.sha256(source.replace("\r\n", "\n").encode()).hexdigest()
    return {"prediction_code_sha256": digest(inspect.getsource(LocalModel.predict)),
            "feature_code_sha256": digest(inspect.getsource(materials))}


def verify_freeze(path: Path, model: LocalModel, *, hybrid_enabled: bool,
                  provider_models: dict[str, str] | None = None,
                  post_submission_evidence_enabled: bool = False) -> str:
    raw = path.read_bytes()
    freeze = CompetitionFreeze.model_validate_json(raw)
    if model.sha256 != freeze.model_sha256 or model.artifact["enriched"]:
        raise ValueError("Trained artifact differs from the declared facts baseline")
    for name, digest in code_hashes().items():
        if getattr(freeze, name) != digest:
            raise ValueError("Prediction/feature code differs from the declaration")
    scorer = Path(__file__).parent / "vendor/scoring.py"
    if hashlib.sha256(scorer.read_bytes()).hexdigest() != freeze.scorer_sha256:
        raise ValueError("Declared scorer source changed")
    # SOURCE: full commit incorporated by the binding rules and retained in THIRD_PARTY.md.
    if freeze.scorer_commit != "501bd3182cd42cf61a727e05bd4b3089b8d1338d":
        raise ValueError("Declared scorer commit differs from the rule-linked pin")
    if freeze.prompt_sha256 != PROMPT_HASH:
        raise ValueError("Structured evidence prompt differs from the declaration")
    if (freeze.submission_origin != COMPETITION_ORIGIN or
            freeze.prediction_budget_seconds != PREDICTION_BUDGET_SECONDS or
            freeze.submission_reserve_seconds != SUBMISSION_RESERVE_SECONDS):
        raise ValueError("Submission policy differs from the declaration")
    if hybrid_enabled:
        raise ValueError("The current declaration permits no prediction-affecting LLM blend")
    if post_submission_evidence_enabled and not freeze.post_submission_evidence_allowed:
        raise ValueError("Post-submission evidence is not permitted by the declaration")
    # A missing optional key must not prevent local coverage; each enabled provider must still use its pin.
    if provider_models is not None and any(freeze.provider_models.get(name) != model_name
                                          for name, model_name in provider_models.items()):
        raise ValueError("Runtime provider/model pins differ from the declaration")
    # SOURCE: repository .gitattributes declares LF. Windows CRLF formatting must not change a version hash.
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
