"""Load a trusted local artifact; never use quarter-wide future ranks at runtime."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd

from eventdesk.materials import feature_row


class LocalModel:
    def __init__(self, path: Path) -> None:
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        # Artifact is created by our trainer and mounted read-only, never downloaded from a webhook.
        self.artifact = cast(dict[str, Any], joblib.load(path))
        if self.artifact.get("schema_version") != "eventdesk-local-v1":
            raise ValueError("Unknown model artifact schema")

    def predict(self, items: dict[str, Any]) -> float:
        enriched = bool(self.artifact["enriched"])
        row = feature_row(items, enriched=enriched)
        # SOURCE: fitted training mean when official materials cannot be obtained, not invented 0.5.
        if not row["text"].strip():
            return float(self.artifact["training_mean"])
        frame = pd.DataFrame([row])
        raw = float(self.artifact["pipeline"].predict(frame)[0])
        if not np.isfinite(raw):
            raise ValueError("Nonfinite model prediction")
        # SOURCE: official API permitted [0,1]; evaluation uses this same clipping.
        return float(np.clip(raw, 0.0, 1.0))
