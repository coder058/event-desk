import pytest


def test_terms_are_actual_linear_computation_not_a_retrospective_story(model):
    items = {"earnings-call-facts": ["Revenue increased guidance raised"]}
    trace = model.explain(items)
    assert trace["prediction"] == pytest.approx(model.predict(items))
    assert trace["linear_total"] == pytest.approx(trace["intercept"] + trace["other_terms_contribution"]
        + sum(term["contribution"] for term in trace["terms"]))
    for term in trace["terms"]:
        assert term["contribution"] == pytest.approx(term["feature_value"] * term["coefficient"])
    missing = model.explain({})
    assert missing["kind"] == "fitted_training_mean"
    assert missing["prediction"] == model.training_mean


def test_sparse_explanation_retains_dense_math_and_does_not_rebuild_vocabulary(model, tmp_path, monkeypatch):
    import copy

    import joblib
    import numpy as np
    import pandas as pd

    from eventdesk.materials import feature_row
    from eventdesk.model import LocalModel

    artifact = copy.deepcopy(model.artifact)
    artifact["pipeline"].named_steps["features"].sparse_output_ = True
    path = tmp_path / "sparse-fixture.joblib"
    joblib.dump(artifact, path)
    sparse_model = LocalModel(path)
    features = sparse_model.artifact["pipeline"].named_steps["features"]
    items = {"earnings-call-facts": ["Revenue increased guidance raised"]}
    transformed = features.transform(pd.DataFrame([feature_row(items, enriched=False)]))
    assert hasattr(transformed, "tocsr")
    ridge = sparse_model.artifact["pipeline"].named_steps["ridge"]
    reference = float(ridge.intercept_ + (transformed.toarray().ravel() * np.asarray(ridge.coef_).ravel()).sum())
    def rebuild_forbidden():
        raise AssertionError("Per-event vocabulary generation returned")
    monkeypatch.setattr(features, "get_feature_names_out", rebuild_forbidden)
    trace = sparse_model.explain(items)
    assert trace["linear_total"] == pytest.approx(reference)
    assert trace["prediction"] == pytest.approx(sparse_model.predict(items))
