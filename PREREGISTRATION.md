# Initial competition prediction declaration — 2026-10-05

This declaration precedes the scoring period beginning 12 October 2026. It freezes
the initial local prediction method, not a claim that registration/network testing
is complete. Public HTTPS and the actual portal test remain pending.

Canonical configuration: `competition-config.json`.
SHA-256: `8fb8ab4da4c57c0863a28a0425b31398a51a52bbc96201eeea7ac2c61d1f6f76`.
The worker verifies model bytes before deserialization, full feature-builder source,
prediction code, rule-linked scorer, evidence prompt and enabled provider pins.
An undocumented artifact or prediction-affecting blend cannot start this worker.
Configuration hashes are retained with each new immutable prediction and heartbeat.

## Training and initial selection

- Closed archive train quarters: 2025Q4, 2026Q1, 2026Q2; 6,299 scored asset rows.
- Facts-only TF-IDF unigram/bigram ridge model. Alpha 3, min_df 5 and max_features
  60,000 were inherited from the owner's earlier research, not calibrated optimal.
- One fixed enriched candidate added preview/options/missingness. Q3 imputed ΔR²
  was 0.022485843848399356 versus 0.04095315077531125 for facts-only; facts-only
  was selected. Full source/data/scorer hashes are in reports/archive-eval.json.
- Q3: 2,362 predictions, 2,275 numeric-surprise scorer rows. Previously examined,
  unsealed development validation; **not an untouched test**. No new parameter sweep.
- Model SHA: `da212d24d1f3bb2c0d8528d62160667f7ca61029e748ca8dac6b5df9a2210bce`.

## Prediction and information policy

Official API materials only; binding rules permit those delivered event materials
after knowledge_cutoff. External future information, outcome blocks, baseline
predictions and scorer surprise metrics never enter the feature builder. No live
batch ranks are calculated using future events. Raw regression outputs are clipped
to [0,1], identically offline and at runtime. Missing/invalid materials use the
already-fitted training-target mean. TEST uses the official unscored neutral value.

Predictions are persisted before POST and cannot be revised during a retry.
Receipt/deadline identity survives duplicate deliveries. API acceptance is separate
from timeliness and scoring eligibility; received events are not the calendar
denominator. Report both failures and missing observations rather than claiming
100% eligible coverage from infrastructure fixtures.

## Generative AI and prospective changes

The initial percentile uses **no LLM blend**. Free Gemini/Groq structured scores may
be collected after submission as separate evidence, under quota/deadline guards;
they cannot explain retrospectively or change the regression prediction. Evidence
confidence is not win probability. Offline alternate-model probes have independent
provider/model/prompt provenance and are not deployment decisions.

A prediction-affecting hybrid requires chronological fitting/validation and a
coverage/leakage review under research/CALIBRATION-PLAN.md. A later method or pin
change must produce a new manifest/hash and dated reason before activation. Keep
each event's original configuration hash; do not rewrite earlier records or apply
new features retrospectively. Post-start changes cannot be called preregistered.

## What this does not establish

No official live score or ten-day eligible coverage exists yet. Archive ΔR² is not
profitability, calibrated trade probability or a portfolio return. Fixtures measured
plumbing capacity under one load, not future network/provider reliability. SEC event
studies and paper portfolios remain separate future stages.
