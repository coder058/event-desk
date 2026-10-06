"""Fixed through-Q1 local model for out-of-training-sample Q2 blend features."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from train import frame, load

from eventdesk.vendor.scoring import score_submission


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    directory = Path("private/calibration")
    artifact = directory/"local-through-q1.joblib"
    prediction_file = directory/"q2-local-out-of-training.jsonl"
    if artifact.exists() or prediction_file.exists():
        raise RuntimeError("Refusing to overwrite retained calibration evidence")
    # SOURCE: declared calibration plan: Q4/Q1 train, Q2 collection, Q3 validation.
    train_quarters = ("2025Q4", "2026Q1")
    test_quarter = "2026Q2"
    # SOURCE: inherited fixed baseline, no tuning or selection on Q2 outcomes here.
    config = json.loads(Path("research/candidates.json").read_text())["facts_baseline"]
    records = {q: load(args.archive/(q+".jsonl.gz")) for q in (*train_quarters, test_quarter)}
    datasets = {q: {"sha256": hashlib.sha256((args.archive/(q+".jsonl.gz")).read_bytes()).hexdigest(),
                    "events": len(records[q])} for q in records}
    deployment = Path("artifacts/local-model.joblib")
    deployment_hash = hashlib.sha256(deployment.read_bytes()).hexdigest()
    xs, ys = [], []
    for quarter in train_quarters:
        features, outcomes = frame(records[quarter], False)
        xs.append(features)
        ys.extend(outcomes["y"].tolist())
    text = TfidfVectorizer(ngram_range=(1, 2), min_df=config["min_df"],
                          max_features=config["max_features"], sublinear_tf=True, stop_words="english")
    pipeline = Pipeline([("features", ColumnTransformer([("text", text, "text")])),
                         ("ridge", Ridge(alpha=config["alpha"]))])
    started = time.perf_counter()
    pipeline.fit(pd.concat(xs, ignore_index=True), np.asarray(ys))
    elapsed = time.perf_counter()-started
    x, outcomes = frame(records[test_quarter], False)
    predictions = np.clip(pipeline.predict(x), 0, 1)
    outcomes["local_q4q1"] = predictions
    score = score_submission(outcomes, "local_q4q1")
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump({"schema_version": "eventdesk-local-v1", "pipeline": pipeline, "enriched": False,
                 "training_mean": float(np.mean(ys)), "train_quarters": train_quarters,
                 "datasets": {q: datasets[q] for q in train_quarters}, "config": config}, artifact)
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    prediction_file.write_text("".join(json.dumps({"event_id": row.event_id,
        "identifier_value": row.identifier_value,
        "local_prediction": float(predictions[index]), "local_model_sha256": artifact_hash})+"\n"
        for index, row in enumerate(outcomes.itertuples())), encoding="utf-8")
    if hashlib.sha256(deployment.read_bytes()).hexdigest() != deployment_hash:
        raise RuntimeError("Production artifact changed during isolated calibration")
    report = {"created_at": datetime.now(UTC).isoformat(), "train_quarters": train_quarters,
        "validation_quarter": test_quarter, "train_rows": len(ys), "predicted_rows": len(outcomes),
        "train_seconds": elapsed, "artifact_sha256": artifact_hash,
        "private_predictions_sha256": hashlib.sha256(prediction_file.read_bytes()).hexdigest(),
        "deployment_artifact_unchanged_sha256": deployment_hash, "datasets": datasets, "config": config,
        "score": score,
        "limits": "Local component for chronological Q2 blend fitting only. Not a fitted hybrid, "
                  "new production model, untouched validation set, live score or trading result."}
    Path("reports/calibration-local.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
