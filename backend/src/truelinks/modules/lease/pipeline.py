"""The lease agent: read, verify, review, apply the rules.

Two steps call a model and two are plain code. Each one records what it cost,
so a slow or expensive step is visible instead of buried in a total.
"""

import time
from dataclasses import dataclass

from pydantic import BaseModel

from truelinks.modules.lease.extraction import extract_lease
from truelinks.modules.lease.review import apply_concerns, review_lease
from truelinks.modules.lease.rules import (
    ESCALATION_RULE_ID,
    EscalationAssessment,
    Rule,
    RuleResult,
    evaluate_rules,
)
from truelinks.modules.lease.verification import VerifiedField, verify_extraction
from truelinks.modules.unit.records import Unit
from truelinks.platform.llm.types import LLMProvider, StructuredResult


@dataclass(frozen=True)
class StepTrace:
    name: str
    model: str | None  # None for steps that are plain code
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class LeaseAnalysis:
    fields: list[VerifiedField]
    # Kept so the rules can be re-evaluated after a person corrects a field.
    escalation: EscalationAssessment | None
    rules: list[RuleResult]
    trace: list[StepTrace]


async def analyse_lease(
    llm: LLMProvider, lease_text: str, ruleset: list[Rule], units: list[Unit]
) -> LeaseAnalysis:
    trace: list[StepTrace] = []

    extraction = await extract_lease(llm, lease_text)
    trace.append(_model_step("extract", extraction))

    started = time.perf_counter()
    fields = verify_extraction(extraction.data, lease_text)
    trace.append(_code_step("verify", started))

    escalation_rule = next(
        (rule.description for rule in ruleset if rule.id == ESCALATION_RULE_ID), ""
    )
    review = await review_lease(llm, lease_text, fields, escalation_rule)
    trace.append(_model_step("review", review))
    fields = apply_concerns(fields, review.data.concerns)

    started = time.perf_counter()
    rules = evaluate_rules(ruleset, fields, units, review.data.escalation)
    trace.append(_code_step("rules", started))

    return LeaseAnalysis(fields, review.data.escalation, rules, trace)


def _model_step[T: BaseModel](name: str, result: StructuredResult[T]) -> StepTrace:
    return StepTrace(
        name, result.model, result.duration_ms, result.input_tokens, result.output_tokens
    )


def _code_step(name: str, started: float) -> StepTrace:
    return StepTrace(name, None, round((time.perf_counter() - started) * 1000))
