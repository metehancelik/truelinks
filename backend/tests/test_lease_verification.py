from datetime import date
from typing import Any

import pytest

from truelinks.modules.lease.schema import LeaseExtraction
from truelinks.modules.lease.verification import (
    FieldStatus,
    VerificationIssue,
    VerifiedField,
    verify_extraction,
)

LQ, RQ = "\N{LEFT DOUBLE QUOTATION MARK}", "\N{RIGHT DOUBLE QUOTATION MARK}"

DOCUMENT = f"""
RESIDENTIAL LEASE AGREEMENT
This lease is made between Marina Crest Holdings W.L.L. (the {LQ}Landlord{RQ}) and
Sara Haddad (the {LQ}Tenant{RQ}) for Apartment 1204, Tower B.
The term is twelve (12) months, commencing on 1 January 2027 and
expiring on 31 December 2027.
Rent is QAR 9,500 per month, being QAR 114,000 per annum.
A security deposit of QAR 9,500 is payable on signing.
The rent shall increase by 5% on each anniversary.
"""


def verify(field: str, value: Any, quote: str | None) -> VerifiedField:
    """Verify one field of an otherwise empty extraction."""
    fields: dict[str, dict[str, Any]] = {
        name: {"value": None, "quote": None} for name in LeaseExtraction.model_fields
    }
    fields[field] = {"value": value, "quote": quote}
    extraction = LeaseExtraction.model_validate(fields)

    return next(f for f in verify_extraction(extraction, DOCUMENT) if f.name == field)


def test_field_without_value_is_missing() -> None:
    result = verify("deposit_amount", None, None)

    assert result.status is FieldStatus.MISSING
    assert result.issue is None


@pytest.mark.parametrize(
    ("field", "value", "quote"),
    [
        ("monthly_rent", 9500, "Rent is QAR 9,500 per month"),
        ("term_months", 12, "The term is twelve (12) months"),
        ("commencement_date", date(2027, 1, 1), "commencing on 1 January 2027"),
        (
            "tenant_name",
            "Sara Haddad",
            f"Sara Haddad (the {LQ}Tenant{RQ})",
        ),
        # An interpreted field: only its quote is checked here.
        ("escalation_clause", "Rent rises 5% a year.", "The rent shall increase by 5%"),
    ],
)
def test_value_backed_by_its_quote_is_verified(field: str, value: Any, quote: str) -> None:
    assert verify(field, value, quote).status is FieldStatus.VERIFIED


@pytest.mark.parametrize(
    ("field", "value", "quote", "issue"),
    [
        ("monthly_rent", 9500, None, VerificationIssue.NO_QUOTE),
        ("monthly_rent", 9500, "   ", VerificationIssue.NO_QUOTE),
        # An invented quote.
        (
            "monthly_rent",
            12000,
            "Rent is QAR 12,000 per month",
            VerificationIssue.QUOTE_NOT_IN_DOCUMENT,
        ),
        # A real quote, misread.
        (
            "monthly_rent",
            12000,
            "Rent is QAR 9,500 per month",
            VerificationIssue.VALUE_NOT_IN_QUOTE,
        ),
        (
            "expiry_date",
            date(2028, 12, 31),
            "expiring on 31 December 2027",
            VerificationIssue.VALUE_NOT_IN_QUOTE,
        ),
        ("tenant_name", "Sarah Haddad", "Sara Haddad", VerificationIssue.VALUE_NOT_IN_QUOTE),
    ],
)
def test_unconfirmed_value_is_unverified_with_a_reason(
    field: str, value: Any, quote: str | None, issue: VerificationIssue
) -> None:
    result = verify(field, value, quote)

    assert result.status is FieldStatus.UNVERIFIED
    assert result.issue is issue


def test_quote_matches_across_line_breaks_case_and_typographic_quotes() -> None:
    quote = 'between MARINA CREST HOLDINGS W.L.L. (the "Landlord") and Sara Haddad'

    assert verify("landlord_name", "Marina Crest Holdings W.L.L.", quote).status is (
        FieldStatus.VERIFIED
    )


def test_layers_one_and_two_cannot_tell_a_quote_is_about_the_wrong_field() -> None:
    """Right number, wrong sentence: this is what the evaluator (layer 3) is for."""
    result = verify("monthly_rent", 9500, "A security deposit of QAR 9,500 is payable")

    assert result.status is FieldStatus.VERIFIED
