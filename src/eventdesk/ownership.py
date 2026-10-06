"""Conservative Form 4 Table I extraction; reported transactions are not trade recommendations."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, localcontext
from typing import Annotated, Any, Literal
from xml.parsers import expat

from pydantic import BaseModel, ConfigDict, Field

from eventdesk.evidence import CapturedDocument, QuotedEvidence, RawObjects

# SOURCE: SEC Ownership 5.5 ownershipDocumentCommon.xsd.xml CIK/POSITIVE_DECIMAL definitions.
CIK = Annotated[str, Field(pattern=r"^[0-9]{1,10}$")]
ReportedDecimal = Annotated[Decimal, Field(ge=0, le=Decimal("999999999999.9999"),
                                         max_digits=16, decimal_places=4)]
# GUESS: bounded parser resource ceilings; revise after observing actual filings. # UNCALIBRATED GUESS
MAX_XML_BYTES = 16 * 1024 * 1024
MAX_XML_DEPTH = 64


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    security_title: str | None
    transaction_date: date | None
    reported_code: str | None
    acquired_disposed: Literal["A", "D"] | None
    reported_shares: ReportedDecimal | None
    reported_price_per_share: ReportedDecimal | None
    classification: str
    footnote_ids: list[str]
    evidence: QuotedEvidence
    warnings: list[str]

    @property
    def reported_price_times_shares(self) -> Decimal | None:
        if self.reported_shares is None or self.reported_price_per_share is None:
            return None
        with localcontext() as context:
            # SOURCE: exact multiplication of two SEC decimals with at most 16 significant digits each.
            context.prec = 32
            return self.reported_shares * self.reported_price_per_share


class OwnershipExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    # SOURCE: digest of retained source bytes.
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_type: Literal["4", "4/A"]
    issuer_cik: CIK
    issuer_symbol: str | None
    # SOURCE: ownership4Document.xsd.xml requires reportingOwner; allocation between joint filers is unknown.
    owner_ciks: list[CIK] = Field(min_length=1)
    # Filing-level checkbox; this does not establish the plan status of each individual transaction.
    rule_10b5_1_checkbox: bool | None
    nonderivative_transactions: list[Transaction]
    footnotes: dict[str, QuotedEvidence]
    unparsed_derivative_transactions: int
    limits: str = ("Table I only; no full XSD validation, currency/materiality, owner allocation, "
                   "tax motive inference, trading signal or calibrated probability. Acceptance comes from capture metadata.")


def one_text(root: ET.Element, path: str) -> str | None:
    elements = root.findall(path)
    if len(elements) > 1:
        raise ValueError("Ambiguous duplicated ownership field")
    if not elements:
        return None
    return (elements[0].text or "").strip() or None


def decimal_text(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    # SOURCE: XSD decimal lexical form, not locale-dependent comma separators or NaN/scientific notation.
    if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", raw) is None:
        raise ValueError("Invalid reported decimal")
    return Decimal(raw)


def lexical_spans(raw: bytes) -> dict[str, list[tuple[int, int]]]:
    """Expat offsets preserve original XML bytes, unlike a normalized ElementTree reserialization."""
    parser = expat.ParserCreate()
    stack: list[str] = []
    spans: dict[str, list[tuple[int, int]]] = {"nonDerivativeTransaction": [], "footnote": []}
    active: list[tuple[str, int, int, int, bool]] = []
    def tag_end(first: int) -> int:
        quoted: int | None = None
        for offset in range(first, len(raw)):
            char = raw[offset]
            if quoted is not None:
                if char == quoted:
                    quoted = None
            elif char in (ord("'"), ord('"')):
                quoted = char
            elif char == ord(">"):
                return offset+1
        raise ValueError("Unterminated XML opening tag")
    def reject(*args: Any) -> None:
        raise ValueError("Ownership DTD/entities are not supported")
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    def start(name: str, attributes: dict[str, str]) -> None:
        if len(stack) >= MAX_XML_DEPTH:
            raise ValueError("Ownership XML depth exceeds parser ceiling")
        if ((name == "nonDerivativeTransaction" and stack == ["ownershipDocument", "nonDerivativeTable"]) or
                (name == "footnote" and stack == ["ownershipDocument", "footnotes"])):
            first = parser.CurrentByteIndex
            opening_end = tag_end(first)
            active.append((name, first, len(stack), opening_end, raw[opening_end-2:opening_end] == b"/>"))
        stack.append(name)
    def end(name: str) -> None:
        stack.pop()
        if active and active[-1][0] == name and active[-1][2] == len(stack):
            _, first, _, opening_end, self_closing = active.pop()
            closing_start = parser.CurrentByteIndex
            # SOURCE: Expat end offset points at closing tag, or after a self-closing element.
            finish = opening_end if self_closing else raw.index(b">", closing_start)+1
            spans[name].append((first, finish))
    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.Parse(raw, True)
    return spans


def extract_form4(document: CapturedDocument, objects: RawObjects) -> OwnershipExtraction:
    document = CapturedDocument.model_validate(document.model_dump())
    if document.source != "sec":
        raise ValueError("Ownership extraction requires SEC capture provenance")
    raw = objects.read(document.content_sha256)
    if len(raw) != document.content_bytes or len(raw) > MAX_XML_BYTES:
        raise ValueError("Ownership bytes do not match capture or exceed parser ceiling")
    source_text = raw.decode("utf-8")
    # Scope is exact UTF-8 XML. Do not silently reinterpret bytes with another declared encoding.
    declaration = re.match(r"\ufeff?\s*<\?xml[^?]*\?>", source_text)
    if declaration:
        encoding = re.search(r"encoding\s*=\s*['\"]([^'\"]+)['\"]", declaration.group())
        if encoding and encoding.group(1).lower() not in ("utf-8", "utf8"):
            raise ValueError("Only UTF-8 ownership extraction is supported")
    # Parse before ElementTree: DTD/entity declarations never reach a text-expanding parser.
    spans = lexical_spans(raw)
    root = ET.fromstring(raw)
    kind = one_text(root, "documentType")
    if root.tag != "ownershipDocument" or kind not in ("4", "4/A"):
        raise ValueError("Only unnamespaced Form 4/4-A XML is supported")
    if document.form is not None and document.form != kind:
        raise ValueError("Captured form conflicts with ownership XML")
    text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    def quote(span: tuple[int, int]) -> QuotedEvidence:
        start, end = (len(raw[:offset].decode("utf-8")) for offset in span)
        evidence = QuotedEvidence(document_sha256=document.content_sha256, text_sha256=text_hash,
            start=start, end=end, quote=source_text[start:end])
        evidence.verify(document, source_text, objects)
        return evidence
    footnotes = {}
    elements = root.findall("footnotes/footnote")
    if len(elements) != len(spans["footnote"]):
        raise ValueError("Footnote lexical provenance mismatch")
    for element, span in zip(elements, spans["footnote"], strict=True):
        identity = element.get("id")
        if not identity or identity in footnotes:
            raise ValueError("Missing/duplicated footnote identity")
        footnotes[identity] = quote(span)
    checkbox_raw = one_text(root, "aff10b5One")
    # SOURCE: XML Schema boolean values; a missing historic checkbox remains unknown, not false.
    if checkbox_raw not in (None, "0", "1", "true", "false"):
        raise ValueError("Invalid Rule 10b5-1 checkbox")
    checkbox = checkbox_raw in ("1", "true") if checkbox_raw is not None else None
    elements = root.findall("nonDerivativeTable/nonDerivativeTransaction")
    if len(elements) != len(spans["nonDerivativeTransaction"]):
        raise ValueError("Transaction lexical provenance mismatch")
    transactions = []
    # SOURCE: Ownership 5.5 PDF section 3.6.10; P/S include PRIVATE as well as open-market transactions.
    classifications = {"P": "purchase_open_or_private", "S": "sale_open_or_private",
        "A": "award_or_other_rule_16b3_acquisition", "F": "exercise_price_or_tax_payment"}
    for element, span in zip(elements, spans["nonDerivativeTransaction"], strict=True):
        code = one_text(element, "transactionCoding/transactionCode")
        direction = one_text(element, "transactionAmounts/transactionAcquiredDisposedCode/value")
        references = list(dict.fromkeys(item.get("id") for item in element.iter("footnoteId")))
        if any(identity is None or identity not in footnotes for identity in references):
            raise ValueError("Unresolved transaction footnote")
        warnings = []
        if code not in classifications:
            warnings.append("no_specific_local_rationale")
        if (code == "P" and direction == "D") or (code == "S" and direction == "A"):
            warnings.append("code_direction_conflict")
        shares = decimal_text(one_text(element, "transactionAmounts/transactionShares/value"))
        price = decimal_text(one_text(element, "transactionAmounts/transactionPricePerShare/value"))
        if shares is None:
            warnings.append("shares_not_reported_as_numeric")
        if price is None:
            warnings.append("price_not_reported_as_numeric")
        transactions.append(Transaction.model_validate({"security_title": one_text(element, "securityTitle/value"),
            "transaction_date": one_text(element, "transactionDate/value"), "reported_code": code,
            "acquired_disposed": direction, "reported_shares": shares, "reported_price_per_share": price,
            "classification": classifications.get(code or "", "other_or_unknown_reported_transaction"),
            "footnote_ids": references, "evidence": quote(span), "warnings": warnings}))
    return OwnershipExtraction.model_validate({"document_sha256": document.content_sha256, "document_type": kind,
        "issuer_cik": one_text(root, "issuer/issuerCik"), "issuer_symbol": one_text(root, "issuer/issuerTradingSymbol"),
        "owner_ciks": list(dict.fromkeys(one_text(owner, "reportingOwnerId/rptOwnerCik") for owner in root.findall("reportingOwner"))),
        "rule_10b5_1_checkbox": checkbox, "nonderivative_transactions": transactions, "footnotes": footnotes,
        "unparsed_derivative_transactions": len(root.findall("derivativeTable/derivativeTransaction"))})
