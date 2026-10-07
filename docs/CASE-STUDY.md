# Event Desk: from an event to an accountable forecast

**The task:** predict the relative stock-market reaction to earnings disclosures,
then have an independent competition score the predictions. This is prediction
research and operational engineering; the current service does not place trades.

[Live service](https://52.17.192.36.sslip.io:80/) ·
[Follow a fictional event through the actual code](https://52.17.192.36.sslip.io:80/walkthrough) ·
[Source](https://github.com/coder058/event-desk)

## One event, six steps

| Step | Actual mechanism | Evidence / failure boundary |
| --- | --- | --- |
| Receive | HMAC over original bytes; unique delivery identity | Altered bytes fail; conflicting signed content cannot overwrite a receipt |
| Retain | PostgreSQL inbox commit before ACK | An uncertain commit returns 503; the sender can retry safely |
| Read | Official facts/preview/options selected by item ID | Other blocks and outcome labels never become features |
| Predict | Facts-only TF-IDF + fitted ridge regression | Invalid/missing text uses the fitted training mean |
| Persist/send | Immutable prediction outbox, bounded POST | Uncertain network result retries that same value; 201 is not score eligibility |
| Explain | Numeric feature contributions; separately labelled LLM evidence | Neither feature weights nor model confidence are causal proof or trade probabilities |

The demonstration uses fictional text and a disposable SQLite database. It runs
the actual signed receiver and worker, including duplicate/modified/conflicting
delivery checks. Its forecast is computed by the archive-trained model, not typed
into HTML. No competition POST or production ledger insertion occurs. Separate
PostgreSQL fixtures verify concurrent durability. The demo is not a live result.

## What I tested, and what failed

### Establish a measurable local baseline

The inherited text pipeline was reproduced with the official scorer. Training
used closed quarters through Q2; Q3 is development validation, already inspected
in earlier research, so it is not an untouched test.

| Historical candidate | Q3 imputed ΔR² | Decision |
| --- | --- | --- |
| Facts-only model | 0.04095315077531125 | Current baseline |
| Added preview/options/missingness features | 0.022485843848399356 | Not selected |

These values measure incremental explanatory power beyond earnings surprise,
not returns, percentage accuracy or probability of winning the competition.
[Evaluation and provenance](../reports/archive-eval.md).

### Make the language-model layer testable

Gemini/Groq return five bounded sub-scores and quotations from supplied text.
Validation rejects invented source quotations. Research and runtime use a shared
PostgreSQL quota ledger; external provider limits still override local admission.

The first fixed fitted blend scored **0.03871855275695035**, below local-only
**0.04095315077531125**. Only 25 surprise-complete Q3 rows had paired AI outputs;
the full-quarter score also reflects missing-output policy. That small, selected
cohort does not establish general superiority. The blend remains unapproved.
[Exact failed experiment and limits](../reports/blend-probe-20261006T103757.json).

The post-submission evidence lane was enabled and its production heartbeat
verified on October 7; hybrid remains disabled. It cannot revise the local
prediction. A slow-AI dispatcher test verifies that predictions can complete
while that lane is blocked. A separate fictional-input smoke made two actual
free-provider requests: Gemini returned 503, Groq produced validated sub-scores
and a matching quote. The local forecast was unchanged. Its competition API was
mocked and its event book disposable; no official delivery is claimed.
[Exact provider smoke](../reports/shadow-provider-smoke.json).

### Define latency before reporting it

The Dublin trained-model fixture received 400 events and produced 400 simulated
results in 10.626 seconds; maximum ACK was 1.249 seconds. It used archived inputs
and real HTTP/PostgreSQL, without official submissions or measured accuracy.
[Retained replay](../reports/dublin-trained-fixture-load-2e8792f.json).

Local inference, signed receipt, public TLS and official API response are distinct
intervals. A fast model calculation does not establish live end-to-end latency.

## Operation and recovery

The existing Dublin VPS hosts the API, worker, observer and PostgreSQL. HTTPS was
externally verified on explicit TLS port 80; standard 443 remains unreachable.
An independent monitor observes service/deadline health. Encrypted backups go to
the existing Frankfurt host; an isolated restore verifies exact archive hashes
without overwriting production. [Restore receipt](../reports/backup-restore.json).

Four read-only MCP tools expose retained public records. They cannot submit
predictions or place orders. [Connection and actual verification](MCP.md).

## Reproduce and inspect

Run the keyless application with `docker compose up --build` (see the root README).
To generate the walkthrough with your own trusted model artifact:
`PYTHONPATH=src python fixtures/build_walkthrough.py --model PATH`.
Tests cover the receiver, immutable decisions, source boundaries and demo isolation;
CI also exercises actual PostgreSQL concurrency. [CI](https://github.com/coder058/event-desk/actions).

## What remains unproven

As of the October 7 verification: no official portal test, live scored observation
or ten-day eligible coverage record. Daily SEC ingestion, prospective event studies
and an event-driven paper portfolio are unfinished. No generative improvement,
durable trading edge, profitability or recruitment outcome is established.
