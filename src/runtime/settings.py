from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_env: Literal["development", "test", "production"] = "development"
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)
    research_contact: str | None = Field(default=None, min_length=3, max_length=200)
    research_cache_path: Path = Path("data/research-cache.sqlite3")
    crm_path: Path = Path("data/crm.sqlite3")
    brave_search_api_key: SecretStr | None = None
    translation_endpoint: str | None = None
    translation_api_key: SecretStr | None = None

    @field_validator("research_contact")
    @classmethod
    def contact_must_be_header_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if "\r" in value or "\n" in value:
            raise ValueError("research contact cannot contain line breaks")
        return value

    @field_validator("research_cache_path")
    @classmethod
    def cache_must_stay_in_local_data(cls, value: Path) -> Path:
        if value.is_absolute() or not value.parts or value.parts[0] != "data":
            raise ValueError("research cache path must be relative and under data/")
        if ".." in value.parts:
            raise ValueError("research cache path cannot traverse directories")
        return value

    @field_validator("crm_path")
    @classmethod
    def crm_must_stay_in_local_data(cls, value: Path) -> Path:
        if value.is_absolute() or not value.parts or value.parts[0] != "data":
            raise ValueError("CRM path must be relative and under data/")
        if ".." in value.parts:
            raise ValueError("CRM path cannot traverse directories")
        return value

    @field_validator("translation_endpoint")
    @classmethod
    def translation_endpoint_must_be_https(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("translation endpoint must be an absolute HTTPS URL")
        return value

    @model_validator(mode="after")
    def translation_configuration_must_be_paired(self) -> Self:
        if (self.translation_endpoint is None) != (self.translation_api_key is None):
            raise ValueError(
                "translation endpoint and API key must be configured together"
            )
        return self

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
            crm_path=values.get("GTM_CRM_PATH", "data/crm.sqlite3"),
            brave_search_api_key=values.get("GTM_BRAVE_SEARCH_API_KEY") or None,
            translation_endpoint=values.get("GTM_TRANSLATION_ENDPOINT") or None,
            translation_api_key=values.get("GTM_TRANSLATION_API_KEY") or None,
        )
