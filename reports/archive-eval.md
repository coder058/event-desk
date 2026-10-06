# Closed-archive evaluation

Selected: **facts_baseline**.

| Candidate | Train rows | Q3 rows | Imputed ΔR² |
|---|---:|---:|---:|
| facts_baseline | 6299 | 2362 | 0.04095315077531125 |
| enriched | 6299 | 2362 | 0.022485843848399356 |

Runtime single-event local predictions matched batch predictions. Scorer and data
hashes are recorded in archive-eval.json.

## Structured AI comparison — October 6

Fixed exploratory ridge mappings were fitted on 42 Q2 events with validated Groq
`openai/gpt-oss-120b` sub-scores. Q2 local inputs came from the separate Q4/Q1-only
artifact. Validation used 28 Q3 events with validated responses and the deployed
through-Q2 local artifact. The official scorer excluded three of those events
without a numeric surprise, leaving 25 common rows. No validation sweep occurred.

| Method | Full Q3 imputed ΔR² (2,275 common rows) | Same available AI cohort ΔR² (25 rows) |
|---|---:|---:|
| Local only | 0.04095315077531125 | 0.03105931416757035 |
| AI sub-scores only | 0.000300660765378602 | 0.02122287058811967 |
| Fitted blend, local when AI absent | 0.03871855275695035 | 0.022573707453389602 |

**Decision: do not deploy this blend.** It scored lower than local on both views.
AI-only missing outputs are mean-imputed by the official scorer; the blend uses
local on the remaining events. These are different coverage policies, so the
full score is not an isolated measurement of reasoning quality.

The training feature matrix had rank six for seven columns: `surprise_vs_preview`
was constant and its fitted coefficient was zero. Cohorts span April 1–14 and
July 1–14, not representative full quarters. Successful-output sampling, API
failures and the small sample limit inference. Leave-one-event-out values in
the report measure sensitivity, not confidence intervals or win probabilities.
The private exploratory artifact has `deployment_approved=false` and cannot
start as a production blend. Source/archive/prompt/evidence hashes and exact
results: [retained probe](blend-probe-20261006T103757.json).

## Limits

- Q3 is development validation after previous research inspection, not untouched test
- The AI comparison is small, chronological development evidence; no generative advantage established
- No live competition or trading performance
