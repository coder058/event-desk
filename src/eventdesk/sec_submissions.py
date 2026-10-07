"""Typed discovery from retained SEC submissions JSON, without timezone guessing.

This is metadata discovery, not extraction of filing contents or complete EDGAR
coverage. Filing dates are not acceptance timestamps. Unknown/naive acceptance
times remain ineligible for point-in-time features.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from eventdesk.evidence import CapturedDocument, RawObjects

# SOURCE: SEC submissions endpoint requires a ten-digit zero-padded CIK.
CIK_WIDTH = 10
# GUESS: resource ceiling for a single submissions response; not a measured typical size. # UNCALIBRATED GUESS
MAX_SUBMISSIONS_BYTES = 16 * 1024 * 1024
# SOURCE: mission scope, including amendments and historical/current SEC naming variants.
SUPPORTED_FORMS = frozenset({"8-K", "8-K/A", "4", "4/A", "SC 13D", "SC 13D/A",
                             "SCHEDULE 13D", "SCHEDULE 13D/A"})


class FilingReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cik: str = Field(pattern=r"^[0-9]{10}$")
    accession: str = Field(pattern=r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
    form: str
    filing_date: date
    primary_document: str
    source_url: str
    accepted_at: datetime | None
    acceptance_status: Literal["explicit_timezone", "missing", "unknown_timezone"]
    discovered_at: datetime
    submissions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def verify_boundary(self) -> FilingReference:
        if self.discovered_at.tzinfo is None or (self.accepted_at is not None and self.accepted_at.tzinfo is None):
            raise ValueError("Discovery/acceptance must be timezone-aware")
        if self.accepted_at is not None and self.accepted_at > self.discovered_at:
            raise ValueError("Acceptance cannot follow captured discovery")
        if (self.accepted_at is None) != (self.acceptance_status != "explicit_timezone"):
            raise ValueError("Acceptance status disagrees with timestamp")
        if self.source_url != primary_url(self.cik, self.accession, self.primary_document):
            raise ValueError("Filing URL disagrees with retained identity")
        if self.form not in SUPPORTED_FORMS:
            raise ValueError("Filing outside declared discovery scope")
        return self

    def discovered_before(self, cutoff: datetime) -> bool:
        if cutoff.tzinfo is None:
            raise ValueError("Cutoff requires timezone")
        return self.accepted_at is not None and self.accepted_at <= cutoff and self.discovered_at <= cutoff


class SubmissionDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cik: str
    submissions_sha256: str
    references: tuple[FilingReference, ...]
    additional_history_files: tuple[str, ...]
    limits: str = ("Recent submissions metadata only; no complete-market/history coverage, filing-body "
                   "extraction or trading signal. Discovery does not establish when exact filing bytes were available.")


def normalize_cik(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("CIK must be a numeric identifier")
    digits = str(value)
    if not re.fullmatch(r"[0-9]{1,10}", digits) or int(digits) == 0:
        raise ValueError("CIK outside SEC identifier shape")
    return digits.zfill(CIK_WIDTH)


def primary_url(cik: str, accession: str, primary_document: str) -> str:
    cik = normalize_cik(cik)
    if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
        raise ValueError("Invalid accession identity")
    # SOURCE: only explicit relative ASCII filenames/directories, never encoded traversal or another origin.
    if (not primary_document or not re.fullmatch(r"[A-Za-z0-9_./-]+", primary_document)
            or any(part in ("", ".", "..") for part in primary_document.split("/"))):
        raise ValueError("Unsafe primary document path")
    return "https://www.sec.gov/Archives/edgar/data/"+str(int(cik))+"/"+accession.replace("-", "")+"/"+primary_document


def acceptance_time(value: Any) -> tuple[datetime | None, Literal["explicit_timezone", "missing", "unknown_timezone"]]:
    if value is None or value == "":
        return None, "missing"
    if not isinstance(value, str):
        raise ValueError("Acceptance timestamp must be text")
    # SOURCE: only explicit ISO offsets/Z are unambiguous; no guessed EST/DST or date-only conversion.
    if "T" not in value or re.search(r"(?:Z|[+-][0-9]{2}:[0-9]{2})$", value) is None:
        return None, "unknown_timezone"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Acceptance timestamp has no timezone")
    return parsed, "explicit_timezone"


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Ambiguous duplicate submissions JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError("Nonfinite submissions JSON constant")


def discover_submissions(document: CapturedDocument, objects: RawObjects) -> SubmissionDiscovery:
    raw = objects.read(document.content_sha256)
    if document.source != "sec" or len(raw) != document.content_bytes or len(raw) > MAX_SUBMISSIONS_BYTES:
        raise ValueError("Expected bounded retained SEC submissions")
    match = re.fullmatch(r"https://data\.sec\.gov/submissions/CIK([0-9]{10})\.json", document.source_url)
    if match is None:
        raise ValueError("Expected SEC submissions endpoint")
    body = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(body, dict) or normalize_cik(body.get("cik")) != match.group(1):
        raise ValueError("Submissions CIK disagrees with requested identity")
    filings = body.get("filings")
    if not isinstance(filings, dict) or not isinstance(filings.get("recent"), dict):
        raise ValueError("Recent submissions missing")
    recent = filings["recent"]
    required = ("accessionNumber", "form", "filingDate", "primaryDocument")
    if any(not isinstance(recent.get(name), list) for name in required):
        raise ValueError("Expected columnar recent submissions")
    count = len(recent["accessionNumber"])
    if any(len(recent[name]) != count for name in required):
        raise ValueError("Submissions columns are misaligned")
    acceptance = recent.get("acceptanceDateTime", [None]*count)
    if not isinstance(acceptance, list) or len(acceptance) != count:
        raise ValueError("Acceptance column is misaligned")
    references: dict[str, FilingReference] = {}
    for index in range(count):
        form = recent["form"][index]
        if not isinstance(form, str):
            raise ValueError("Filing form must be text")
        if form not in SUPPORTED_FORMS:
            continue
        accepted, status = acceptance_time(acceptance[index])
        accession, primary = recent["accessionNumber"][index], recent["primaryDocument"][index]
        if not isinstance(accession, str) or not isinstance(primary, str):
            raise ValueError("Filing identity must be text")
        filed = recent["filingDate"][index]
        if not isinstance(filed, str):
            raise ValueError("Filing date must be text")
        reference = FilingReference(cik=match.group(1), accession=accession, form=form,
            filing_date=date.fromisoformat(filed), primary_document=primary,
            source_url=primary_url(match.group(1), accession, primary), accepted_at=accepted,
            acceptance_status=status, discovered_at=document.first_seen_at, submissions_sha256=document.content_sha256)
        if accession in references and references[accession] != reference:
            raise ValueError("Conflicting duplicate accession")
        references[accession] = reference
    history = filings.get("files", [])
    if not isinstance(history, list):
        raise ValueError("Additional history metadata must be a list")
    names = []
    for record in history:
        name = record.get("name") if isinstance(record, dict) else None
        if not isinstance(name, str) or re.fullmatch(r"CIK"+match.group(1)+r"-submissions-[0-9]+\.json", name) is None:
            raise ValueError("Unexpected additional history filename")
        names.append(name)
    return SubmissionDiscovery(cik=match.group(1), submissions_sha256=document.content_sha256,
        references=tuple(references[key] for key in sorted(references)), additional_history_files=tuple(names))
