from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline

from eventdesk.config import Settings, Submission
from eventdesk.model import LocalModel
from eventdesk.store import Store

# SOURCE: official public test vector; not an owner credential.
SECRET = "whsec_dGVzdC1zZWNyZXQtMzItYnl0ZXMtZm9yLXRlc3R2ZWN0"


@pytest.fixture(scope="session")
def model(tmp_path_factory):
    path = tmp_path_factory.mktemp("model") / "fixture.joblib"
    pipeline = Pipeline([("features", ColumnTransformer([("text", TfidfVectorizer(), "text")])),
                         ("ridge", Ridge(alpha=1))])
    # PLACEHOLDER: synthetic test labels verify wiring only, never competition skill.
    pipeline.fit(pd.DataFrame({"text": ["Revenue increased guidance raised", "Revenue declined guidance cut"]}),
                 [1, 0])
    joblib.dump({"schema_version": "eventdesk-local-v1", "pipeline": pipeline,
                 "enriched": False, "training_mean": 0.5, "fixture_only": True}, path)
    return LocalModel(path)


@pytest.fixture
def store(tmp_path):
    result = Store("sqlite:///" + str(tmp_path / "database.sqlite"))
    result.initialize_fixture()
    return result


@pytest.fixture
def settings(store):
    return Settings(str(store.engine.url), Path("fixture.joblib"),
                    {"s1": Submission("s1", "fixture-not-owner", SECRET)}, True, frozenset())
