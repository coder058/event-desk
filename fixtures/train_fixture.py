"""Synthetic model ONLY for keyless plumbing demos, never competition inference."""
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline

# PLACEHOLDER: synthetic text/targets test application wiring, not market skill.
pipeline = Pipeline([("features", ColumnTransformer([("text", TfidfVectorizer(), "text")])),
                     ("ridge", Ridge(alpha=1))])
pipeline.fit(pd.DataFrame({"text": ["Revenue increased guidance raised", "Revenue declined guidance cut"]}),
             [1.0, 0.0])
Path("/models").mkdir(exist_ok=True)
joblib.dump({"schema_version": "eventdesk-local-v1", "pipeline": pipeline,
             "enriched": False, "training_mean": 0.5, "fixture_only": True}, "/models/fixture.joblib")
