import time

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent, NativeOutput
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from truelinks.platform.llm.config import LLMSettings
from truelinks.platform.llm.types import StructuredRequest, StructuredResult


class OpenAICompatibleProvider:
    """Talks to any OpenAI-compatible chat endpoint through Pydantic AI.

    Pydantic AI handles the wire format, JSON-schema constrained output and
    validation, and re-asks the model with the validation error when its
    answer does not fit the schema. This class only maps our request onto it.
    """

    name = "openai-compatible"

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._provider = OpenAIProvider(base_url=settings.base_url, api_key=settings.api_key)

    async def generate_structured[T: BaseModel](
        self, request: StructuredRequest[T]
    ) -> StructuredResult[T]:
        started = time.perf_counter()
        model_id = self._settings.model_for(has_images=bool(request.images))

        agent = Agent(
            OpenAIChatModel(model_id, provider=self._provider),
            output_type=NativeOutput(request.schema),
            instructions=request.system,
            model_settings=self._model_settings(),
        )
        images = [BinaryContent(data=i.data, media_type=i.media_type) for i in request.images]
        result = await agent.run([request.prompt, *images])

        usage = result.usage
        return StructuredResult(
            data=result.output,
            model=model_id,
            duration_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

    def _model_settings(self) -> OpenAIChatModelSettings:
        settings = OpenAIChatModelSettings(temperature=self._settings.temperature)
        if self._settings.reasoning_effort:
            # Passed through the request body so any value the endpoint
            # understands (e.g. Ollama's "none") is accepted.
            settings["extra_body"] = {"reasoning_effort": self._settings.reasoning_effort}
        return settings
