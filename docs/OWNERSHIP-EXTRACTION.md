# Initial Form 4 extraction boundary

The parser handles original UTF-8 primary XML for Form 4 / 4-A, with
non-derivative Table I transactions and referenced footnotes. It rereads and
hash-verifies captured source bytes. Quotes are exact raw XML spans with character
offsets, not ElementTree's rewritten representation. Unicode, comments, entities
and self-closing footnotes have specific provenance tests.

## Primary specification actually inspected

[SEC Technical Specifications](https://www.sec.gov/submit-filings/technical-specifications)
links Ownership 5.5 dated March 18, 2026. The ZIP was downloaded through the normal
browser documentation link, not through an unidentified automated EDGAR scraper.
ZIP SHA-256: `4c1e9fb1f2c4a8a4e3d6c70cb93b6d77130dcf0a9e588841e5797507db33c3e7`.
PDF SHA-256: `0e403c330042b210450383abaf9c0bf661f0a5bcac654bfa4ce4572ef20fb86c`.
The PDF's section 3.6.10 (printed pages 3-16/3-17) and the actual reduced-content
XSD files were inspected. The official sample is a schema example, not an observed
filing. Full specs: [Ownership 5.5 ZIP](https://www.sec.gov/files/edgar/filer-information/specifications/ownershipxmltechspec-v5-5.zip).

## Interpretations and omissions

- `P`/`S` include private purchases/sales; neither means exclusively open market.
- `F` can be exercise-price payment **or** tax liability. A specific tax rationale
  needs additional verified evidence. `A` is an award/other Rule 16b-3 acquisition.
- `aff10b5One` is a filing-level checkbox. Missing historical values stay unknown;
  a checked filing does not allocate plan status to every transaction.
- Multiple reporting owners are retained as identifiers; transactions are counted
  once. Individual allocation and issuer-level insider clusters are not inferred.
- Footnote-only price is unknown, not zero. Multiplication uses exact Decimal
  arithmetic; currency, market cap and relative materiality remain unverified.
- Derivative rows are counted as unparsed, not silently interpreted as common
  stock purchases. Unsupported forms, namespaces and non-UTF-8 XML are explicit.
- DTDs/entities and ambiguous duplicate fields are rejected. Resource limits are
  operational guesses. This is **not full XSD validation** or a trading strategy.

The extractor cannot establish acceptance time from a transaction date or
period-of-report. That time must come from separately verified capture metadata.
Only captures passing both acceptance and first-seen cutoff checks may become
competition features. No deployed forecast currently imports these features.
Daily SEC ingestion, live filing replay, LLM extraction, materiality/cluster
analysis and a prospective event study are still incomplete. No edge is claimed.
