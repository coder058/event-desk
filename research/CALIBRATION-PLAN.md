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

## Actual isolated local component — October 6

`build_calibration_local.py` trained the inherited facts pipeline on 4,239 outcome
rows from Q4/Q1 and produced 2,060 Q2 asset predictions. The official scorer used
1,996 surprise-complete rows: imputed delta R-squared 0.008100532382788295.
Hashes/configuration are in reports/calibration-local.json; artifact and per-asset
predictions stay private. The deployed through-Q2 artifact's hash was verified
unchanged. This is an input for future blend fitting, not an approved hybrid or a
model-selection result. Q2 is now inspected development evidence.

## Bounded collection / exploratory fit implementation

`collect_llm.py --wait-local-seconds` allows waiting only for the local ledger's
recorded window release, within the caller's explicit bound. External cooldowns
remain stops. Admission is checked again transactionally; this cannot establish
account-wide available quota. Research SQLite and production PostgreSQL budgets
are still separate; they must share/synchronize usage before concurrent live LLM
collection is enabled. Production remains local-only.

`probe_blend.py` fits the inherited fixed ridge alpha with training-only standard
scaling, once on the retained Q2 successful-output cohort. It verifies exact
archive/input hashes and source quotes, rejects conflicting favorable retries,
and retains immutable input snapshots. It evaluates Q3 local-only, LLM-only and
hybrid on the same available cohort and full official imputation sample. Missing
LLM-only outputs use the official mean; missing hybrid outputs use local.
Leave-one-event-out is sensitivity, not a confidence interval.

The exploratory artifact is always unapproved. Small chronological cohorts can
cover only a few days and cannot establish deployment readiness or representative
quarter-wide skill. Further collection is evidence gathering, not a parameter
sweep on Q3. No fit/evaluation result is asserted before running it.

## Actual first fixed blend probe — October 6

`reports/blend-probe-20261006T103757.json` retains the actual 42-row Q2 fit and
28-row Q3 response cohort. The official scorer used 25 surprise-complete paired
rows. Blend underperformed local both on the paired cohort and full local-fallback
quarter; no deployment approval was granted. Matrix rank was six for seven
features, with constant `surprise_vs_preview`. Groq stopped collection on an
actual TPD 429 (200,000 limit, 198,677 used, 1,637 requested); local ledger usage
did not imply available account capacity. Do not bypass that account limit.
Further evidence must remain label-blind; do not tune repeatedly on this cohort.
