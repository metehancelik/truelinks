"""The whole lease agent, run against the stub: no model, same code path."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from truelinks.modules.lease.extraction import LEASE_EXTRACT_TASK
from truelinks.modules.lease.pipeline import LeaseAnalysis, analyse_lease
from truelinks.modules.lease.review import LEASE_REVIEW_TASK
from truelinks.modules.lease.rules import Outcome, load_ruleset
from truelinks.modules.lease.signatures import LEASE_SIGNATURES_TASK
from truelinks.modules.lease.verification import FieldStatus, VerificationIssue
from truelinks.modules.unit.records import load_units
from truelinks.platform.llm.stub import StubProvider
from truelinks.platform.llm.types import LLMImage

ROOT = Path(__file__).parents[2]
RULESET = load_ruleset(ROOT / "data" / "owner_ruleset.json")
UNITS = load_units(ROOT / "data" / "units.json")
LEASE = (ROOT / "samples" / "leases" / "01-clean-mc-b-1204.txt").read_text(encoding="utf-8")


def field(value: Any, quote: str | None) -> dict[str, Any]:
    return {"value": value, "quote": quote}


# What a careful reader extracts from the clean sample lease.
EXTRACTION: dict[str, dict[str, Any]] = {
    "landlord_name": field(
        "Marina Crest Holdings W.L.L.", "LANDLORD: Marina Crest Holdings W.L.L."
    ),
    "tenant_name": field("Sara Haddad", "TENANT: Sara Haddad"),
    "landlord_signed": field(True, "For the Landlord: /s/ Khalid Al-Mansoori"),
    "tenant_signed": field(True, "For the Tenant: /s/ Sara Haddad"),
    "unit_reference": field(
        "Apartment 1204, Tower B, Marina Crest Residences",
        "Apartment 1204, Tower B, Marina Crest Residences",
    ),
    "commencement_date": field("2027-01-01", "commencing on 1 January 2027"),
    "expiry_date": field("2027-12-31", "expiring on 31 December 2027"),
    "term_months": field(12, "a fixed term of twelve (12) months"),
    "monthly_rent": field(9500, "twelve equal monthly instalments of QAR 9,500"),
    "annual_rent": field(114000, "The annual rent is QAR 114,000"),
    "currency": field("QAR", "The annual rent is QAR 114,000"),
    "payment_frequency": field("monthly", "payable in twelve equal monthly instalments"),
    "deposit_amount": field(9500, "a security deposit of QAR 9,500"),
    "escalation_clause": field(
        "Rent rises 5% on each renewal.", "the rent shall increase by five percent (5%)"
    ),
    "renewal_terms": field(
        "Renews automatically for twelve months.", "This lease renews automatically"
    ),
    "termination_terms": field("Ninety days written notice.", "ninety (90) days written notice"),
}

CLEAN_REVIEW: dict[str, Any] = {
    "escalation_is_defined": True,
    "escalation_reason": "The clause fixes the increase at 5% of the previous rent.",
    "concerns": [],
}


def analyse(
    extraction: dict[str, dict[str, Any]] = EXTRACTION, review: dict[str, Any] = CLEAN_REVIEW
) -> LeaseAnalysis:
    llm = (
        StubProvider()
        .register(LEASE_EXTRACT_TASK, lambda _: extraction)
        .register(LEASE_REVIEW_TASK, lambda _: review)
    )
    return asyncio.run(analyse_lease(llm, LEASE, RULESET, UNITS))


def test_clean_lease_is_fully_verified_and_passes_every_rule() -> None:
    analysis = analyse()

    assert {f.status for f in analysis.fields} == {FieldStatus.VERIFIED}
    assert {r.outcome for r in analysis.rules} == {Outcome.PASS}


def test_escalation_rule_carries_the_evaluators_reason() -> None:
    vague = CLEAN_REVIEW | {
        "escalation_is_defined": False,
        "escalation_reason": 'The clause only says "as mutually agreed".',
    }

    [rule] = [r for r in analyse(review=vague).rules if r.rule.id == "R2"]

    assert rule.outcome is Outcome.FAIL
    assert rule.reason == 'The clause only says "as mutually agreed".'


WRONG_SOURCE = {
    "field": "monthly_rent",
    "kind": "WRONG_SOURCE",
    "explanation": "The quote states the deposit, not the rent.",
}


def test_evaluator_catches_what_the_code_checks_cannot() -> None:
    """Right number, wrong sentence: layers 1 and 2 pass it, layer 3 rejects it."""
    extraction = EXTRACTION | {"monthly_rent": field(9500, "a security deposit of QAR 9,500")}

    analysis = analyse(extraction, CLEAN_REVIEW | {"concerns": [WRONG_SOURCE]})

    [rent] = [f for f in analysis.fields if f.name == "monthly_rent"]
    assert rent.status is FieldStatus.UNVERIFIED
    assert rent.issue is VerificationIssue.WRONG_SOURCE
    assert rent.explanation == "The quote states the deposit, not the rent."
    assert rent.value == 9500  # flagged, never rewritten


def test_a_field_the_code_already_rejected_keeps_its_own_reason() -> None:
    extraction = EXTRACTION | {"monthly_rent": field(9500, "Rent is QAR 9,500 a month")}

    analysis = analyse(extraction, CLEAN_REVIEW | {"concerns": [WRONG_SOURCE]})

    [rent] = [f for f in analysis.fields if f.name == "monthly_rent"]
    assert rent.issue is VerificationIssue.QUOTE_NOT_IN_DOCUMENT
    assert rent.explanation is None


def test_evaluator_cannot_report_an_issue_that_only_code_can_establish() -> None:
    concern = WRONG_SOURCE | {"kind": "QUOTE_NOT_IN_DOCUMENT"}

    with pytest.raises(ValidationError):
        analyse(review=CLEAN_REVIEW | {"concerns": [concern]})


def test_evaluator_cannot_raise_a_concern_about_a_field_that_does_not_exist() -> None:
    concern = {"field": "rent_per_week", "kind": "IMPLAUSIBLE", "explanation": "Too high."}

    with pytest.raises(ValidationError, match="is not a lease field"):
        analyse(review=CLEAN_REVIEW | {"concerns": [concern]})


def test_every_step_is_traced_and_only_model_steps_name_a_model() -> None:
    trace = analyse().trace

    assert [step.name for step in trace] == ["extract", "verify", "review", "rules"]
    assert [step.model for step in trace] == ["stub", None, "stub", None]


def test_on_a_scan_the_signature_page_decides_the_signatures_and_a_person_confirms() -> None:
    llm = (
        StubProvider()
        .register(LEASE_EXTRACT_TASK, lambda _: EXTRACTION)
        .register(LEASE_REVIEW_TASK, lambda _: CLEAN_REVIEW)
        .register(
            LEASE_SIGNATURES_TASK,
            lambda request: {
                "landlord_signed": len(request.images) == 1,
                "tenant_signed": False,
                "explanation": "The landlord line is signed; the tenant line is empty.",
            },
        )
    )
    page = LLMImage(media_type="image/png", data=b"not a real page")

    analysis = asyncio.run(analyse_lease(llm, LEASE, RULESET, UNITS, page))

    signed = {f.name: f for f in analysis.fields if f.name.endswith("_signed")}
    assert signed["landlord_signed"].value is True
    assert signed["tenant_signed"].value is False
    # A judgement on an image cannot be checked by code, so a person confirms it.
    assert {f.status for f in signed.values()} == {FieldStatus.UNVERIFIED}
    assert "signature page" in (signed["tenant_signed"].explanation or "")
    assert next(r for r in analysis.rules if r.rule.id == "R5").outcome is Outcome.FAIL
    assert [step.name for step in analysis.trace] == [
        "extract",
        "verify",
        "review",
        "signatures",
        "rules",
    ]
