# Event Desk — current submission method

## Current deployed method

Traditional machine learning: TF-IDF of the official earnings-call facts,
unigram/bigram features and ridge regression. Training targets are official
within-quarter percentile ranks of one-day abnormal returns from closed archive
quarters 2025Q4–2026Q2. Predictions are clipped to the API's [0,1] interval.
No future live-event batch ranks are used. Missing materials use the fitted
training-target mean. TEST events use the official neutral test prediction.

The current deployed version does not use a generative model or LLM blend.
Gemini/Groq evidence and a fitted hybrid version are under development; this
description must be updated when those methods actually affect predictions.

## Evaluation

The facts model's 2026Q3 development-validation imputed delta R-squared is
0.04095315077531125, computed with the scorer incorporated by the rules.
All 2,362 scored asset outcomes were predicted, of which 2,275 carried a numeric
surprise and entered the common regression sample. Q3 had been examined during
prior research; it is not an untouched test. Its official manifest is not sealed.

Preview/options/missingness were tested as a fixed enriched candidate and scored
lower on that same validation set, so they are not in the initial local model.

## Information boundary

Only materials delivered through the official competition API enter the current
model. Binding rules permit those materials after knowledge_cutoff; external
post-cutoff information is prohibited. Outcome, earnings-surprise metric and
baseline prediction blocks never enter the feature builder.

## Operational provenance and limits

Source/scorer/data/model hashes are retained with predictions and reports.
The initial configuration is declared in PREREGISTRATION.md and checked before
production model deserialization/startup. New immutable predictions retain its
configuration hash; earlier rows are not rewritten when versions change.
Receipt, immutable outbox and result are stored in PostgreSQL before success
is claimed. API acceptance is separate from score eligibility.

No live score, ten-day coverage record, win probability, investment return,
LLM advantage or profit is claimed. Single-VPS failure and unavailable materials
can degrade coverage or information quality.
