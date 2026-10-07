# SEC evidence boundaries and current status

The engine does not yet collect EDGAR daily. No real filings or prospective
returns have been processed. An actual administrative contact in SEC_USER_AGENT
is still required before external automated reads; see BLOCKED.md.

## Implemented, with synthetic verification

- Hash-addressed exact source bytes, aware acceptance/first-seen metadata,
  append-only batches and atomic checkpoint comparison/advance.
- Conservative Form 4 Table I extraction with exact source-span quotes. Owner
  allocation, derivatives, motives, materiality and win probabilities are unknown.
- Recent submissions JSON discovery for 8-K, Form 4 and Schedule 13D variants.
  It checks requested CIK, aligned arrays, accession identity, relative primary
  paths, duplicate keys and additional-history filenames.
- Only an explicit ISO timezone/Z produces an acceptance timestamp. A filing
  date, naive timestamp or unavailable timestamp does not become a pre-cutoff
  feature. Acceptance after capture is rejected.

Discovery retains a source hash and first-seen time. It does not prove when the
exact filing-body bytes were available; the body must be captured separately.
Additional history is listed, not claimed downloaded. Recent-company metadata is
not all-market coverage. Primary XML stylesheet paths are preserved exactly;
no guessed rewrite is presented as a verified raw document.

## Next engineering steps

1. Identified, bounded HTTP transport and one shared project pacing/cooldown gate.
2. Explicit universe/feed coverage and failures; no silent checkpoint over failed
   discovery or filing reads. Capture raw documents before committing provenance.
3. Persist extractor version and typed output with verified evidence joins.
4. Freeze the prospective event cohort before outcomes; sector-adjusted 1/5/20
   trading-day study, placebo and uncertainty. Unmatured/unsupported outcomes stay
   missing. No pre-cutoff competition features until a separate validated version.

Sources: [SEC submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
and [fair-access policy](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
The SEC's ceiling is ten requests per second, not a throughput target or guarantee.
