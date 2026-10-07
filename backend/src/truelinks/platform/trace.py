"""What each step of an agent cost, so a slow or expensive one is visible."""

import time
from dataclasses import dataclass

from pydantic import BaseModel

from truelinks.platform.llm.types import StructuredResult


@dataclass(frozen=True)
class StepTrace:
    name: str
    model: str | None  # None for steps that are plain code
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0


def model_step[T: BaseModel](name: str, result: StructuredResult[T]) -> StepTrace:
    return StepTrace(
        name, result.model, result.duration_ms, result.input_tokens, result.output_tokens
    )


def code_step(name: str, started: float) -> StepTrace:
    return StepTrace(name, None, round((time.perf_counter() - started) * 1000))
