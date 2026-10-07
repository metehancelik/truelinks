from datetime import date
from pathlib import Path

import pytest

from truelinks.modules.lease.rules import (
    EscalationAssessment,
    Outcome,
    Rule,
    RuleResult,
    evaluate_rules,
    load_ruleset,
    whole_months_between,
)
from truelinks.modules.lease.verification import FieldStatus, FieldValue, VerifiedField
from truelinks.modules.unit.records import find_units, load_units

DATA = Path(__file__).parents[2] / "data"
RULESET = load_ruleset(DATA / "owner_ruleset.json")
UNITS = load_units(DATA / "units.json")

DEFINED = EscalationAssessment(is_defined=True, reason="States a fixed 5% increase.")
VAGUE = EscalationAssessment(is_defined=False, reason='Only says "as mutually agreed".')

# A lease that satisfies every rule. Each test changes one thing.
CLEAN: dict[str, FieldValue | None] = {
    "landlord_name": "Marina Crest Holdings W.L.L.",
    "tenant_name": "Sara Haddad",
    "landlord_signed": True,
    "tenant_signed": True,
    "unit_reference": "Apartment 1204, Tower B, Marina Crest Residences",
    "commencement_date": date(2027, 1, 1),
    "expiry_date": date(2027, 12, 31),
    "term_months": 12,
    "monthly_rent": 9500.0,
    "annual_rent": 114000.0,
    "currency": "QAR",
    "payment_frequency": "monthly",
    "deposit_amount": 9500.0,
    "escalation_clause": "Rent increases by 5% on each renewal.",
    "renewal_terms": "Renews automatically for twelve months.",
    "termination_terms": "Ninety days written notice.",
}


def evaluate(
    changes: dict[str, FieldValue | None] | None = None,
    escalation: EscalationAssessment | None = DEFINED,
) -> dict[str, RuleResult]:
    values = CLEAN | (changes or {})
    fields = [
        VerifiedField(
            name,
            value,
            quote=None,
            status=FieldStatus.MISSING if value is None else FieldStatus.VERIFIED,
        )
        for name, value in values.items()
    ]
    results = evaluate_rules(RULESET, fields, UNITS, escalation)
    return {result.rule.id: result for result in results}


def test_ruleset_file_declares_the_seven_rules() -> None:
    assert [rule.id for rule in RULESET] == ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]


def test_clean_lease_passes_every_rule() -> None:
    results = evaluate()

    assert {rule_id: r.outcome for rule_id, r in results.items()} == dict.fromkeys(
        results, Outcome.PASS
    )


@pytest.mark.parametrize(
    ("rule_id", "changes"),
    [
        ("R1", {"deposit_amount": 5000.0}),
        ("R3", {"term_months": 48}),
        ("R4", {"expiry_date": date(2026, 12, 31)}),  # ends before it starts
        ("R4", {"expiry_date": date(2028, 6, 30)}),  # 18 months of dates, 12 stated
        ("R4", {"expiry_date": date(2027, 12, 15)}),  # not whole months
        ("R5", {"tenant_signed": False}),
        ("R6", {"annual_rent": 120000.0}),
        ("R7", {"unit_reference": "Apartment 1205, Tower B"}),  # occupied
        ("R7", {"unit_reference": "Apartment 9999, Tower B"}),  # not in the records
    ],
)
def test_rule_fails(rule_id: str, changes: dict[str, FieldValue | None]) -> None:
    assert evaluate(changes)[rule_id].outcome is Outcome.FAIL


@pytest.mark.parametrize(
    ("rule_id", "changes"),
    [
        ("R1", {"deposit_amount": None}),
        ("R2", {"escalation_clause": None}),
        ("R3", {"term_months": None}),
        ("R4", {"commencement_date": None}),
        ("R5", {"landlord_signed": None}),  # e.g. a signature that is an image
        ("R6", {"annual_rent": None}),  # only a monthly figure is stated
        ("R7", {"unit_reference": None}),
        ("R7", {"unit_reference": "Apartment 1204 and Apartment 1205, Tower B"}),
    ],
)
def test_rule_is_not_determinable_instead_of_guessing(
    rule_id: str, changes: dict[str, FieldValue | None]
) -> None:
    assert evaluate(changes)[rule_id].outcome is Outcome.NOT_DETERMINABLE


def test_escalation_rule_follows_the_evaluators_assessment() -> None:
    assert evaluate(escalation=DEFINED)["R2"].outcome is Outcome.PASS
    assert evaluate(escalation=VAGUE)["R2"].outcome is Outcome.FAIL
    assert evaluate(escalation=None)["R2"].outcome is Outcome.NOT_DETERMINABLE
    assert evaluate(escalation=VAGUE)["R2"].reason == VAGUE.reason


def test_result_names_the_fields_it_relied_on() -> None:
    result = evaluate()["R1"]

    assert [field.name for field in result.inputs] == ["deposit_amount", "monthly_rent"]


def test_failure_reason_states_the_numbers() -> None:
    reason = evaluate({"annual_rent": 120000.0})["R6"].reason

    assert reason == "Annual rent 120,000 is not 12 x 9,500 (114,000)."


def test_rule_without_a_check_is_reported_not_passed() -> None:
    new_rule = Rule(id="R99", description="Added to the file, not to the code.", severity="low")

    [result] = evaluate_rules([new_rule], [], UNITS)

    assert result.outcome is Outcome.NOT_DETERMINABLE
    assert "R99" in result.reason


@pytest.mark.parametrize(
    ("start", "end", "months"),
    [
        (date(2027, 1, 1), date(2027, 12, 31), 12),  # inclusive end date
        (date(2027, 1, 1), date(2028, 1, 1), 12),  # anniversary named as the end
        (date(2027, 3, 15), date(2030, 3, 14), 36),
        (date(2027, 1, 1), date(2027, 12, 15), None),
    ],
)
def test_whole_months_between(start: date, end: date, months: int | None) -> None:
    assert whole_months_between(start, end) == months


def test_unit_is_found_by_label_and_building() -> None:
    [unit] = find_units("apartment 0301,  Tower A, Marina Crest Residences", UNITS)

    assert unit.unit_id == "MC-A-0301"


def test_label_alone_does_not_identify_a_unit() -> None:
    assert find_units("Apartment 1204", UNITS) == []


def test_a_unit_occupied_by_this_lease_still_passes_r7() -> None:
    occupied = [
        unit.model_copy(update={"status": "occupied"}) if unit.unit_id == "MC-B-1204" else unit
        for unit in UNITS
    ]
    fields = [
        VerifiedField(name, value, quote=None, status=FieldStatus.VERIFIED)
        for name, value in CLEAN.items()
    ]

    as_new_lease = evaluate_rules(RULESET, fields, occupied, DEFINED)
    as_active_lease = evaluate_rules(RULESET, fields, occupied, DEFINED, "MC-B-1204")

    assert as_new_lease[-1].outcome is Outcome.FAIL
    assert as_active_lease[-1].outcome is Outcome.PASS
