from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_env: Literal["development", "test", "production"] = "development"
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)
    research_contact: str | None = Field(default=None, min_length=3, max_length=200)
    research_cache_path: Path = Path("data/research-cache.sqlite3")

    @field_validator("research_contact")
    @classmethod
    def contact_must_be_header_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if "\r" in value or "\n" in value:
            raise ValueError("research contact cannot contain line breaks")
        return value

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Self:
        return cls(
            app_env=values.get("GTM_APP_ENV", "development"),
            api_host=values.get("GTM_API_HOST", "127.0.0.1"),
            api_port=values.get("GTM_API_PORT", "8000"),
            research_contact=values.get("GTM_RESEARCH_CONTACT") or None,
            research_cache_path=values.get(
                "GTM_RESEARCH_CACHE_PATH", "data/research-cache.sqlite3"
            ),
        )
