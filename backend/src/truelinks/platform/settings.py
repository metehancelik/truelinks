from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/truelinks/platform/settings.py -> repository root
_REPO_ROOT = Path(__file__).parents[4]


class AppSettings(BaseSettings):
    """Application settings, read from the environment or `.env`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite needs no setup; Docker Compose points this at Postgres.
    database_url: str = "sqlite:///./truelinks.db"
    # The owner's ruleset and unit records, and the bundled sample leases.
    data_dir: Path = _REPO_ROOT / "data"
    samples_dir: Path = _REPO_ROOT / "samples"
    # Where reported photos are kept. A mounted volume in Docker.
    uploads_dir: Path = _REPO_ROOT / "backend" / "uploads"
    # "stub" serves canned answers for the bundled samples: a demo with no model.
    llm_provider: Literal["openai-compatible", "stub"] = "openai-compatible"
    # Every row carries a tenant. One owner today; the column is what keeps
    # a second one from seeing the first one's leases.
    tenant_id: str = "marina-crest"
