# Event Desk — current submission method

## Current deployed method

Traditional machine learning: TF-IDF of the official earnings-call facts,
unigram/bigram features and ridge regression. Training targets are official
within-quarter percentile ranks of one-day abnormal returns from closed archive
quarters 2025Q4–2026Q2. Predictions are clipped to the API's [0,1] interval.
No future live-event batch ranks are used. Missing materials use the fitted
training-target mean. TEST events use the official neutral test prediction.

The prediction itself does not use a generative model or LLM blend. The production
configuration now enables Gemini/Groq only in a separate post-submission evidence
lane, under shared quotas. Deployment/heartbeat verified this flag on October 7,
with hybrid disabled and unchanged model/configuration hashes. An actual accepted
competition event is still required to claim live event evidence. An isolated
fictional-input smoke produced validated Groq evidence after Gemini returned 503;
its competition API was mocked, not a real delivery or submission.
One genuine official TEST was accepted on October 7 at 22:03 UTC. It uses the
neutral 0.5 rule and does not exercise trained inference or generative evidence;
no non-TEST production event or live generative evidence is claimed.
Those quotations and sub-scores cannot change the predicted percentile or serve as
retrospective reasoning for the local regression. A fixed Groq blend was
actually fitted on 42 Q2 events and validated on 28 Q3 events (25 surprise-complete
scorer rows). Its full imputed ΔR² was 0.03871855275695035 versus the local model's
0.04095315077531125, and its paired score was also lower. It remains unapproved;
these small cohorts do not establish a generative advantage. Exact hashes,
coverage policies and limits are in reports/archive-eval.md. This description
must change before another method actually affects production predictions.

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
