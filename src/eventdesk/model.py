"""Load a trusted local artifact; never use quarter-wide future ranks at runtime."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd

from eventdesk.materials import feature_row


class LocalModel:
    def __init__(self, path: Path, *, expected_sha256: str | None = None) -> None:
        raw = path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and self.sha256 != expected_sha256:
            raise ValueError("Trained artifact hash differs from the declaration")
        # Artifact is created by our trainer and mounted read-only, never downloaded from a webhook.
        # Load precisely the bytes hashed above, not a pathname that could be replaced between reads.
        self.artifact = cast(dict[str, Any], joblib.load(io.BytesIO(raw)))
        if self.artifact.get("schema_version") != "eventdesk-local-v1":
            raise ValueError("Unknown model artifact schema")
        self.training_mean = float(self.artifact["training_mean"])
        if not np.isfinite(self.training_mean) or not 0 <= self.training_mean <= 1:
            raise ValueError("Invalid fitted fallback mean")
        pipeline = self.artifact["pipeline"]
        # SOURCE: static fitted metadata; previously regenerated for every event's explanation.
        self._feature_names = pipeline.named_steps["features"].get_feature_names_out()
        self._coefficients = np.asarray(pipeline.named_steps["ridge"].coef_).ravel()
        self._intercept = float(pipeline.named_steps["ridge"].intercept_)

    def predict(self, items: dict[str, Any]) -> float:
        enriched = bool(self.artifact["enriched"])
        row = feature_row(items, enriched=enriched)
        # SOURCE: fitted training mean when official materials cannot be obtained, not invented 0.5.
        if not row["text"].strip():
            return self.training_mean
        frame = pd.DataFrame([row])
        raw = float(self.artifact["pipeline"].predict(frame)[0])
        if not np.isfinite(raw):
            raise ValueError("Nonfinite model prediction")
        # SOURCE: official API permitted [0,1]; evaluation uses this same clipping.
        return float(np.clip(raw, 0.0, 1.0))

    def explain(self, items: dict[str, Any]) -> dict[str, Any]:
        """Actual linear feature contributions, not invented agent thoughts or a causal explanation."""
        row = feature_row(items, enriched=bool(self.artifact["enriched"]))
        if not row["text"].strip():
            return {"kind": "fitted_training_mean", "prediction": self.training_mean,
                    "limits": "Official facts missing; no textual inference was made"}
        pipeline = self.artifact["pipeline"]
        transformed = pipeline.named_steps["features"].transform(pd.DataFrame([row]))
        if hasattr(transformed, "tocsr"):
            sparse = transformed.tocsr()
            sparse.sum_duplicates()
            indices, values = sparse.indices, sparse.data
        else:
            dense = np.asarray(transformed).ravel()
            indices = np.flatnonzero(dense)
            values = dense[indices]
        coefficients = self._coefficients[indices]
        contributions = values * coefficients
        intercept = self._intercept
        raw = float(intercept + contributions.sum())
        if not np.isfinite(raw):
            raise ValueError("Nonfinite explanation")
        # GUESS: five displayed terms per decision; a presentation cap, not a prediction threshold. # UNCALIBRATED GUESS
        displayed = sorted(np.flatnonzero(contributions), key=lambda i: (-abs(contributions[i]), int(indices[i])))[:5]
        terms: list[dict[str, Any]] = [{"feature": str(self._feature_names[indices[i]]), "feature_value": float(values[i]),
                  "coefficient": float(coefficients[i]), "contribution": float(contributions[i])}
                 for i in displayed]
        return {"kind": "tf_idf_ridge_computation", "intercept": intercept,
                "linear_total": raw, "prediction": float(np.clip(raw, 0, 1)), "terms": terms,
                "other_terms_contribution": float(contributions.sum() - sum(t["contribution"] for t in terms)),
                "limits": "Correlational text-feature weights; not causal evidence or a win probability"}
