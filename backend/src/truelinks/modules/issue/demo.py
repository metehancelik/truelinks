"""Canned assessments for demo mode (`LLM_PROVIDER=stub`).

The stub cannot see, so the answer is chosen from the reporter's note. Each
one refers to photo 1, which every report has.
"""

from typing import Any

from truelinks.modules.issue.pipeline import ISSUE_ASSESS_TASK
from truelinks.platform.llm.stub import StubProvider
from truelinks.platform.llm.types import StructuredRequest

AC_LEAK: dict[str, Any] = {
    "overall_condition": "damaged",
    "damages": [
        {
            "description": "Water is dripping from the indoor AC unit onto the wall below.",
            "photo": 1,
        },
        {"description": "Brown water staining on the wall under the unit.", "photo": 1},
    ],
    "equipment": [{"name": "split AC indoor unit", "condition": "damaged", "photo": 1}],
    "work_order": {
        "title": "AC unit leaking water onto wall",
        "description": (
            "The indoor AC unit is leaking and has stained the wall beneath it. "
            "Clear the condensate drain, check the drain pan, then repaint the stained area."
        ),
        "urgency": "high",
    },
}

WATER_HEATER: dict[str, Any] = {
    "overall_condition": "worn",
    "damages": [
        {"description": "Rust and scale around the water heater's lower fittings.", "photo": 1}
    ],
    "equipment": [{"name": "electric water heater", "condition": "worn", "photo": 1}],
    "work_order": {
        "title": "Inspect corroded water heater",
        "description": (
            "The water heater shows rust at its lower fittings, a sign of a slow leak. "
            "Inspect the tank and valves, and replace the unit if the tank is corroded."
        ),
        "urgency": "medium",
    },
}

GENERAL: dict[str, Any] = {
    "overall_condition": "worn",
    "damages": [
        {"description": "Cracked and peeling paint with a visible stain on the wall.", "photo": 1}
    ],
    "equipment": [{"name": "painted interior wall", "condition": "worn", "photo": 1}],
    "work_order": {
        "title": "Repair and repaint damaged wall",
        "description": (
            "The wall has cracked, peeling paint and a stain. "
            "Check for moisture behind it, repair the plaster and repaint."
        ),
        "urgency": "low",
    },
}

_BY_KEYWORD: dict[str, dict[str, Any]] = {
    "ac": AC_LEAK,
    "air con": AC_LEAK,
    "cooling": AC_LEAK,
    "heater": WATER_HEATER,
    "hot water": WATER_HEATER,
}


def _answer(request: StructuredRequest[Any]) -> dict[str, Any]:
    note = request.prompt.lower().split("reporter's note:")[-1]
    words = note.replace(",", " ").replace(".", " ")
    for keyword, answer in _BY_KEYWORD.items():
        if f" {keyword} " in f" {words} ":
            return answer
    return GENERAL


def register_demo_issues(stub: StubProvider) -> StubProvider:
    return stub.register(ISSUE_ASSESS_TASK, _answer)
