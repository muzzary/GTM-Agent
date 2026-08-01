from collections.abc import Mapping
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_env: Literal["development", "test", "production"] = "development"
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Self:
        return cls(
            app_env=values.get("GTM_APP_ENV", "development"),
            api_host=values.get("GTM_API_HOST", "127.0.0.1"),
            api_port=values.get("GTM_API_PORT", "8000"),
        )
