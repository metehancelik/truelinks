"""Layer 3 of verification: a second model pass that judges meaning.

Code can tell that a quote exists and contains the value. It cannot tell that
the quote is about the deposit rather than the rent, that two clauses disagree,
or that "as mutually agreed" is not a rent escalation mechanism. This pass can.

It only raises concerns. It never changes an extracted value: a person decides.
"""

from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from truelinks.modules.lease.rules import EscalationAssessment
from truelinks.modules.lease.schema import LeaseExtraction
from truelinks.modules.lease.verification import FieldStatus, VerificationIssue, VerifiedField
from truelinks.platform.llm.types import LLMProvider, StructuredRequest, StructuredResult

LEASE_REVIEW_TASK = "lease.review"


# The evaluator may only raise the issues that need judgement.
type ConcernKind = Literal[
    VerificationIssue.WRONG_SOURCE,
    VerificationIssue.CONTRADICTION,
    VerificationIssue.IMPLAUSIBLE,
]


class Concern(BaseModel):
    field: str = Field(description="Name of the field the concern is about, exactly as given")
    kind: ConcernKind
    explanation: str = Field(description="One sentence a property owner can act on")

    @field_validator("field")
    @classmethod
    def _must_be_a_lease_field(cls, name: str) -> str:
        if name not in LeaseExtraction.model_fields:
            raise ValueError(f'"{name}" is not a lease field')
        return name


class LeaseReview(BaseModel):
    escalation_is_defined: bool | None = Field(
        description="Whether the escalation clause satisfies the owner's rule. "
        "Null when the record has no escalation clause."
    )
    escalation_reason: str = Field(
        description="One sentence naming the mechanism, or what is missing"
    )
    concerns: list[Concern] = Field(
        description="Problems a person should check. Empty when there are none."
    )

    @property
    def escalation(self) -> EscalationAssessment | None:
        if self.escalation_is_defined is None:
            return None
        return EscalationAssessment(self.escalation_is_defined, self.escalation_reason)


SYSTEM_PROMPT = """\
You review a structured record that was extracted from a residential lease. \
You are given the lease and, for each field, the extracted value and the quote it was taken from.

Report a concern only when something is actually wrong:
- WRONG_SOURCE: the quote is about a different field than the one it is attached to. \
For example a deposit sentence quoted as evidence for the rent, even when the numbers are equal.
- CONTRADICTION: the lease states two different values for the same thing.
- IMPLAUSIBLE: the value looks wrong on its face, such as an expiry date before the start date.

Do not report missing fields, do not restate the record, and do not correct any value. \
A clean record is the normal case: return an empty list of concerns.

Then judge the rent escalation clause against the owner's rule, which is given with the record.
"""


async def review_lease(
    llm: LLMProvider,
    lease_text: str,
    fields: list[VerifiedField],
    escalation_rule: str,
) -> StructuredResult[LeaseReview]:
    record = "\n".join(
        f"- {field.name}: value={field.value!r} quote={field.quote!r}" for field in fields
    )
    prompt = (
        f"<lease>\n{lease_text}\n</lease>\n\n"
        f"<record>\n{record}\n</record>\n\n"
        f"<owner_rule>\n{escalation_rule}\n</owner_rule>"
    )
    return await llm.generate_structured(
        StructuredRequest(
            task=LEASE_REVIEW_TASK, system=SYSTEM_PROMPT, prompt=prompt, schema=LeaseReview
        )
    )


def apply_concerns(fields: list[VerifiedField], concerns: list[Concern]) -> list[VerifiedField]:
    """Downgrade each VERIFIED field the evaluator raised a concern about.

    A field is trusted only when both the code checks and the evaluator accept
    it. A field the code already rejected keeps its own, deterministic reason.
    """
    by_field: dict[str, Concern] = {}
    for concern in concerns:
        by_field.setdefault(concern.field, concern)

    return [
        replace(
            field,
            status=FieldStatus.UNVERIFIED,
            issue=by_field[field.name].kind,
            explanation=by_field[field.name].explanation,
        )
        if field.name in by_field and field.status is FieldStatus.VERIFIED
        else field
        for field in fields
    ]
