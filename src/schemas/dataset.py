import json
from enum import StrEnum
from hashlib import sha256
from typing import Any, Self

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from src.schemas.base import StrictModel


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    HELD_OUT = "held_out"


class LicenseKind(StrEnum):
    SYNTHETIC = "synthetic"
    PUBLIC_DATASET = "public_dataset"


class GenerationMethod(StrEnum):
    HUMAN_AUTHORED = "human_authored"
    TEACHER_MODEL = "teacher_model"
    TEMPLATE = "template"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class TrainingExample(StrictModel):
    example_id: str = Field(pattern=r"^dataset-example-[a-z0-9-]{4,64}$")
    split: DatasetSplit = Field(strict=False)
    product_group: str = Field(pattern=r"^product-[a-z0-9-]{4,64}$")
    icp_group: str = Field(min_length=1, max_length=120)
    company_group: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    prospect_group: str = Field(pattern=r"^prospect-[a-z0-9-]{4,64}$")
    product_name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=12_000)
    target_subject: str = Field(min_length=1, max_length=120)
    target_body: str = Field(min_length=1, max_length=4_000)
    approved_claim_ids: list[str] = Field(min_length=1, max_length=64)
    personalization_evidence_ids: list[str] = Field(min_length=1, max_length=64)
    source_kind: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=500)
    license_kind: LicenseKind = Field(strict=False)
    license_basis: str = Field(min_length=1, max_length=500)
    license_url: HttpUrl | None = None
    generation_method: GenerationMethod = Field(strict=False)
    reviewer_status: ReviewStatus = Field(strict=False)
    reviewer_reference: str | None = Field(default=None, max_length=160)
    reviewed_at: AwareDatetime | None = None
    relevance: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    differentiation: int = Field(ge=1, le=5)
    credibility: int = Field(ge=1, le=5)
    cta_quality: int = Field(ge=1, le=5)
    brand_fit: int = Field(ge=1, le=5)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    benchmark_case_id: str | None = Field(
        default=None, pattern=r"^case-[a-z0-9-]{3,64}$"
    )

    @model_validator(mode="before")
    @classmethod
    def populate_content_hash(cls, value: Any) -> Any:
        if not isinstance(value, dict) or value.get("content_sha256"):
            return value
        content = {
            key: value.get(key)
            for key in (
                "prompt",
                "target_subject",
                "target_body",
                "approved_claim_ids",
                "personalization_evidence_ids",
            )
        }
        return {**value, "content_sha256": _content_digest(content)}

    @model_validator(mode="after")
    def provenance_is_complete(self) -> Self:
        if self.license_kind is LicenseKind.PUBLIC_DATASET and self.license_url is None:
            raise ValueError("public dataset examples require a license URL")
        if self.reviewer_status is ReviewStatus.REVIEWED and (
            self.reviewer_reference is None or self.reviewed_at is None
        ):
            raise ValueError("reviewed examples require reviewer provenance")
        if self.content_sha256 != self.content_sha256_for_audit():
            raise ValueError("content_sha256 does not match example content")
        return self

    def content_sha256_for_audit(self) -> str:
        return _content_digest(
            {
                "prompt": self.prompt,
                "target_subject": self.target_subject,
                "target_body": self.target_body,
                "approved_claim_ids": self.approved_claim_ids,
                "personalization_evidence_ids": self.personalization_evidence_ids,
            }
        )


class DatasetManifest(StrictModel):
    dataset_id: str = Field(pattern=r"^dataset-[a-z0-9-]{4,64}$")
    dataset_version: str = Field(pattern=r"^\d+\.\d+$")
    claim_catalog: list[str] = Field(min_length=1, max_length=256)
    evidence_catalog: list[str] = Field(min_length=1, max_length=256)
    examples: list[TrainingExample] = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def catalogs_are_unique(self) -> Self:
        if len(self.claim_catalog) != len(set(self.claim_catalog)):
            raise ValueError("claim catalog IDs must be unique")
        if len(self.evidence_catalog) != len(set(self.evidence_catalog)):
            raise ValueError("evidence catalog IDs must be unique")
        return self


class DatasetAuditReport(StrictModel):
    dataset_id: str
    passed: bool
    split_counts: dict[str, int]
    overlap_groups: list[str]
    duplicate_example_ids: list[str]
    duplicate_content_hashes: list[str]
    unsupported_claim_ids: list[str]
    unsupported_evidence_ids: list[str]
    benchmark_overlap: list[str]
    errors: list[str]


def _content_digest(content: dict[str, Any]) -> str:
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()
