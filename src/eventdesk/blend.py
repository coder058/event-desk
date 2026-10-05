"""Fit-dependent percentile mapping: no heuristic or guessed blend coefficient."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd

from eventdesk.schemas import LLMAnalysis

SCORE_FIELDS = ("beat_vs_buyside_bar", "guidance_change", "tone", "new_risks", "surprise_vs_preview")


def row(local: float, analysis: LLMAnalysis) -> dict[str, float]:
    values = {name: float(getattr(analysis, name)) for name in SCORE_FIELDS}
    values["local"] = local
    values["confidence"] = analysis.confidence
    return values


class BlendModel:
    def __init__(self, path: Path) -> None:
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.artifact = cast(dict[str, Any], joblib.load(path))
        if self.artifact.get("schema_version") != "eventdesk-blend-v1":
            raise ValueError("Unknown blend schema")
        if not self.artifact.get("deployment_approved"):
            raise ValueError("Blend lacks evidence-based deployment approval")

    def predict(self, local: float, analysis: LLMAnalysis, *, prompt_hash: str,
                provider: str, provider_model: str) -> float:
        if (self.artifact["prompt_hash"] != prompt_hash
                or self.artifact["provider"] != provider
                or self.artifact["provider_model"] != provider_model):
            raise ValueError("Blend calibration/provider provenance mismatch")
        value = float(self.artifact["pipeline"].predict(pd.DataFrame([row(local, analysis)]))[0])
        if not np.isfinite(value):
            raise ValueError("Invalid fitted blend prediction")
        # SOURCE: official output interval; clipping is included in the calibration evaluation.
        return float(np.clip(value, 0, 1))

