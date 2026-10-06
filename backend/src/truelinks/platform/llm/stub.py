from collections.abc import Callable
from typing import Any, Self

from pydantic import BaseModel

from truelinks.platform.llm.types import StructuredRequest, StructuredResult

# Produces the canned answer for one task. It receives the request so a module
# can return different answers per input (e.g. per sample lease).
type StubResolver = Callable[[StructuredRequest[Any]], object]


class StubProvider:
    """A provider that never calls a model.

    Domain modules register a resolver per task; the stub itself knows nothing
    about leases or issues. Answers are validated against the request schema,
    so a fixture that drifts from its schema fails loudly instead of passing
    bad data along.
    """

    name = "stub"

    def __init__(self) -> None:
        self._resolvers: dict[str, StubResolver] = {}

    def register(self, task: str, resolver: StubResolver) -> Self:
        self._resolvers[task] = resolver
        return self

    async def generate_structured[T: BaseModel](
        self, request: StructuredRequest[T]
    ) -> StructuredResult[T]:
        resolver = self._resolvers.get(request.task)
        if resolver is None:
            raise LookupError(f'StubProvider: no resolver registered for task "{request.task}"')

        data = request.schema.model_validate(resolver(request))

        return StructuredResult(
            data=data, model=self.name, duration_ms=0, input_tokens=0, output_tokens=0
        )
