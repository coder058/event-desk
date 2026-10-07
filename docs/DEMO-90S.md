# Event Desk — interview demo

This is a suggested rehearsal schedule, not a measured playback duration.
Open the [dashboard](https://52.17.192.36.sslip.io/) and [walkthrough](https://52.17.192.36.sslip.io/walkthrough) before the interview. Read the dashboard's timestamp and current states; do not substitute the dated observations below for fresh status.
The walkthrough loads retained evidence automatically. Its buttons change views; they do not send official events. Do not run a new provider probe to fill the demo.

## Suggested 90-second walkthrough

**0–12 seconds — dashboard: establish the boundary.**
“This is an earnings-event prediction service, not a trading bot. The dashboard separates retained jobs from official observations. We verified a genuine TEST; that TEST used a neutral prediction and does not establish model accuracy.”
Point to the current submission state and timestamp. If failures are visible, acknowledge them: the initial incident snapshot had three rejected deliveries and a later observation had 15 consecutive failures; their cause remains unknown. [TEST](../reports/official-test-20261007.json), [initial incident](../reports/delivery-failures-readonly-20261008.json), [follow-up](../reports/delivery-failures-followup-readonly-20261008.json).

**12–27 seconds — `1. Read the inputs`, then `2. Verify and retain`.**
“This example has fictional earnings text and a disposable SQLite database. It uses the actual receiver code. Retained checks show signed acceptance, deduplicated retry, altered-byte rejection and a signed conflicting-body rejection. This fixture does not measure public TLS or production PostgreSQL.” [Retained walkthrough](../reports/walkthrough.json)

**27–43 seconds — `3. Calculate the forecast`.**
“The archive-trained model encodes the supplied facts as TF-IDF features and combines fitted ridge weights. The table reconciles displayed contributions with the other terms and intercept. The output is a market-reaction percentile, not a probability of winning or causal reasoning.”
Point to one positive and one negative retained contribution; use their displayed names rather than inventing a narrative. [Retained calculation](../reports/walkthrough.json)

**43–57 seconds — `4. Persist the decision`.**
“The payload and hashes are retained before sending. An uncertain external result must reuse this prediction rather than recompute it. This demo ends in simulation; it does not submit to the competition or claim a production restart.”
Expand **Exact prediction payload**. [Retained payload](../reports/walkthrough.json)

**57–72 seconds — `5. Inspect the outcome`, then `6. Separate AI evidence`.**
“The demo outcome is simulated. Separately retained provider evidence is labelled as a fictional-input smoke. It validates source quotations and provenance, but cannot rewrite the local forecast. If that report is unavailable, the page says so instead of filling it with generated evidence.”
Explain that exact quotation matching checks attribution, not whether every sub-score is justified. [Walkthrough](../reports/walkthrough.json), [separate provider smoke](../reports/shadow-provider-smoke.json)

**72–90 seconds — measured decision, then remaining risk.**
“The historical blend had lower incremental R² than local-only, so we kept it disabled. Warm local inference had millisecond percentiles, but those exclude network and durable submission. The next evidence is real scored outcomes and a resolved delivery incident; this is not established edge.”
Point to [the scoped measurements](PORTFOLIO-SUMMARY.md), not an inferred live latency or a claim of profitability.

## Three difficult questions

### “Is there edge?”

“No live or tradable edge is established. The official TEST verifies transport only. The historical metric is incremental R² beyond earnings surprise, on a previously examined development quarter. It is not a return, winning probability or untouched test. Prospective official outcomes are missing.” [Evaluation](../reports/archive-eval.md), [TEST](../reports/official-test-20261007.json)

### “What did AI write, and what did you write?”

“This is an AI-assisted project. Codex and Claude assisted with implementation, tests, analysis and documentation; Jordi directed scope, constraints, accounts and approvals. I do not claim that every line was written unaided or personally reviewed. I would explain the receiver, frozen outbox and evaluation by walking through their code and tests.”
There is no verified per-line authorship ledger. Do not invent percentages or claim independent mastery; demonstrate only what you can explain and reproduce.

### “Why not blend?”

“The full-quarter comparison was local ΔR² 0.040953 versus blend 0.038719; the paired comparison was 0.031059 versus 0.022574 on 25 complete rows. The blend was lower in both views. Coverage was sparse and selected, and the full-quarter result includes fallback behavior, so this is a decision about this candidate, not all AI. The optional evidence lane remains separate.” [Exact comparison and limitations](../reports/blend-probe-20261006T103757.json)

## Before presenting

- Check that both pages load and the walkthrough says **SYNTHETIC EXAMPLE · NO OFFICIAL SUBMISSION**. If unavailable, open the retained report and label it as a dated record.
- Identify the deployed revision separately from unpublished local changes. The prepared rejection logger is not proof that production rejection reasons are now recorded.
- Do not hide delivery failures, claim an official score, imply trading execution or present fixture compute latency as live end-to-end latency.
