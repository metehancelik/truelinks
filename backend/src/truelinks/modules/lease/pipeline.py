"""The lease agent: read, verify, review, apply the rules.

Two steps call a model and two are plain code. Each one records what it cost,
so a slow or expensive step is visible instead of buried in a total.
"""

import time
from dataclasses import dataclass

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
from truelinks.platform.llm.types import LLMProvider
from truelinks.platform.trace import StepTrace, code_step, model_step


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
    trace.append(model_step("extract", extraction))

    started = time.perf_counter()
    fields = verify_extraction(extraction.data, lease_text)
    trace.append(code_step("verify", started))

    escalation_rule = next(
        (rule.description for rule in ruleset if rule.id == ESCALATION_RULE_ID), ""
    )
    review = await review_lease(llm, lease_text, fields, escalation_rule)
    trace.append(model_step("review", review))
    fields = apply_concerns(fields, review.data.concerns)

    started = time.perf_counter()
    rules = evaluate_rules(ruleset, fields, units, review.data.escalation)
    trace.append(code_step("rules", started))

    return LeaseAnalysis(fields, review.data.escalation, rules, trace)
