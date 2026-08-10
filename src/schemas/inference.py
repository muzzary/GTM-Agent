import re
from typing import Literal, Self

from pydantic import Field, model_validator

from src.schemas.base import StrictModel


class ModelIdentity(StrictModel):
    model_id: str = Field(min_length=3, max_length=200)
    model_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    adapter_id: str | None = Field(default=None, min_length=3, max_length=200)
    adapter_revision: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
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


class OutreachConstraints(StrictModel):
    subject_min_words: int = Field(default=1, ge=1, le=6)
    subject_max_words: int = Field(default=6, ge=1, le=6)
    body_min_words: int = Field(default=25, ge=25, le=150)
    body_max_words: int = Field(default=150, ge=25, le=150)
    cta_count: Literal[1] = 1

    @model_validator(mode="after")
    def bounds_are_ordered(self) -> Self:
        if self.subject_min_words > self.subject_max_words:
            raise ValueError("subject word bounds are out of order")
        if self.body_min_words > self.body_max_words:
            raise ValueError("body word bounds are out of order")
        return self


class SupportMapEntry(StrictModel):
    sentence: str = Field(min_length=1, max_length=500)
    role: Literal["prospect_fact", "product_claim", "hypothesis", "cta"]
    claim_ids: list[str] = Field(default_factory=list, max_length=16)
    evidence_ids: list[str] = Field(default_factory=list, max_length=16)
    cta_kind: Literal["interest_question", "approved_offer"] | None = None

    @model_validator(mode="after")
    def sentence_and_role_are_structured(self) -> Self:
        terminal_groups = re.findall(r"[.!?]+(?:\s|$)", self.sentence)
        if len(terminal_groups) != 1 or not re.search(r"[.!?]+$", self.sentence):
            raise ValueError("support map entry must contain exactly one sentence")
        if self.role == "cta":
            if self.cta_kind is None or not self.sentence.endswith("?"):
                raise ValueError("CTA requires a kind and must be a question")
        elif self.cta_kind is not None:
            raise ValueError("CTA kind is only valid for CTA sentences")
        if self.claim_ids != sorted(set(self.claim_ids)):
            raise ValueError("support map claim IDs must be unique and sorted")
        if self.evidence_ids != sorted(set(self.evidence_ids)):
            raise ValueError("support map evidence IDs must be unique and sorted")
        return self


class SentenceSupportVerdict(StrictModel):
    role: Literal["prospect_fact", "product_claim", "hypothesis", "cta"]
    claim_ids: list[str] = Field(default_factory=list, max_length=16)
    evidence_ids: list[str] = Field(default_factory=list, max_length=16)
    cta_kind: Literal["interest_question", "approved_offer"] | None = None
    mentions_offer: bool
    approved: bool

    @model_validator(mode="after")
    def identifiers_are_canonical(self) -> Self:
        if self.claim_ids != sorted(set(self.claim_ids)):
            raise ValueError("verdict claim IDs must be unique and sorted")
        if self.evidence_ids != sorted(set(self.evidence_ids)):
            raise ValueError("verdict evidence IDs must be unique and sorted")
        return self


class GroundedOutreachOutput(StrictModel):
    generation_status: Literal[
        "drafted", "needs_more_evidence", "disqualified", "opted_out"
    ]
    subject: str = Field(max_length=120)
    body: str = Field(max_length=4_000)
    support_map: list[SupportMapEntry] = Field(default_factory=list, max_length=32)
    uncertainty_notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def content_matches_generation_status(self) -> Self:
        if self.generation_status == "drafted":
            if not self.subject or not self.body or not self.support_map:
                raise ValueError(
                    "drafted output requires subject, body, and support map"
                )
            mapped_body = " ".join(item.sentence for item in self.support_map)
            if self.body != mapped_body:
                raise ValueError("body must exactly match support map sentences")
            sentences = [item.sentence for item in self.support_map]
            if len(sentences) != len(set(sentences)):
                raise ValueError("support map sentences must be unique")
        elif self.subject or self.body or self.support_map:
            raise ValueError("non-draft status must not contain outreach copy")
        elif not self.uncertainty_notes:
            raise ValueError("non-draft status requires an uncertainty note")
        elif any(not note.strip() for note in self.uncertainty_notes):
            raise ValueError("uncertainty note must not be empty")
        return self


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
