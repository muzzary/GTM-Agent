from typing import Literal, Self

from pydantic import Field, model_validator

from src.schemas.base import StrictModel


class ModelIdentity(StrictModel):
    model_id: str = Field(min_length=3, max_length=200)
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    adapter_id: str | None = Field(default=None, min_length=3, max_length=200)
    adapter_revision: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{40}$",
    )

    @model_validator(mode="after")
    def adapter_fields_must_be_paired(self) -> Self:
        if (self.adapter_id is None) != (self.adapter_revision is None):
            raise ValueError(
                "adapter_id and adapter_revision must be provided together"
            )
        return self


class GenerationSettings(StrictModel):
    do_sample: Literal[False] = False
    max_new_tokens: int = Field(ge=1, le=1024)
    seed: int = Field(ge=0, le=2**32 - 1)


class OutreachOutput(StrictModel):
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)
    claims_used: list[str] = Field(default_factory=list, max_length=64)
    evidence_used: list[str] = Field(default_factory=list, max_length=64)
    uncertainty_notes: list[str] = Field(default_factory=list, max_length=32)


class RuntimeMetadata(StrictModel):
    python_version: str = Field(min_length=3, max_length=40)
    torch_version: str = Field(min_length=1, max_length=80)
    transformers_version: str = Field(min_length=1, max_length=80)
    cuda_version: str | None = Field(default=None, max_length=80)
    gpu_name: str = Field(min_length=1, max_length=200)
    gpu_memory_mb: int = Field(gt=0, le=1_000_000)
    latency_ms: float = Field(ge=0, le=86_400_000)


class InferenceRequest(StrictModel):
    contract_version: Literal["1.0"] = "1.0"
    request_id: str = Field(pattern=r"^req_[a-z0-9]{12,64}$")
    prompt: str = Field(min_length=1, max_length=12_000)
    approved_claim_ids: list[str] = Field(default_factory=list, max_length=64)
    max_new_tokens: int = Field(default=256, ge=1, le=1024)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)


class InferenceResponse(StrictModel):
    contract_version: Literal["1.0"] = "1.0"
    request_id: str = Field(pattern=r"^req_[a-z0-9]{12,64}$")
    model: ModelIdentity
    generation: GenerationSettings
    output: OutreachOutput
    runtime: RuntimeMetadata


class InferenceResultBundle(StrictModel):
    bundle_version: Literal["1.0"] = "1.0"
    payload: InferenceResponse
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
