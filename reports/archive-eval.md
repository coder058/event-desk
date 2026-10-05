# Closed-archive evaluation

Selected: **facts_baseline**.

| Candidate | Train rows | Q3 rows | Imputed ΔR² |
|---|---:|---:|---:|
| facts_baseline | 6299 | 2362 | 0.04095315077531125 |
| enriched | 6299 | 2362 | 0.022485843848399356 |

LLM and blend: not evaluated. Runtime single-event predictions matched batch predictions.
Scorer and data hashes are recorded in archive-eval.json.

## Limits

- Q3 is development validation after previous research inspection, not untouched test
- LLM and fitted blend not evaluated yet
- No live competition or trading performance
