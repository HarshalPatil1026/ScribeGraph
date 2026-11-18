"""Application settings, read from environment variables and an optional ``.env`` file.

Nested settings use a double underscore, for example ``llm__api_key`` or
``r2__bucket_name``. Variable names are case-insensitive.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = PACKAGE_DIR.parent
DEFAULT_SITE_DIR = PACKAGE_DIR / "web"

# Groq retired llama-3.3-70b-versatile for free and developer accounts on 2026-08-16
# and recommends openai/gpt-oss-120b as the replacement.
DEFAULT_MODEL = "openai/gpt-oss-120b"


class ConfigError(RuntimeError):
    """A required setting is missing or invalid."""


class LLMSettings(BaseModel):
    api_key: str = ""
    model_name: str = DEFAULT_MODEL
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_retries: int = Field(default=2, ge=0)
    timeout: float = Field(default=120.0, gt=0, description="Request timeout in seconds.")


class R2Settings(BaseModel):
    account_id: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    bucket_name: str = ""

    @property
    def configured(self) -> bool:
        return all((self.account_id, self.access_key_id, self.secret_access_key, self.bucket_name))


class StorageSettings(BaseModel):
    # "auto" uses Cloudflare R2 when all r2__* values are set, otherwise the local site folder.
    backend: Literal["auto", "local", "r2"] = "auto"
    local_dir: Path = DEFAULT_SITE_DIR


class ContentAPISettings(BaseModel):
    tavily_api_key: str = ""
    guardian_api_key: str = ""


class PipelineSettings(BaseModel):
    max_revisions: int = Field(default=3, ge=0, le=10)
    history_size: int = Field(default=5, ge=0, le=50)


class Settings(BaseSettings):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    r2: R2Settings = Field(default_factory=R2Settings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    content: ContentAPISettings = Field(default_factory=ContentAPISettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)

    # The conventional variable name, accepted as an alias for llm__api_key.
    groq_api_key: str = Field(default="", exclude=True, repr=False)

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _apply_fallbacks(self) -> Settings:
        if not self.llm.api_key and self.groq_api_key:
            self.llm.api_key = self.groq_api_key
        return self

    @property
    def storage_backend(self) -> Literal["local", "r2"]:
        if self.storage.backend == "auto":
            return "r2" if self.r2.configured else "local"
        return self.storage.backend


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings. Call ``get_settings.cache_clear()`` after changing env vars."""
    return Settings()
