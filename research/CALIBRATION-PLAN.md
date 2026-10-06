# Frozen structured-LLM calibration plan — 2026-10-05

The initial competition deployment remains facts-only. No guessed blend weight is used.

1. Use the same quoted sub-score prompt/schema/router for offline and runtime.
2. Collect deterministic archive samples from Q2 for fitting and Q3 for validation.
   Sample selection is label-blind (event datetime/id ordering); never select by return.
   Q2's local feature must come from a model trained on Q4/Q1 only; the deployed
   baseline trained through Q2 would supply an in-sample feature and is forbidden
   for blend fitting. Retain that calibration artifact's hash separately. Evaluate
   the fitted mapping with the deployed through-Q2 local model on Q3, recording
   this training-window difference instead of treating it as identical input quality.
3. Keep input, prompt, schema, provider/model hashes and every failed attempt. Retries
   obey persisted quotas; do not bypass free-account limits or silently replace models.
4. Fit a regression mapping local prediction and five sub-scores plus evidence
   confidence to the official percentile-rank target. Regularization is inherited
   from the existing ridge baseline (alpha=3); it is not known optimal for these features.
5. Compare local-only, LLM-only and fitted hybrid on the same chronological
   validation sample and the full imputed common sample. Missing LLM output falls
   back to the evaluated local model. Report sample size and uncertainty.
6. Do not deploy a hybrid merely because its fit or tiny-sample score looks higher.
   Require actual out-of-sample evidence and a review of coverage, leakage and model
   variability; if insufficient, retain local-only with LLM evidence in shadow.

The archive Q3 has previously been inspected and is not sealed. This is development
validation; Oct12 onward is the prospective scored observation period.
