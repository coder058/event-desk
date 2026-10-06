from datetime import UTC, datetime
from decimal import Decimal

import pytest

from eventdesk.evidence import CapturedDocument, RawObjects
from eventdesk.ownership import extract_form4


def transaction(code="P", direction="A", price="12.3456"):
    # PLACEHOLDER: synthetic data in schema-verified SEC element paths, not an actual insider event.
    return f'''<nonDerivativeTransaction><securityTitle><value>Préferred &amp; common</value></securityTitle>
    <transactionDate><value>2026-10-12</value></transactionDate>
    <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>10</value></transactionShares>
    <transactionPricePerShare>{"<value>"+price+"</value>" if price else '<footnoteId id="F1"/>'}</transactionPricePerShare>
    <transactionAcquiredDisposedCode><value>{direction}</value></transactionAcquiredDisposedCode></transactionAmounts>
    <footnoteId id="F1"/></nonDerivativeTransaction>'''


def fixture(rows, checkbox="<aff10b5One>true</aff10b5One>", footnote='<footnote id="F1">Synthetic plan disclosure</footnote>'):
    return f'''<?xml version="1.0" encoding="UTF-8"?><ownershipDocument>
    <documentType>4</documentType><issuer><issuerCik>123</issuerCik><issuerTradingSymbol>FIXTURE</issuerTradingSymbol></issuer>
    <reportingOwner><reportingOwnerId><rptOwnerCik>456</rptOwnerCik></reportingOwnerId></reportingOwner>
    <reportingOwner><reportingOwnerId><rptOwnerCik>789</rptOwnerCik></reportingOwnerId></reportingOwner>{checkbox}
    <!-- A comment is not an event: <nonDerivativeTransaction>fake</nonDerivativeTransaction> -->
    <nonDerivativeTable>{rows}</nonDerivativeTable><footnotes>{footnote}</footnotes>
    <derivativeTable><derivativeTransaction/></derivativeTable></ownershipDocument>'''.encode()


def retained(raw, tmp_path):
    objects = RawObjects(tmp_path/"objects")
    document = CapturedDocument(source="sec", source_url="https://www.sec.gov/Archives/edgar/fixture.xml",
        content_sha256=objects.put(raw), content_bytes=len(raw), form="4", accepted_at=None,
        first_seen_at=datetime.now(UTC))
    return document, objects


def test_codes_and_joint_owners_never_multiply_positions_or_invent_rationale(tmp_path):
    raw = fixture(transaction()+transaction("S", "D")+transaction("F", "D")+transaction("A", "A"))
    document, objects = retained(raw, tmp_path)
    parsed = extract_form4(document, objects)
    assert parsed.owner_ciks == ["456", "789"]
    assert len(parsed.nonderivative_transactions) == 4
    assert [row.classification for row in parsed.nonderivative_transactions] == [
        "purchase_open_or_private", "sale_open_or_private", "exercise_price_or_tax_payment",
        "award_or_other_rule_16b3_acquisition"]
    assert parsed.rule_10b5_1_checkbox is True
    assert parsed.unparsed_derivative_transactions == 1
    for row in parsed.nonderivative_transactions:
        assert row.reported_price_times_shares == Decimal("123.4560")
        assert row.security_title == "Préferred & common"
        row.evidence.verify(document, raw.decode(), objects)
    parsed.footnotes["F1"].verify(document, raw.decode(), objects)
    assert "currency/materiality" in parsed.limits


def test_missing_checkbox_price_and_unknown_code_remain_unknown(tmp_path):
    raw = fixture(transaction("J", "A", ""), checkbox="")
    parsed = extract_form4(*retained(raw, tmp_path))
    assert parsed.rule_10b5_1_checkbox is None
    row = parsed.nonderivative_transactions[0]
    assert row.reported_price_per_share is None and row.reported_price_times_shares is None
    assert row.classification == "other_or_unknown_reported_transaction"
    assert row.footnote_ids == ["F1"]
    assert row.warnings == ["no_specific_local_rationale", "price_not_reported_as_numeric"]


def test_invalid_numbers_unresolved_notes_and_ambiguous_fields_fail_closed(tmp_path):
    for price in ("NaN", "1e2", "1,000", "-1", "100.12345", "1000000000000"):
        with pytest.raises(ValueError):
            extract_form4(*retained(fixture(transaction(price=price)), tmp_path))
    for raw in (fixture(transaction()).replace(b'<footnote id="F1">', b'<footnote id="F2">'),
                fixture(transaction()).replace(b"<issuerCik>123</issuerCik>", b"<issuerCik>123</issuerCik><issuerCik>789</issuerCik>"),
                fixture(transaction(), checkbox="<aff10b5One>yes</aff10b5One>")):
        with pytest.raises(ValueError):
            extract_form4(*retained(raw, tmp_path))


def test_doctype_entity_and_non_utf8_inputs_are_not_silently_expanded(tmp_path):
    raw = fixture(transaction())
    dtd = raw.replace(b"<ownershipDocument>", b'<!DOCTYPE ownershipDocument [<!ENTITY file SYSTEM "file:///etc/passwd">]><ownershipDocument>')
    with pytest.raises(ValueError, match="DTD"):
        extract_form4(*retained(dtd, tmp_path))
    with pytest.raises(ValueError, match="UTF-8"):
        extract_form4(*retained(raw.replace(b'encoding="UTF-8"', b'encoding="ISO-8859-1"'), tmp_path))


def test_self_closing_and_quoted_attribute_footnotes_preserve_exact_xml_span(tmp_path):
    footnote = '<footnote id="F1"/>\n<footnote id="F2" description="a>b">Other</footnote>'
    parsed = extract_form4(*retained(fixture(transaction(), footnote=footnote), tmp_path))
    assert parsed.footnotes["F1"].quote == '<footnote id="F1"/>'
    assert parsed.footnotes["F2"].quote == '<footnote id="F2" description="a>b">Other</footnote>'
