"""The evaluation harness itself, run on the canned answers of the bundled samples."""

import asyncio
from datetime import date
from pathlib import Path

from truelinks.evals.lease import load_cases, matches, run_case, summarise
from truelinks.modules.lease.demo import register_demo_leases
from truelinks.modules.lease.rules import load_ruleset
from truelinks.modules.unit.records import load_units
from truelinks.platform.llm.stub import StubProvider

ROOT = Path(__file__).parents[2]
CASES = load_cases(ROOT / "evals" / "leases" / "cases.json")


def test_every_case_points_at_a_document_and_covers_every_rule() -> None:
    for case in CASES:
        assert (ROOT / case.document).is_file(), case.name
        assert set(case.rules) == {f"R{n}" for n in range(1, 8)}, case.name


def test_canned_answers_score_perfectly() -> None:
    llm = register_demo_leases(StubProvider())
    ruleset = load_ruleset(ROOT / "data" / "owner_ruleset.json")
    units = load_units(ROOT / "data" / "units.json")
    cases = [c for c in CASES if c.name in ("clean", "problems")]

    results = [asyncio.run(run_case(llm, c, ROOT, ruleset, units)) for c in cases]
    summary = summarise(results)

    assert summary.errors == 0
    assert summary.correct == summary.fields
    assert summary.trusted_but_wrong == 0
    assert summary.rules_correct == summary.rules


def test_values_are_compared_by_meaning_not_by_spelling() -> None:
    assert matches("monthly_rent", 9500.0, 9500)
    assert matches("commencement_date", date(2027, 1, 1), "2027-01-01")
    assert matches("tenant_name", "Ms Sara Haddad", "Sara Haddad")
    assert matches("escalation_clause", "Rent rises 5% on renewal.", "5")
    assert matches("monthly_rent", None, None)
    assert not matches("monthly_rent", 42000.0, None)  # calculated or invented
    assert not matches("tenant_signed", True, False)
