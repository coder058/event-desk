# Source evidence foundation — not daily EDGAR ingestion

`RawObjects` captures immutable content-addressed bytes. Identical concurrent
writes deduplicate without replacing an object; reads verify the hash. Private
temporary files are fsynced before atomic creation; POSIX directory metadata is
also fsynced. Objects must live under a trusted private root. This does not claim
an adversarial multi-user filesystem or full-host recovery guarantee.

`CapturedDocument` distinguishes official acceptance from first observed capture.
Timezone-free values, future acceptance relative to capture, and unapproved source
hosts are rejected. Conservative pre-cutoff use requires both times before the
cutoff; an old URL fetched later is not proof of its earlier bytes. Unknown
acceptance remains unavailable, not a guessed time at midnight.

`QuotedEvidence` checks exact character offsets/text hashes and rereads retained
bytes. A fabricated unrelated text with a plausible quote/hash cannot be attached
to another document. Initial quote scope is exact UTF-8 raw text, including HTML
markup if present. Initial Table I XML extraction is described in
[ownership extraction](OWNERSHIP-EXTRACTION.md). HTML normalization, PDF conversion,
batch LLM extraction and daily collector are still to build. Unsupported encodings
must remain raw-only, not be silently reinterpreted.

`Sources.commit_batch` verifies every referenced blob before one transaction
appends metadata/batch hashes and advances the cursor. Compare-and-swap refuses
stale writers; a retry of a committed batch cannot rewind a newer cursor. A later
failure rolls back all metadata, leaving only harmless unreferenced raw objects.
Cutoff reads recheck metadata hashes, timestamps and actual raw bytes. Initial
SQLite tests cover retries, missing/corrupt bytes, rollback, cutoff filtering and
concurrent calls. CI includes actual PostgreSQL duplicate/cross-feed races.
The source tables are additive migrations, not a running daily ingestion service.

No SEC HTTP request or real filing is claimed by the synthetic boundary tests.
The configured SEC identity is still missing; see BLOCKED.md. Future network work
must follow [SEC fair access](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
and the [official submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
All of this is independent from the declared competition prediction function.
