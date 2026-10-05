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
