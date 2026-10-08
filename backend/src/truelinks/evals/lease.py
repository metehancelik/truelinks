"""Score the lease agent against hand-written answers.

The number that matters most is `trusted_but_wrong`: a field the system marks
VERIFIED whose value is wrong. Those reach a person looking settled, so they
are the failures review cannot catch. Everything else is either right, or
wrong and flagged, which is what review is for.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from truelinks.modules.lease.documents import read_document
from truelinks.modules.lease.pipeline import analyse_lease
from truelinks.modules.lease.rules import Outcome, Rule
from truelinks.modules.lease.schema import FieldValue, parse_field_value
from truelinks.modules.lease.verification import FieldStatus, VerifiedField
from truelinks.modules.unit.records import Unit
from truelinks.platform.llm.types import LLMImage, LLMProvider

# Summaries written by the model: checked for a phrase, not for exact words.
SUMMARY_FIELDS = frozenset({"escalation_clause", "renewal_terms", "termination_terms"})


class EvalCase(BaseModel):
    name: str
    document: str
    tests: str
    needs_ocr: bool = False
    fields: dict[str, Any]
    rules: dict[str, Outcome]


@dataclass(frozen=True)
class FieldScore:
    name: str
    expected: Any
    actual: FieldValue | None
    status: FieldStatus
    correct: bool

    @property
    def trusted(self) -> bool:
        """Shown to a person as settled: verified, or correctly reported as absent."""
        return self.status is FieldStatus.VERIFIED or (
            self.status is FieldStatus.MISSING and self.expected is None
        )


@dataclass
class CaseResult:
    case: EvalCase
    fields: list[FieldScore] = field(default_factory=list[FieldScore])
    rules: dict[str, tuple[Outcome, Outcome]] = field(
        default_factory=dict[str, tuple[Outcome, Outcome]]
    )
    seconds: float = 0.0
    tokens: int = 0
    error: str | None = None

    @property
    def trusted_but_wrong(self) -> list[FieldScore]:
        return [f for f in self.fields if f.trusted and not f.correct]

    @property
    def flagged_and_wrong(self) -> list[FieldScore]:
        return [f for f in self.fields if not f.trusted and not f.correct]

    @property
    def flagged_but_right(self) -> list[FieldScore]:
        return [f for f in self.fields if not f.trusted and f.correct]

    @property
    def rules_wrong(self) -> list[str]:
        return [rule for rule, (expected, got) in self.rules.items() if expected is not got]


def load_cases(path: Path) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [EvalCase.model_validate(case) for case in raw["cases"]]


async def run_case(
    llm: LLMProvider, case: EvalCase, root: Path, ruleset: list[Rule], units: list[Unit]
) -> CaseResult:
    result = CaseResult(case)
    path = root / case.document
    try:
        document = read_document(path.name, path.read_bytes())
        page = (
            LLMImage(media_type="image/png", data=document.signature_page)
            if document.signature_page
            else None
        )
        analysis = await analyse_lease(llm, document.text, ruleset, units, page)
    except Exception as error:  # one broken case must not stop the run
        result.error = f"{type(error).__name__}: {error}"
        return result

    by_name = {f.name: f for f in analysis.fields}
    result.fields = [score_field(name, by_name[name], case.fields[name]) for name in case.fields]
    result.rules = {
        r.rule.id: (case.rules[r.rule.id], r.outcome)
        for r in analysis.rules
        if r.rule.id in case.rules
    }
    result.seconds = sum(step.duration_ms for step in analysis.trace) / 1000
    result.tokens = sum(step.input_tokens + step.output_tokens for step in analysis.trace)
    return result


def score_field(name: str, field: VerifiedField, expected: Any) -> FieldScore:
    return FieldScore(
        name, expected, field.value, field.status, matches(name, field.value, expected)
    )


def matches(name: str, actual: FieldValue | None, expected: Any) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    if name in SUMMARY_FIELDS:
        # true: any summary will do; text: the summary must mention it.
        return expected is True or str(expected).casefold() in str(actual).casefold()
    if isinstance(actual, str):
        # Names and references: the expected text must be there; extra detail is fine.
        return str(expected).casefold() in actual.casefold()
    wanted = parse_field_value(name, expected)
    if isinstance(actual, date | bool):
        return actual == wanted
    return isinstance(wanted, int | float) and abs(float(actual) - float(wanted)) < 0.005


@dataclass(frozen=True)
class Summary:
    cases: int
    errors: int
    fields: int
    correct: int
    trusted_but_wrong: int
    flagged_and_wrong: int
    flagged_but_right: int
    rules: int
    rules_correct: int
    seconds_per_lease: float


def summarise(results: list[CaseResult]) -> Summary:
    scored = [r for r in results if r.error is None]
    fields = [f for r in scored for f in r.fields]
    rules = [pair for r in scored for pair in r.rules.values()]
    return Summary(
        cases=len(results),
        errors=len(results) - len(scored),
        fields=len(fields),
        correct=sum(f.correct for f in fields),
        trusted_but_wrong=sum(len(r.trusted_but_wrong) for r in scored),
        flagged_and_wrong=sum(len(r.flagged_and_wrong) for r in scored),
        flagged_but_right=sum(len(r.flagged_but_right) for r in scored),
        rules=len(rules),
        rules_correct=sum(expected is got for expected, got in rules),
        seconds_per_lease=round(sum(r.seconds for r in scored) / max(len(scored), 1), 1),
    )
