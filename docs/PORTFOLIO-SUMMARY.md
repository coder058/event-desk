# Event Desk

A signed-webhook prediction service for the Optiver × Chicago Booth Explaining Markets competition.
It turns supplied earnings facts into a frozen forecast and retains enough evidence to audit delivery, calculation and submission separately. It does not trade.

## The problem

A forecast is useful only if the service receives the right event, respects its information cutoff, submits on time and can explain what survived a retry. Fluent AI text alone does not establish predictive value.

## Architecture: five boxes

```text
[Signed webhook] → [PostgreSQL inbox] → [Trained local model] → [Immutable outbox] → [Official API acknowledgement]
```

The receiver checks the original signed bytes before retaining them. The facts-only model uses TF-IDF text features and fitted ridge regression to predict a market-reaction percentile. Optional language-model evidence runs separately after submission; it cannot revise the frozen forecast.

## Three decisions and their reasons

- **Commit before acknowledging delivery.** PostgreSQL retains the event before success is returned. Duplicate and conflicting deliveries have explicit outcomes; an uncertain commit is not reported as success.
- **Freeze before sending.** Retain the prediction, input/model hashes and payload before the external POST. An uncertain network result reuses that outbox instead of producing a new answer.
- **Keep generative evidence outside the forecast.** Exact quotations and provider provenance make the evidence inspectable, but the measured blend was worse than the local baseline. The blend stays disabled.

## What was measured

| Measurement | Result | Exact scope and source |
| --- | --- | --- |
| Full-quarter development ΔR² | Local **0.040953**; blend **0.038719** | **2,275** surprise-complete historical rows; missing AI outputs fall back to local in the blend. [Blend report](../reports/blend-probe-20261006T103757.json), [baseline evaluation](../reports/archive-eval.md) |
| Paired development ΔR² | Local **0.031059**; blend **0.022574** | Only **25** surprise-complete rows with both outputs. Small, selected successful-output cohort. [Blend report](../reports/blend-probe-20261006T103757.json) |
| Warm single-event inference | p50 **1.946 ms**; p95 **2.269 ms** | **2,362** archived inputs on Dublin; excludes model cold load, network, durable ACK and submission. [Inference report](../reports/dublin-inference.json) |
| Paired explanation experiment | Baseline p50/p95 **100.345/175.565 ms**; candidate **2.735/4.195 ms** | **400** archived inputs, alternating order on the same host/process; calculation only, without HTTP, database or capacity measurement. [Comparison report](../reports/explanation-comparison.json) |

ΔR² measures incremental explanatory power beyond earnings surprise, not winning probability or trading profit. The validation quarter had already been inspected: it is development evidence, not an untouched test. The sparse AI comparison does not establish a general conclusion about language models.

## Verified operation and remaining limits

- **One** genuine official TEST was accepted, with a neutral **0.5** prediction and HTTP **201**. It verifies connectivity, not trained inference or scoring. The same observation had **zero** non-TEST submissions. [Official TEST receipt](../reports/official-test-20261007.json)
- An initial snapshot found **three** webhook deliveries classified as 4xx; a later retained official observation had **15** consecutive failures. Their exact code and cause were not retained. A redacted rejection-log proposal is prepared locally and awaits owner approval to publish/deploy. [Initial snapshot](../reports/delivery-failures-readonly-20261008.json), [follow-up snapshot](../reports/delivery-failures-followup-readonly-20261008.json), [incident analysis](INCIDENT-2026-10-08-delivery-4xx.md)
- Standard HTTPS is externally reachable; a signed portal TEST through that route is still pending. A local real-proxy fixture preserves signed bytes on both paths; it does not verify public delivery. [HTTPS evidence](../reports/https443-20261008.json), [proxy fixture](../reports/two-proxy-bytes-20261008.json)
- Off-host alerts have not been connected. The new nightly encrypted backup matches on both hosts, but its restoration is unverified. [Operational audit](../reports/scoring-readiness-readonly-20261008.json), [nightly check](../reports/nightly-backup-readonly-20261008.json)
- Prospective scored outcomes are still needed. No live predictive advantage, competition result or tradable edge is established.

[Live dashboard](https://52.17.192.36.sslip.io/) · [Synthetic walkthrough](https://52.17.192.36.sslip.io/walkthrough) · [Engineering case study](CASE-STUDY.md)
