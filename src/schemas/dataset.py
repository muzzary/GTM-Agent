import json
import unicodedata
from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal, Self

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from src.evaluation.phase6_quality import GroundedQualityReport
from src.schemas.base import StrictModel
from src.schemas.inference import (
    GroundedOutreachOutput,
    OutreachConstraints,
    SentenceSupportVerdict,
)


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    HELD_OUT = "held_out"


ScenarioKind = Literal["initial_outreach", "follow_up"]


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
    reviewed_at: AwareDatetime | None = Field(default=None, strict=False)
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


class DatasetManifestV2(StrictModel):
    dataset_id: str = Field(pattern=r"^dataset-[a-z0-9-]{4,64}$")
    dataset_version: str = Field(pattern=r"^\d+\.\d+$")
    examples: list["TrainingExampleV2"] = Field(min_length=1, max_length=2_000)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def content_hash_is_valid(self) -> Self:
        expected_hash = self.content_sha256_for_audit()
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected_hash)
        elif self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match v2 dataset manifest")
        return self

    def content_sha256_for_audit(self) -> str:
        return _content_digest_v2(
            self.model_dump(mode="json", exclude={"content_sha256"})
        )


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


class DatasetAuditReportV2(StrictModel):
    dataset_id: str
    passed: bool
    split_counts: dict[str, int]
    status_counts: dict[str, dict[str, int]]
    overlap_groups: list[str]
    duplicate_example_ids: list[str]
    duplicate_content_hashes: list[str]
    unsupported_claim_ids: list[str]
    unsupported_evidence_ids: list[str]
    benchmark_identity_overlap: list[str]
    benchmark_content_overlap: list[str]
    errors: list[str]


class IdentityGroups(StrictModel):
    product_group: str = Field(pattern=r"^product-[a-z0-9-]{4,64}$")
    icp_group: str = Field(min_length=1, max_length=120)
    company_group: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    prospect_group: str = Field(pattern=r"^prospect-[a-z0-9-]{4,64}$")


class ApprovedClaimRecord(StrictModel):
    claim_id: str = Field(pattern=r"^claim-[a-z0-9-]{3,64}$")
    text: str = Field(min_length=1, max_length=500)
    source_kind: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=500)
    license_kind: LicenseKind = Field(strict=False)
    license_basis: str = Field(min_length=1, max_length=500)
    license_url: HttpUrl | None = None

    @model_validator(mode="after")
    def public_source_has_license_url(self) -> Self:
        if self.license_kind is LicenseKind.PUBLIC_DATASET and self.license_url is None:
            raise ValueError("public claim source requires a license URL")
        return self


class EvidenceRecordV2(StrictModel):
    evidence_id: str = Field(pattern=r"^evidence-[a-z0-9-]{3,64}$")
    text: str = Field(min_length=1, max_length=2_000)
    source_url: HttpUrl
    collected_at: AwareDatetime = Field(strict=False)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_kind: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=500)
    license_kind: LicenseKind = Field(strict=False)
    license_basis: str = Field(min_length=1, max_length=500)
    license_url: HttpUrl | None = None

    @model_validator(mode="after")
    def public_source_has_license_url(self) -> Self:
        if self.license_kind is LicenseKind.PUBLIC_DATASET and self.license_url is None:
            raise ValueError("public evidence source requires a license URL")
        return self


class TrainingInputV2(StrictModel):
    target_role: str = Field(min_length=1, max_length=120)
    approved_claims: list[ApprovedClaimRecord] = Field(max_length=64)
    prospect_evidence: list[EvidenceRecordV2] = Field(max_length=64)
    pain_hypotheses: list[str] = Field(default_factory=list, max_length=16)
    constraints: OutreachConstraints

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> Self:
        claim_ids = [claim.claim_id for claim in self.approved_claims]
        evidence_ids = [evidence.evidence_id for evidence in self.prospect_evidence]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("approved claim IDs must be unique")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("prospect evidence IDs must be unique")
        return self


class TrainingProvenanceV2(StrictModel):
    source_kind: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=500)
    license_kind: LicenseKind = Field(strict=False)
    license_basis: str = Field(min_length=1, max_length=500)
    license_url: HttpUrl | None = None
    generation_method: GenerationMethod = Field(strict=False)
    reviewer_reference: str = Field(min_length=1, max_length=160)
    reviewed_at: AwareDatetime = Field(strict=False)

    @model_validator(mode="after")
    def public_source_has_license_url(self) -> Self:
        if self.license_kind is LicenseKind.PUBLIC_DATASET and self.license_url is None:
            raise ValueError("public dataset provenance requires a license URL")
        return self


class TrainingProvenanceCandidateV2(StrictModel):
    source_kind: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=500)
    license_kind: LicenseKind = Field(strict=False)
    license_basis: str = Field(min_length=1, max_length=500)
    license_url: HttpUrl | None = None
    generation_method: GenerationMethod = Field(strict=False)

    @model_validator(mode="after")
    def public_source_has_license_url(self) -> Self:
        if self.license_kind is LicenseKind.PUBLIC_DATASET and self.license_url is None:
            raise ValueError("public dataset provenance requires a license URL")
        return self


class TrainingExampleCandidateV2(StrictModel):
    example_id: str = Field(pattern=r"^dataset-example-[a-z0-9-]{4,64}$")
    schema_version: Literal["2.0"]
    task_type: Literal["outreach_generation"]
    intended_split: Literal["train", "validation"]
    scenario_kind: ScenarioKind
    product_name: str = Field(min_length=1, max_length=120)
    identity_groups: IdentityGroups
    prompt_template_version: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{3,63}$")
    input: TrainingInputV2
    proposed_output: GroundedOutreachOutput
    provenance: TrainingProvenanceCandidateV2
    gate_report: GroundedQualityReport
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def content_hash_is_valid(self) -> Self:
        expected_hash = self.content_sha256_for_audit()
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected_hash)
        elif self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match candidate example content")
        return self

    def content_sha256_for_audit(self) -> str:
        content = self.model_dump(mode="json", exclude={"content_sha256"})
        content.pop("example_id")
        return _content_digest_v2(content)


class DatasetCandidateManifestV2(StrictModel):
    dataset_id: str = Field(pattern=r"^dataset-[a-z0-9-]{4,64}$")
    dataset_version: str = Field(pattern=r"^\d+\.\d+$")
    lifecycle_status: Literal["pending_review"]
    examples: list[TrainingExampleCandidateV2] = Field(min_length=1, max_length=2_000)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def content_hash_is_valid(self) -> Self:
        expected_hash = self.content_sha256_for_audit()
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected_hash)
        elif self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match candidate manifest")
        return self

    def content_sha256_for_audit(self) -> str:
        return _content_digest_v2(
            self.model_dump(mode="json", exclude={"content_sha256"})
        )


class HumanRubricScores(StrictModel):
    personalization: int = Field(ge=1, le=5)
    grounding: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    differentiation: int = Field(ge=1, le=5)
    cta_quality: int = Field(ge=1, le=5)
    brand_fit: int = Field(ge=1, le=5)

    @property
    def average(self) -> float:
        return (
            sum(
                (
                    self.personalization,
                    self.grounding,
                    self.clarity,
                    self.differentiation,
                    self.cta_quality,
                    self.brand_fit,
                )
            )
            / 6
        )


class TrainingReviewV2(StrictModel):
    status: ReviewStatus = Field(strict=False)
    hard_gates_passed: bool
    support_verdicts: dict[str, SentenceSupportVerdict] = Field(max_length=64)
    scores: HumanRubricScores | None = None
    review_notes: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def reviewed_record_is_complete(self) -> Self:
        if self.status is ReviewStatus.REVIEWED and (
            not self.hard_gates_passed
            or self.scores is None
            or not all(verdict.approved for verdict in self.support_verdicts.values())
        ):
            raise ValueError(
                "reviewed record requires passed gates, scores, and positive verdicts"
            )
        return self


class TrainingExampleV2(StrictModel):
    example_id: str = Field(pattern=r"^dataset-example-[a-z0-9-]{4,64}$")
    schema_version: Literal["2.0"]
    split: DatasetSplit = Field(strict=False)
    task_type: Literal["outreach_generation"]
    scenario_kind: "ScenarioKind"
    product_name: str = Field(min_length=1, max_length=120)
    identity_groups: IdentityGroups
    prompt_template_version: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{3,63}$")
    input: TrainingInputV2
    approved_output: GroundedOutreachOutput
    provenance: TrainingProvenanceV2
    review: TrainingReviewV2
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def approved_training_record_is_consistent(self) -> Self:
        if self.split is DatasetSplit.TRAIN and (
            self.review.status is not ReviewStatus.REVIEWED
            or not self.review.hard_gates_passed
        ):
            raise ValueError("training split requires a reviewed hard-gate pass")

        claim_ids = {claim.claim_id for claim in self.input.approved_claims}
        evidence_ids = {
            evidence.evidence_id for evidence in self.input.prospect_evidence
        }
        used_claim_ids = {
            claim_id
            for item in self.approved_output.support_map
            for claim_id in item.claim_ids
        }
        used_evidence_ids = {
            evidence_id
            for item in self.approved_output.support_map
            for evidence_id in item.evidence_ids
        }
        if not used_claim_ids.issubset(claim_ids):
            raise ValueError("approved output uses a claim outside its input")
        if not used_evidence_ids.issubset(evidence_ids):
            raise ValueError("approved output uses evidence outside its input")

        supported_sentences = {
            item.sentence for item in self.approved_output.support_map
        }
        if self.review.status is ReviewStatus.REVIEWED and (
            set(self.review.support_verdicts) != supported_sentences
        ):
            raise ValueError("reviewed record must verdict every supported sentence")

        if self.review.status is ReviewStatus.REVIEWED:
            from src.evaluation.phase6_quality import evaluate_grounded_output

            gate_report = evaluate_grounded_output(
                self.approved_output,
                approved_claim_ids=claim_ids,
                approved_evidence_ids=evidence_ids,
                support_verdicts=self.review.support_verdicts,
                constraints=self.input.constraints,
            )
            if not gate_report.passed:
                raise ValueError("reviewed training record failed actual hard gates")

        expected_hash = self.content_sha256_for_audit()
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected_hash)
        elif self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match v2 example content")
        return self

    def content_sha256_for_audit(self) -> str:
        content = self.model_dump(
            mode="json",
            exclude={"content_sha256"},
        )
        content.pop("example_id")
        return _content_digest_v2(content)


def _content_digest(content: dict[str, Any]) -> str:
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _content_digest_v2(content: dict[str, Any]) -> str:
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    normalized = unicodedata.normalize("NFC", canonical)
    return sha256(normalized.encode("utf-8")).hexdigest()
