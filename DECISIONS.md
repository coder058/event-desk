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
