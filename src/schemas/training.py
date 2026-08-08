from typing import Literal

from pydantic import Field

from src.schemas.base import StrictModel


class TrainingConfig(StrictModel):
    config_version: Literal["1.0"]
    base_model_id: str = Field(min_length=1, max_length=200)
    base_model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    adapter_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{3,63}$")
    seed: int = Field(ge=0, le=2**31 - 1)
    max_length: int = Field(ge=128, le=4096)
    epochs: int = Field(ge=1, le=10)
    max_steps: int = Field(ge=1, le=1000)
    learning_rate: float = Field(gt=0, lt=1)
    lora_rank: int = Field(ge=1, le=64)
    lora_alpha: int = Field(ge=1, le=256)
    lora_dropout: float = Field(ge=0, le=1)
    target_modules: str = Field(min_length=1, max_length=200)
