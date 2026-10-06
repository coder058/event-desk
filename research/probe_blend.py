"""Chronological exploratory blend fitting. Never writes an approved production artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from train import frame, load

from eventdesk.blend import row
from eventdesk.llm import PROMPT_HASH, prompt_materials
from eventdesk.materials import input_hash, select_items
from eventdesk.model import LocalModel
from eventdesk.schemas import LLMAnalysis
from eventdesk.vendor.scoring import score_submission


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validated_samples(records: list[dict[str, Any]], attempts: list[dict[str, Any]], *,
                      quarter: str, provider: str, model: str) -> dict[str, LLMAnalysis]:
    by_id = {record["event_id"]: record for record in records}
    if len(by_id) != len(records):
        raise ValueError("Archive event identity is duplicated")
    validated = {}
    for attempt in attempts:
        if (not attempt.get("analysis") or attempt.get("prompt_hash") != PROMPT_HASH
                or attempt.get("provider") != provider or attempt.get("model") != model):
            continue
        event_id = attempt["event_id"]
        if attempt["quarter"] != quarter or event_id not in by_id:
            raise ValueError("Evidence quarter/event does not match the retained archive")
        items = select_items(by_id[event_id])
        if attempt["inputs_hash"] != input_hash(items):
            raise ValueError("Evidence was generated from different archive inputs")
        analysis = LLMAnalysis.model_validate(attempt["analysis"])
        analysis.validate_quotes(prompt_materials(items))
        if event_id in validated and validated[event_id] != analysis:
            raise ValueError("Conflicting valid outputs: cannot choose the favorable retry")
        validated[event_id] = analysis
    return validated


def read_attempts(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--q2-evidence", type=Path, required=True)
    parser.add_argument("--q3-evidence", type=Path, required=True)
    parser.add_argument("--provider", choices=("groq", "gemini"), required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    # SOURCE: fixed Q4/Q1 local component -> Q2 fit, deployed through-Q2 component -> Q3 validation.
    calibration = json.loads(Path("reports/calibration-local.json").read_text(encoding="utf-8"))
    q2_local_path = Path("private/calibration/q2-local-out-of-training.jsonl")
    if digest(q2_local_path) != calibration["private_predictions_sha256"]:
        raise ValueError("Retained out-of-training-sample predictions changed")
    q2_local = read_attempts(q2_local_path)
    local_by_asset = {(value["event_id"], value["identifier_value"]): value for value in q2_local}
    if len(local_by_asset) != len(q2_local) or any(value["local_model_sha256"] != calibration["artifact_sha256"]
                                                for value in q2_local):
        raise ValueError("Calibration local prediction identity/provenance invalid")
    paths = {q: args.archive/(q+".jsonl.gz") for q in ("2026Q2", "2026Q3")}
    if digest(paths["2026Q2"]) != calibration["datasets"]["2026Q2"]["sha256"]:
        raise ValueError("Q2 archive differs from calibration archive")
    records = {q: load(path) for q, path in paths.items()}
    evidence_paths = {"2026Q2": args.q2_evidence, "2026Q3": args.q3_evidence}
    # Collection may still append. Retain the exact bytes used instead of hashing a later file version.
    evidence_bytes = {q: path.read_bytes() for q, path in evidence_paths.items()}
    evidence_hashes = {q: hashlib.sha256(raw).hexdigest() for q, raw in evidence_bytes.items()}
    evidence = {q: validated_samples(records[q], [json.loads(line) for line in evidence_bytes[q].decode("utf-8")
        .splitlines() if line.strip()], quarter=q,
                                    provider=args.provider, model=args.model) for q in paths}
    event_times = {q: [datetime.fromisoformat(record["event_datetime"].replace("Z", "+00:00"))
                      for record in records[q] if record["event_id"] in evidence[q]] for q in paths}
    if not all(event_times.values()) or any(value.tzinfo is None for values in event_times.values() for value in values):
        raise ValueError("Both cohorts require timezone-aware event dates")
    if max(event_times["2026Q2"]) >= min(event_times["2026Q3"]):
        raise ValueError("Training and validation evidence chronology overlaps")
    _, training = frame(records["2026Q2"], False)
    train_x, train_y = [], []
    for value in training.itertuples():
        if value.event_id not in evidence["2026Q2"]:
            continue
        local = local_by_asset[(value.event_id, value.identifier_value)]["local_prediction"]
        train_x.append(row(local, evidence["2026Q2"][value.event_id]))
        train_y.append(value.y)
    if not train_x or len(train_x) <= len(train_x[0]):
        # SOURCE: require more observations than feature dimensions for this exploratory fit.
        # This algebraic floor does not establish statistical adequacy or deployment readiness.
        raise ValueError("Insufficient training observations even for the exploratory feature dimensions")
    xtrain = pd.DataFrame(train_x)
    alpha = json.loads(Path("research/candidates.json").read_text(encoding="utf-8"))["facts_baseline"]["alpha"]
    pipelines = {}
    for name, columns in (("llm_only", [c for c in xtrain if c != "local"]), ("blend", list(xtrain))):
        # SOURCE: inherited alpha=3; training-only scaling follows the existing numeric-feature pipeline.
        # Neither is calibrated optimal for this small cohort. No validation-based sweep is performed.
        pipeline = Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=alpha))])
        pipeline.fit(xtrain[columns], np.asarray(train_y))
        pipelines[name] = (pipeline, columns)
    freeze = json.loads(Path("competition-config.json").read_text(encoding="utf-8"))
    local = LocalModel(Path("artifacts/local-model.joblib"), expected_sha256=freeze["model_sha256"])
    _, validation = frame(records["2026Q3"], False)
    by_id = {record["event_id"]: record for record in records["2026Q3"]}
    validation["local_only"] = [local.predict(select_items(by_id[event_id])) for event_id in validation.event_id]
    validation["blend"] = validation["local_only"]
    validation["llm_only"] = np.nan
    matched = []
    for index, value in validation.iterrows():
        analysis = evidence["2026Q3"].get(value.event_id)
        if analysis is None:
            continue
        features = pd.DataFrame([row(float(value.local_only), analysis)])
        for name, (pipeline, columns) in pipelines.items():
            prediction = float(pipeline.predict(features[columns])[0])
            if not np.isfinite(prediction):
                raise ValueError("Nonfinite fitted validation prediction")
            # SOURCE: official percentile interval; identical clipping to the runtime mapping.
            validation.loc[index, name] = float(np.clip(prediction, 0, 1))
        matched.append(index)
    metrics = {name: score_submission(validation, name) for name in ("local_only", "llm_only", "blend")}
    paired = validation.loc[matched]
    paired_metrics = {name: score_submission(paired, name) for name in metrics}
    validation_ids = set(paired.event_id)
    sensitivity = []
    for event_id in sorted(validation_ids):
        subset = paired[paired.event_id != event_id]
        sensitivity.append({name: score_submission(subset, name)["delta_r_squared"] for name in metrics})
    created = datetime.now(UTC)
    label = created.strftime("%Y%m%dT%H%M%S")
    target = Path("private/calibration")/("blend-probe-"+label+".joblib")
    report_path = Path("reports")/("blend-probe-"+label+".json")
    if target.exists() or report_path.exists():
        raise RuntimeError("Refusing to overwrite exploratory evidence")
    for quarter, raw in evidence_bytes.items():
        snapshot = target.parent/("evidence-"+evidence_hashes[quarter]+".jsonl")
        if snapshot.exists():
            if snapshot.read_bytes() != raw:
                raise ValueError("Retained evidence snapshot changed")
        else:
            with snapshot.open("xb") as stream:
                stream.write(raw)
    pipeline, _ = pipelines["blend"]
    joblib.dump({"schema_version": "eventdesk-blend-v1", "deployment_approved": False,
        "pipeline": pipeline, "prompt_hash": PROMPT_HASH, "provider": args.provider,
        "provider_model": args.model, "train_quarter": "2026Q2", "validation_quarter": "2026Q3"}, target)
    def dates(quarter: str) -> dict[str, Any]:
        values = sorted(record["event_datetime"] for record in records[quarter]
                        if record["event_id"] in evidence[quarter])
        return {"events": len(values), "first": values[0] if values else None, "last": values[-1] if values else None}
    report = {"created_at": created.isoformat(), "provider": args.provider, "model": args.model,
        "prompt_sha256": PROMPT_HASH, "artifact_sha256": digest(target), "deployment_approved": False,
        "training_rows": len(train_x), "training_feature_rank": int(np.linalg.matrix_rank(xtrain)),
        "feature_columns": list(xtrain), "alpha": alpha,
        "local_train_artifact_sha256": calibration["artifact_sha256"], "local_validation_artifact_sha256": local.sha256,
        "archive_sha256": {q: digest(path) for q, path in paths.items()},
        "evidence_sha256": evidence_hashes,
        "cohorts": {q: dates(q) for q in paths}, "paired_validation_rows": len(paired),
        "metrics_full_imputation": metrics, "metrics_paired_validation": paired_metrics,
        "leave_one_validation_event_out": sensitivity,
        "coefficients_scaled": {name: {"intercept": float(p.named_steps["ridge"].intercept_),
            "features": dict(zip(cols, p.named_steps["ridge"].coef_.tolist(), strict=True))}
            for name, (p, cols) in pipelines.items()},
        "limits": ["Exploratory, not approved for deployment; no generative advantage established",
            "Q3 previously examined and unsealed; development validation, not untouched test",
            "Chronological successful-output cohorts may cover only a small portion of each quarter",
            "Leave-one-event-out is sensitivity, not a confidence interval or win probability",
            "LLM-only missing outputs use official mean imputation; blend missing outputs use local",
            "Q2 local feature is trained through Q1; Q3 local feature is trained through Q2",
            "Only fixed settings fitted; no candidate selected using validation outcomes",
            "No live scored competition or trading performance"]}
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path), "training_rows": len(train_x),
                      "paired_validation_rows": len(paired), "deployment_approved": False}))


if __name__ == "__main__":
    main()
