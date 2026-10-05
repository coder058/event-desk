"""Reproducible fixed-candidate chronological training, no API calls."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from eventdesk.materials import OPTION_NAMES, feature_row, select_items
from eventdesk.model import LocalModel
from eventdesk.vendor.scoring import add_percentiles, outcomes_frame, score_submission


def load(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def frame(records: list[dict[str, Any]], enriched: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    outcome = add_percentiles(outcomes_frame(records))
    by_id = {record["event_id"]: record for record in records}
    features = [feature_row(select_items(by_id[event_id]), enriched=enriched)
                for event_id in outcome["event_id"]]
    return pd.DataFrame(features), outcome


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/local-model.joblib"))
    args = parser.parse_args()
    config = json.loads(Path("research/candidates.json").read_text())
    quarters = config["train_quarters"] + [config["validation_quarter"]]
    records = {quarter: load(args.archive / (quarter + ".jsonl.gz")) for quarter in quarters}
    report: dict[str, Any] = {"created_at": datetime.now(UTC).isoformat(), "config": config,
                              "sklearn_version": sklearn.__version__, "datasets": {}, "candidates": {}}
    for quarter in quarters:
        path = args.archive / (quarter + ".jsonl.gz")
        report["datasets"][quarter] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                        "events": len(records[quarter])}
    models: dict[str, dict[str, Any]] = {}
    validation = records[config["validation_quarter"]]
    for name, enriched in (("facts_baseline", False), ("enriched", True)):
        settings = config[name]
        xs, ys = [], []
        for quarter in config["train_quarters"]:
            x, outcome = frame(records[quarter], enriched)
            xs.append(x)
            ys.extend(outcome["y"].tolist())
        xtrain = pd.concat(xs, ignore_index=True)
        text = TfidfVectorizer(ngram_range=(1, 2), min_df=settings["min_df"],
                              max_features=settings["max_features"], sublinear_tf=True,
                              stop_words="english")
        # SOURCE: original Claude baseline text settings; enriched numeric features are a fixed new candidate.
        transforms: list[Any] = [("text", text, "text")]
        if enriched:
            numeric = ["facts_missing", "preview_missing"] + [k for n in OPTION_NAMES for k in (n, n + "_missing")]
            transforms.append(("numeric", StandardScaler(), numeric))
        pipeline = Pipeline([("features", ColumnTransformer(transforms)),
                             ("ridge", Ridge(alpha=settings["alpha"]))])
        start = time.perf_counter()
        pipeline.fit(xtrain, np.asarray(ys))
        artifact = {"schema_version": "eventdesk-local-v1", "pipeline": pipeline, "enriched": enriched,
                    "training_mean": float(np.mean(ys)), "config": config, "datasets": report["datasets"]}
        models[name] = artifact
        xv, outcome = frame(validation, enriched)
        start_predict = time.perf_counter()
        raw = pipeline.predict(xv)
        predict_ms = (time.perf_counter() - start_predict) * 1000
        outcome["local"] = np.clip(raw, 0, 1)
        score = score_submission(outcome, "local")
        report["candidates"][name] = {"train_rows": len(ys), "validation_rows": len(outcome),
                                        "train_seconds": start_predict - start,
                                        "batch_prediction_ms": predict_ms, "score": score}
        if not enriched:
            # Reproduce the old helper's double-argsort labels separately, with corrected runtime clipping.
            legacy_y: list[float] = []
            for quarter in config["train_quarters"]:
                legacy_outcome = outcomes_frame(records[quarter])
                v = np.asarray(legacy_outcome["car1"])
                legacy_y.extend((np.argsort(np.argsort(v)) / (len(v) - 1)).tolist())
            pipeline.fit(xtrain, legacy_y)
            outcome["legacy_clipped"] = np.clip(pipeline.predict(xv), 0, 1)
            report["legacy_double_argsort"] = score_submission(outcome, "legacy_clipped")
            # Restore the official tie-handled target before saving deployment artifact.
            pipeline.fit(xtrain, ys)
    def metric(name: str) -> float:
        value = report["candidates"][name]["score"]["delta_r_squared_imputed"]
        return float(value) if value is not None else -float("inf")
    selected = "enriched" if metric("enriched") > metric("facts_baseline") else "facts_baseline"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(models[selected], args.output)
    deployed = LocalModel(args.output)
    # Check serialized single-event runtime, not just an in-memory batch pipeline.
    xv, outcome = frame(validation, bool(models[selected]["enriched"]))
    by_id = {record["event_id"]: record for record in validation}
    singles = [deployed.predict(select_items(by_id[event_id])) for event_id in outcome["event_id"]]
    if not np.allclose(singles, np.clip(models[selected]["pipeline"].predict(xv), 0, 1)):
        raise RuntimeError("Runtime/archive feature mismatch")
    report["selected"] = selected
    report["artifact_sha256"] = deployed.sha256
    report["official_scorer_sha256"] = hashlib.sha256(Path("src/eventdesk/vendor/scoring.py").read_bytes()).hexdigest()
    report["limits"] = ["Q3 is development validation after previous research inspection, not untouched test",
                         "LLM and fitted blend not evaluated yet", "No live competition or trading performance"]
    Path("reports").mkdir(exist_ok=True)
    Path("reports/archive-eval.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Closed-archive evaluation", "", f"Selected: **{selected}**.", "",
             "| Candidate | Train rows | Q3 rows | Imputed ΔR² |", "|---|---:|---:|---:|"]
    for name, result in report["candidates"].items():
        lines.append(f"| {name} | {result['train_rows']} | {result['validation_rows']} | {result['score']['delta_r_squared_imputed']} |")
    lines += ["", "LLM and blend: not evaluated. Runtime single-event predictions matched batch predictions.",
              "Scorer and data hashes are recorded in archive-eval.json.", "", "## Limits", ""]
    lines += ["- " + limit for limit in report["limits"]]
    Path("reports/archive-eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"selected": selected, "candidates": report["candidates"], "artifact_sha256": deployed.sha256}))


if __name__ == "__main__":
    main()
