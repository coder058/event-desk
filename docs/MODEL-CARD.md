# Event Desk — model card

## Task and current status

Event Desk predicts the percentile of an earnings event's next-day abnormal
stock return relative to the quarter's event outcomes. The output is a rank in
the competition's permitted range, not a trade, price target or win probability.

Two genuine official TEST round trips are verified as of October 8, 2026.
They submit a neutral prediction and bypass trained inference. No non-TEST
prediction is accepted and no live score is verified. The portal lists three
October 7 market events as refused deliveries. A webhook-contract incompatibility
was reproduced and repaired; its role in those historical failures is unproven.
A genuine market-event round trip remains to be verified.

## Inputs and model

The deployed forecast uses supplied official earnings-call facts, selected by
item identity. Outcome/return labels are excluded from runtime features. TF-IDF
features feed fitted ridge regression; the API-bound output uses the same
clipping as historical evaluation. Missing or invalid usable text falls back
to the fitted training target mean and is explicitly recorded.

Training quarters are 2025Q4, 2026Q1 and 2026Q2. Validation is 2026Q3, which was
previously examined and is development evidence, not an untouched test.
Inherited hyperparameters are recorded in the frozen configuration; they are
not claimed to be optimal or independently calibrated.
[Frozen configuration](https://github.com/coder058/event-desk/blob/main/competition-config.json).

The worker reads only the signed event's allowlisted official material URL.
The webhook example need not contain the calendar knowledge_cutoff. Official
platform-delivered materials are permitted by the competition FAQ; supplemental
sources would require the calendar cutoff and are not enabled in this forecast.
[Source contract and repair](https://github.com/coder058/event-desk/blob/main/docs/INCIDENT-2026-10-08-delivery-4xx.md).

## Operation and optional AI evidence

The service verifies the signature over original bytes, commits the PostgreSQL
inbox before ACK, and deduplicates deliveries. Input/model/configuration hashes
and the prediction payload are retained before submission. Network uncertainty
retries the persisted prediction; it cannot generate a different answer.
API acceptance is distinct from timely scoring eligibility.

Optional Gemini/Groq evidence runs after submission in a separate queue. It
retains structured sub-scores, provider/model provenance and quotations checked
against supplied input. Quote matching checks attribution, not truth. This lane
cannot alter the deployed forecast; the AI blend remains disabled. Numeric local
feature contributions explain the fitted calculation, not causality.

## Evaluation and limitations

The historical facts-only candidate's imputed incremental R-squared was
0.04095315077531125; the fitted blend's was 0.03871855275695035. These are
previously examined development results, not prospective scores or profit.
Only 25 surprise-complete validation rows had paired AI outputs, a small selected
cohort; missing AI outputs also affect the full-quarter comparison.
[Baseline](https://github.com/coder058/event-desk/blob/main/reports/archive-eval.md),
[blend experiment](https://github.com/coder058/event-desk/blob/main/reports/blend-probe-20261006T103757.json).

Free providers can fail; the single VPS is a failure point. Off-host alerts are
not connected. Historical refusal reasons were not retained. TEST success does
not validate real-event inference, score eligibility or predictive skill.
Prospective outcomes and coverage are still missing. No calibrated winning
probability, generative advantage, trading edge or profitability is established.

## Authorship and inspection

This is an AI-assisted project. Jordi directed scope and accounts; Codex and
Claude assisted implementation, tests, analysis and documentation. No per-line
authorship percentages or unaided implementation claim is made.

[Code](https://github.com/coder058/event-desk) ·
[Live observations](https://52.17.192.36.sslip.io/) ·
[Labelled synthetic walkthrough](https://52.17.192.36.sslip.io/walkthrough)
