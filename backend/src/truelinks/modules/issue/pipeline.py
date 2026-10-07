"""The issue agent: look at the photos, check its own references, draft a work order."""

import time
from dataclasses import dataclass
from enum import StrEnum

from truelinks.modules.issue.schema import IssueAssessment
from truelinks.modules.unit.records import Unit
from truelinks.platform.llm.types import LLMImage, LLMProvider, StructuredRequest
from truelinks.platform.trace import StepTrace, code_step, model_step

ISSUE_ASSESS_TASK = "issue.assess"

SYSTEM_PROMPT = """\
You inspect photos of a rental unit that a tenant or inspector sent with an issue report, \
and you prepare a draft work order for the property owner.

Rules:
- Describe only what the photos show. Do not infer damage you cannot see.
- For every damage and every piece of equipment, give the number of the photo that shows it. \
Photos are numbered in the order given, starting at 1.
- Condition is one of: new, good, worn (aged but working), damaged (broken, leaking, unsafe).
- The work order must address what the reporter described. If the photos do not show the \
reported problem, say so in the description and ask for an inspection instead of guessing.
- Urgency is high for water leaks, electrical faults and anything unsafe; low for cosmetic wear.
"""


class IssueFlag(StrEnum):
    """Something a person should look at before trusting the assessment."""

    # A finding points at a photo that was not sent: possibly invented.
    INVALID_PHOTO_REFERENCE = "INVALID_PHOTO_REFERENCE"
    # A problem was reported but the photos show no damage.
    NO_VISIBLE_DAMAGE = "NO_VISIBLE_DAMAGE"


@dataclass(frozen=True)
class IssueAnalysis:
    assessment: IssueAssessment
    flags: list[IssueFlag]
    trace: list[StepTrace]


async def assess_issue(
    llm: LLMProvider, unit: Unit, note: str, photos: list[LLMImage]
) -> IssueAnalysis:
    prompt = (
        f"Unit: {unit.label}, {unit.building_name} ({unit.unit_type})\n"
        f"Photos attached: {len(photos)}\n"
        f"Reporter's note: {note or '(none)'}"
    )
    result = await llm.generate_structured(
        StructuredRequest(
            task=ISSUE_ASSESS_TASK,
            system=SYSTEM_PROMPT,
            prompt=prompt,
            schema=IssueAssessment,
            images=photos,
        )
    )
    trace = [model_step("assess", result)]

    started = time.perf_counter()
    flags = check_assessment(result.data, photo_count=len(photos))
    trace.append(code_step("check", started))

    return IssueAnalysis(result.data, flags, trace)


def check_assessment(assessment: IssueAssessment, photo_count: int) -> list[IssueFlag]:
    """Deterministic checks on the model's answer."""
    flags: list[IssueFlag] = []

    references = [item.photo for item in (*assessment.damages, *assessment.equipment)]
    if any(not 1 <= photo <= photo_count for photo in references):
        flags.append(IssueFlag.INVALID_PHOTO_REFERENCE)

    if not assessment.damages:
        flags.append(IssueFlag.NO_VISIBLE_DAMAGE)

    return flags
