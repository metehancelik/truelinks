"""Canned agent answers for the bundled sample leases.

With `LLM_PROVIDER=stub` the whole application runs without a model: same
pipeline, same checks, answers looked up here. The hosted demo uses this.
A test runs each answer against its sample file, so they cannot drift apart.
"""

from typing import Any

from truelinks.modules.lease.extraction import LEASE_EXTRACT_TASK
from truelinks.modules.lease.review import LEASE_REVIEW_TASK
from truelinks.platform.llm.stub import StubProvider
from truelinks.platform.llm.types import StructuredRequest


def _field(value: Any, quote: str | None) -> dict[str, Any]:
    return {"value": value, "quote": quote}


_LANDLORD = _field("Marina Crest Holdings W.L.L.", "LANDLORD: Marina Crest Holdings W.L.L.")
_LANDLORD_SIGNED = _field(True, "For the Landlord: /s/ Khalid Al-Mansoori")

CLEAN_EXTRACTION: dict[str, dict[str, Any]] = {
    "landlord_name": _LANDLORD,
    "tenant_name": _field("Sara Haddad", "TENANT: Sara Haddad"),
    "landlord_signed": _LANDLORD_SIGNED,
    "tenant_signed": _field(True, "For the Tenant: /s/ Sara Haddad"),
    "unit_reference": _field(
        "Apartment 1204, Tower B, Marina Crest Residences",
        "Apartment 1204, Tower B, Marina Crest Residences",
    ),
    "commencement_date": _field("2027-01-01", "commencing on 1 January 2027"),
    "expiry_date": _field("2027-12-31", "expiring on 31 December 2027"),
    "term_months": _field(12, "a fixed term of twelve (12) months"),
    "monthly_rent": _field(9500, "twelve equal monthly instalments of QAR 9,500"),
    "annual_rent": _field(114000, "The annual rent is QAR 114,000"),
    "currency": _field("QAR", "The annual rent is QAR 114,000"),
    "payment_frequency": _field("monthly", "payable in twelve equal monthly instalments"),
    "deposit_amount": _field(9500, "a security deposit of QAR 9,500"),
    "escalation_clause": _field(
        "Rent rises 5% on each renewal.", "the rent shall increase by five percent (5%)"
    ),
    "renewal_terms": _field(
        "Renews automatically for twelve months unless notice is given 60 days before expiry.",
        "This lease renews automatically for a further term of twelve (12) months",
    ),
    "termination_terms": _field(
        "Either party may end the lease with 90 days written notice.",
        "by giving ninety (90) days written notice",
    ),
}

CLEAN_REVIEW: dict[str, Any] = {
    "escalation_is_defined": True,
    "escalation_reason": "The clause fixes the increase at 5% of the previous term's rent.",
    "concerns": [],
}

PROBLEM_EXTRACTION: dict[str, dict[str, Any]] = {
    "landlord_name": _LANDLORD,
    "tenant_name": _field("Omar Khalil", "TENANT: Omar Khalil"),
    "landlord_signed": _LANDLORD_SIGNED,
    "tenant_signed": _field(False, "For the Tenant: ______________________"),
    "unit_reference": _field(
        "Apartment 1205, Tower B, Marina Crest Residences",
        "Apartment 1205, Tower B, Marina Crest Residences",
    ),
    "commencement_date": _field("2027-03-01", "commencing on 1 March 2027"),
    "expiry_date": _field("2028-08-31", "expiring on 31 August 2028"),
    "term_months": _field(24, "a fixed term of twenty-four (24) months"),
    "monthly_rent": _field(11000, "payable in monthly instalments of QAR 11,000"),
    "annual_rent": _field(120000, "The annual rent is QAR 120,000"),
    "currency": _field("QAR", "The annual rent is QAR 120,000"),
    "payment_frequency": _field("monthly", "payable in monthly instalments"),
    "deposit_amount": _field(5000, "a security deposit of QAR 5,000"),
    "escalation_clause": _field(
        "Rent may be increased on renewal by mutual agreement.",
        "The rent may be increased upon renewal as mutually agreed between the parties.",
    ),
    "renewal_terms": _field(
        "Renewal needs written agreement of both parties 60 days before expiry.",
        "This lease may be renewed for a further term by written agreement of both parties",
    ),
    "termination_terms": _field(
        "The tenant may leave with 60 days notice and one month's rent as compensation.",
        "by giving sixty (60) days written notice",
    ),
}

PROBLEM_REVIEW: dict[str, Any] = {
    "escalation_is_defined": False,
    "escalation_reason": (
        'The clause only says "as mutually agreed": no percentage, amount or index is stated.'
    ),
    "concerns": [
        {
            "field": "term_months",
            "kind": "CONTRADICTION",
            "explanation": (
                "The lease states 24 months, but 1 March 2027 to 31 August 2028 is 18 months."
            ),
        }
    ],
}

# A phrase that identifies each sample, mapped to (extraction, review).
_SAMPLES: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "TENANT: Sara Haddad": (CLEAN_EXTRACTION, CLEAN_REVIEW),
    "TENANT: Omar Khalil": (PROBLEM_EXTRACTION, PROBLEM_REVIEW),
}


def _answer(request: StructuredRequest[Any], index: int) -> dict[str, Any]:
    for marker, answers in _SAMPLES.items():
        if marker in request.prompt:
            return answers[index]
    raise LookupError("Demo mode only knows the bundled sample leases.")


def register_demo_leases(stub: StubProvider) -> StubProvider:
    return stub.register(LEASE_EXTRACT_TASK, lambda request: _answer(request, 0)).register(
        LEASE_REVIEW_TASK, lambda request: _answer(request, 1)
    )
