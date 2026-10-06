"""The owner's acceptance rules, evaluated as plain code.

The model reads the lease; it never decides whether a rule passes. Every rule
here is a small pure function over the verified fields, so the same lease
always gets the same verdict and each verdict can be traced to its inputs.
"""

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from truelinks.modules.lease.verification import VerifiedField
from truelinks.modules.unit.records import Unit, find_units

MAX_TERM_MONTHS = 36


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_DETERMINABLE = "NOT_DETERMINABLE"


class Rule(BaseModel, frozen=True):
    """One entry of the owner's ruleset file."""

    id: str
    description: str
    severity: Literal["low", "medium", "high"]


@dataclass(frozen=True)
class EscalationAssessment:
    """The evaluator's reading of the escalation clause (rule R2 needs judgement)."""

    is_defined: bool
    reason: str


@dataclass(frozen=True)
class Verdict:
    outcome: Outcome
    reason: str


@dataclass(frozen=True)
class RuleResult:
    rule: Rule
    outcome: Outcome
    reason: str
    # The lease fields the verdict relied on; their quotes are the source clauses.
    inputs: tuple[VerifiedField, ...]


@dataclass(frozen=True)
class RuleContext:
    """Everything a rule may look at."""

    fields: Mapping[str, VerifiedField]
    units: list[Unit]
    escalation: EscalationAssessment | None

    def number(self, name: str) -> float | None:
        value = self.fields[name].value
        return (
            float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
        )

    def day(self, name: str) -> date | None:
        value = self.fields[name].value
        return value if isinstance(value, date) else None

    def flag(self, name: str) -> bool | None:
        value = self.fields[name].value
        return value if isinstance(value, bool) else None

    def text(self, name: str) -> str | None:
        value = self.fields[name].value
        return value if isinstance(value, str) else None


def load_ruleset(path: Path) -> list[Rule]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Rule.model_validate(rule) for rule in raw["rules"]]


def evaluate_rules(
    ruleset: list[Rule],
    fields: list[VerifiedField],
    units: list[Unit],
    escalation: EscalationAssessment | None = None,
) -> list[RuleResult]:
    context = RuleContext({field.name: field for field in fields}, units, escalation)
    return [_evaluate(rule, context) for rule in ruleset]


def _evaluate(rule: Rule, context: RuleContext) -> RuleResult:
    check = _CHECKS.get(rule.id)
    if check is None:
        # A rule added to the file without code behind it must not pass silently.
        verdict = _unknown(f"No check is implemented for rule {rule.id}.")
        return RuleResult(rule, verdict.outcome, verdict.reason, ())

    verdict = check.run(context)
    inputs = tuple(context.fields[name] for name in check.inputs)
    return RuleResult(rule, verdict.outcome, verdict.reason, inputs)


def _passed(reason: str) -> Verdict:
    return Verdict(Outcome.PASS, reason)


def _failed(reason: str) -> Verdict:
    return Verdict(Outcome.FAIL, reason)


def _unknown(reason: str) -> Verdict:
    return Verdict(Outcome.NOT_DETERMINABLE, reason)


def _missing(*labels: str) -> Verdict:
    """A field the model did not find never fails a rule; it goes to a human.

    "Not found by the model" is not the same as "not in the lease".
    """
    return _unknown(f"The lease record has no {' or '.join(labels)}.")


# --- The rules ---------------------------------------------------------------


def _deposit_covers_one_month(c: RuleContext) -> Verdict:
    deposit, rent = c.number("deposit_amount"), c.number("monthly_rent")
    if deposit is None or rent is None:
        return _missing("deposit amount", "monthly rent")
    if deposit >= rent:
        return _passed(f"Deposit {deposit:,.0f} covers one month's rent of {rent:,.0f}.")
    return _failed(f"Deposit {deposit:,.0f} is below one month's rent of {rent:,.0f}.")


def _escalation_is_defined(c: RuleContext) -> Verdict:
    if c.text("escalation_clause") is None:
        return _missing("rent escalation clause")
    if c.escalation is None:
        return _unknown("The escalation clause has not been assessed yet.")
    if c.escalation.is_defined:
        return _passed(c.escalation.reason)
    return _failed(c.escalation.reason)


def _term_within_limit(c: RuleContext) -> Verdict:
    term = c.number("term_months")
    if term is None:
        return _missing("stated term")
    if term <= MAX_TERM_MONTHS:
        return _passed(f"Term of {term:.0f} months is within the {MAX_TERM_MONTHS}-month limit.")
    return _failed(
        f"Term of {term:.0f} months exceeds {MAX_TERM_MONTHS} months; owner approval is required."
    )


def _dates_match_term(c: RuleContext) -> Verdict:
    start, end, term = c.day("commencement_date"), c.day("expiry_date"), c.number("term_months")
    if start is None or end is None or term is None:
        return _missing("commencement date", "expiry date", "stated term")
    if end <= start:
        return _failed(f"Expiry {end} is not after commencement {start}.")

    months = whole_months_between(start, end)
    if months is None:
        return _failed(f"{start} to {end} is not a whole number of months.")
    if months != term:
        return _failed(f"The lease states {term:.0f} months but {start} to {end} is {months}.")
    return _passed(f"{start} to {end} is {months} months, as stated.")


def _both_parties_signed(c: RuleContext) -> Verdict:
    if c.text("landlord_name") is None or c.text("tenant_name") is None:
        return _missing("landlord name", "tenant name")

    signed = {"landlord": c.flag("landlord_signed"), "tenant": c.flag("tenant_signed")}
    if None in signed.values():
        # Signatures in a scanned lease are images, which text extraction cannot see.
        return _unknown("A signature could not be read from the lease text; check the document.")

    unsigned = [party for party, has_signed in signed.items() if not has_signed]
    if unsigned:
        return _failed(f"Not signed by the {' or the '.join(unsigned)}.")
    return _passed("Both parties are identified and have signed.")


def _annual_rent_reconciles(c: RuleContext) -> Verdict:
    annual, monthly = c.number("annual_rent"), c.number("monthly_rent")
    if annual is None or monthly is None:
        return _missing("annual rent", "monthly rent")
    if math.isclose(annual, monthly * 12, abs_tol=0.005):
        return _passed(f"Annual rent {annual:,.0f} equals 12 x {monthly:,.0f}.")
    return _failed(f"Annual rent {annual:,.0f} is not 12 x {monthly:,.0f} ({monthly * 12:,.0f}).")


def _unit_exists_and_is_available(c: RuleContext) -> Verdict:
    reference = c.text("unit_reference")
    if reference is None:
        return _missing("unit reference")

    matches = find_units(reference, c.units)
    if not matches:
        return _failed(f'No unit in the owner\'s records matches "{reference}".')
    if len(matches) > 1:
        ids = ", ".join(unit.unit_id for unit in matches)
        return _unknown(f'"{reference}" matches several units: {ids}.')

    unit = matches[0]
    if unit.status != "available":
        return _failed(f"Unit {unit.unit_id} is {unit.status}; it cannot take a new lease.")
    return _passed(f"Unit {unit.unit_id} exists and is available.")


def whole_months_between(start: date, end: date) -> int | None:
    """Months from `start` to `end`, or None when they are not whole months apart.

    A lease term usually ends the day before its anniversary (1 Jan to 31 Dec
    is twelve months), so the end date is treated as inclusive. A lease that
    names the anniversary itself (1 Jan to 1 Jan) is accepted as well.
    """
    for boundary in (end + timedelta(days=1), end):
        if boundary.day == start.day:
            return (boundary.year - start.year) * 12 + boundary.month - start.month
    return None


@dataclass(frozen=True)
class _Check:
    run: Callable[[RuleContext], Verdict]
    inputs: tuple[str, ...]


# Rule ids are the contract with the owner's ruleset file.
_CHECKS: dict[str, _Check] = {
    "R1": _Check(_deposit_covers_one_month, ("deposit_amount", "monthly_rent")),
    "R2": _Check(_escalation_is_defined, ("escalation_clause",)),
    "R3": _Check(_term_within_limit, ("term_months",)),
    "R4": _Check(_dates_match_term, ("commencement_date", "expiry_date", "term_months")),
    "R5": _Check(
        _both_parties_signed,
        ("landlord_name", "tenant_name", "landlord_signed", "tenant_signed"),
    ),
    "R6": _Check(_annual_rent_reconciles, ("annual_rent", "monthly_rent")),
    "R7": _Check(_unit_exists_and_is_available, ("unit_reference",)),
}
