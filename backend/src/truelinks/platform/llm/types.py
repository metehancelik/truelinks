"""The only door to a model.

Domain modules depend on `LLMProvider`, never on a vendor SDK, so the stub,
a local Ollama and a hosted API are interchangeable.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


@dataclass(frozen=True)
class LLMImage:
    """An image passed to a vision-capable model."""

    media_type: str
    data: bytes


@dataclass(frozen=True)
class StructuredRequest[T: BaseModel]:
    """One model call that must return data matching `schema`.

    `task` is a stable name (e.g. "lease.extract") used for tracing and for
    picking a canned answer in the stub provider.
    """

    task: str
    system: str
    prompt: str
    schema: type[T]
    images: Sequence[LLMImage] = ()


@dataclass(frozen=True)
class StructuredResult[T: BaseModel]:
    data: T
    model: str
    duration_ms: int
    input_tokens: int
    output_tokens: int


class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def generate_structured[T: BaseModel](
        self, request: StructuredRequest[T]
    ) -> StructuredResult[T]: ...
