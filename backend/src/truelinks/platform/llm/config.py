from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """Model settings, read from `LLM_*` environment variables or `.env`.

    Defaults target a local Ollama. Point the same variables at any
    OpenAI-compatible endpoint to switch models without touching code.
    """

    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    text_model: str = "gemma4:12b"
    # Used when a request carries images. Empty means "same as text_model".
    vision_model: str = ""
    # 0 so the same document yields the same extraction.
    temperature: float = 0.0
    # Sent as `reasoning_effort`. "none" switches thinking off on local models;
    # set it empty for models that reject the parameter.
    reasoning_effort: str = "none"

    def model_for(self, *, has_images: bool) -> str:
        return (self.vision_model or self.text_model) if has_images else self.text_model
