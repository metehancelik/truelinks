import asyncio

import pytest
from pydantic import BaseModel, ValidationError

from truelinks.platform.llm.stub import StubProvider
from truelinks.platform.llm.types import StructuredRequest


class Answer(BaseModel):
    rent: float


def request(task: str = "demo") -> StructuredRequest[Answer]:
    return StructuredRequest(task=task, system="", prompt="", schema=Answer)


def test_returns_the_registered_answer_validated_against_the_schema() -> None:
    stub = StubProvider().register("demo", lambda _: {"rent": 9500})

    result = asyncio.run(stub.generate_structured(request()))

    assert result.data == Answer(rent=9500)


def test_unknown_task_fails_by_name_instead_of_returning_empty_data() -> None:
    with pytest.raises(LookupError, match='no resolver registered for task "demo"'):
        asyncio.run(StubProvider().generate_structured(request()))


def test_fixture_that_drifted_from_its_schema_fails() -> None:
    stub = StubProvider().register("demo", lambda _: {"rent": "a lot"})

    with pytest.raises(ValidationError):
        asyncio.run(stub.generate_structured(request()))
