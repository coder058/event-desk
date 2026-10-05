# Decisions

## 2026-10-05 — rules control the input boundary

Official rules allow materials delivered for the event by the competition API
even when delivered after knowledge_cutoff. External information remains strictly
pre-cutoff. This binding exception overrides the mission's blanket rejection.
Source: https://explainingmarkets.ai/contest-rules, information restrictions.

## 2026-10-05 — durable ACK

ACK only after the event and work item are committed in PostgreSQL. FastAPI
BackgroundTasks alone cannot survive process failure and are not the queue.
Preserve first receipt/deadline across duplicates, including different delivery IDs.

## 2026-10-05 — scorer and calibration

Use the official version linked by the rules (501bd31), with source hash recorded.
Delta R-squared is not win probability or investment return. It is invariant to
affine transformations of the regressor; arbitrary rank-preserving transformations
are not generally equivalent. Do not normalize predictions using future live events.

## 2026-10-05 — zero new spend

Existing VPS and free Gemini/Groq only. No paid-model fallback. Train a local
model from closed archive quarters before enabling competition predictions.
Without a fitted blend, report LLM evidence separately and retain local predictions.

## 2026-10-05 — optional evidence cannot block coverage

Until a hybrid is approved, local predictions are frozen and submitted before
the optional structured-LLM analysis. That analysis uses the same retained official
inputs in a separate durable queue; its trace explicitly says it did not affect
the percentile. Restart recovery preserves that distinction. It is not a
retrospective explanation of why the local regression produced its value.
An approved inline hybrid still needs a fault/load review before activation.

## 2026-10-05 — reserve survives material-source outages

The fifteen-second official-starter timeout is a maximum, not permission to consume
the final submission reserve. Bound DNS and body reads by the remaining event budget
minus the mission's thirty seconds. Late queued events use the fitted target mean
and retain `materials_skipped_deadline_reserve`; an outage can therefore dilute
the score even when predictions arrive. Broker/provider outages still prevent any
guarantee of future coverage. Expired backlog cannot hold up newer valid work.

Cache only static fitted explanation metadata and operate on nonzero sparse terms.
Prediction and feature code stay frozen. Record the paired measurement and numerical
differences; this improves evidence rendering, not model accuracy or a trading edge.
