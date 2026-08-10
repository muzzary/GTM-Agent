import json
import unicodedata
from hashlib import sha256
from typing import Any, Literal, Self

from pydantic import AwareDatetime, Field, model_validator
from pydantic.networks import HttpUrl

from src.schemas.base import StrictModel
from src.schemas.dataset import IdentityGroups, TrainingInputV2
from src.schemas.inference import OutreachConstraints

ProductCategory = Literal[
    "reporting_automation",
    "security_asset_inventory",
    "developer_productivity",
    "support_knowledge_workflow",
    "crm_data_hygiene",
]
IcpPattern = Literal[
    "regulated_mid_market",
    "distributed_operations",
    "high_growth_software",
    "professional_services",
    "enterprise_transformation",
]
RoleTier = Literal["individual_contributor", "manager", "director", "vp", "c_level"]
EvidenceCondition = Literal["strong", "weak", "conflicting", "stale", "absent"]
GenerationStatus = Literal[
    "drafted", "needs_more_evidence", "disqualified", "opted_out"
]
ScenarioKind = Literal["initial_outreach", "follow_up"]
AdversarialTag = Literal[
    "unsupported_fact_combination",
    "invented_pain",
    "false_citation",
    "fake_offer",
    "invasive_personalization",
    "stale_evidence",
    "conflicting_evidence",
    "opt_out_signal",
    "disqualification_signal",
]


class Phase6BenchmarkCase(StrictModel):
    case_id: str = Field(pattern=r"^case-phase6-[a-z0-9-]{3,64}$")
    schema_version: Literal["2.0"]
    task_type: Literal["outreach_generation"]
    product_category: ProductCategory
    icp_pattern: IcpPattern
    role_tier: RoleTier
    evidence_condition: EvidenceCondition
    scenario_kind: ScenarioKind
    identity_groups: IdentityGroups
    product_name: str = Field(min_length=1, max_length=120)
    input: TrainingInputV2
    expected_generation_status: GenerationStatus
    required_claim_ids: list[str] = Field(default_factory=list, max_length=64)
    required_evidence_ids: list[str] = Field(default_factory=list, max_length=64)
    adversarial_tags: list[AdversarialTag] = Field(default_factory=list, max_length=16)
    protected_adversarial: bool = False
    review_status: Literal["pending", "reviewed"]
    reviewer_reference: str | None = Field(default=None, min_length=1, max_length=160)
    reviewed_at: AwareDatetime | None = Field(default=None, strict=False)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def expected_behavior_is_consistent(self) -> Self:
        if self.review_status == "reviewed" and (
            self.reviewer_reference is None or self.reviewed_at is None
        ):
            raise ValueError("reviewed benchmark cases require reviewer provenance")
        if self.review_status == "pending" and (
            self.reviewer_reference is not None or self.reviewed_at is not None
        ):
            raise ValueError("pending benchmark cases cannot claim reviewer provenance")
        if self.required_claim_ids != sorted(set(self.required_claim_ids)):
            raise ValueError("required claim IDs must be unique and sorted")
        if self.required_evidence_ids != sorted(set(self.required_evidence_ids)):
            raise ValueError("required evidence IDs must be unique and sorted")
        if self.adversarial_tags != sorted(set(self.adversarial_tags)):
            raise ValueError("adversarial tags must be unique and sorted")
        if self.protected_adversarial and not self.adversarial_tags:
            raise ValueError("protected adversarial cases require a classification tag")

        claim_ids = {claim.claim_id for claim in self.input.approved_claims}
        evidence_ids = {
            evidence.evidence_id for evidence in self.input.prospect_evidence
        }
        for evidence in self.input.prospect_evidence:
            if evidence.content_sha256 != _text_digest(evidence.text):
                raise ValueError(
                    f"evidence content hash does not match {evidence.evidence_id}"
                )
        sourced_items = [
            *self.input.approved_claims,
            *self.input.prospect_evidence,
        ]
        if any(
            item.source_kind != "first_party_synthetic"
            or item.license_kind.value != "synthetic"
            for item in sourced_items
        ):
            raise ValueError(
                "benchmark claims and evidence require controlled synthetic provenance"
            )
        if not set(self.required_claim_ids).issubset(claim_ids):
            raise ValueError("required claim IDs must exist in the case input")
        if not set(self.required_evidence_ids).issubset(evidence_ids):
            raise ValueError("required evidence IDs must exist in the case input")

        is_draft = self.expected_generation_status == "drafted"
        if is_draft and not self.required_claim_ids:
            raise ValueError("drafted cases require at least one approved claim")
        if not is_draft and (self.required_claim_ids or self.required_evidence_ids):
            raise ValueError("non-draft cases cannot require output citations")
        if "opt_out_signal" in self.adversarial_tags and (
            self.expected_generation_status != "opted_out"
        ):
            raise ValueError("opt_out_signal requires an opted_out status")
        if self.expected_generation_status == "opted_out" and (
            "opt_out_signal" not in self.adversarial_tags
        ):
            raise ValueError("opted_out cases require an opt_out_signal")
        if "disqualification_signal" in self.adversarial_tags and (
            self.expected_generation_status != "disqualified"
        ):
            raise ValueError("disqualification_signal requires a disqualified status")
        if self.expected_generation_status == "disqualified" and (
            "disqualification_signal" not in self.adversarial_tags
        ):
            raise ValueError("disqualified cases require a disqualification_signal")
        if self.expected_generation_status == "needs_more_evidence" and (
            self.evidence_condition == "strong"
        ):
            raise ValueError("needs_more_evidence cannot use strong evidence")

        expected_hash = self.content_sha256_for_audit()
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected_hash)
        elif self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match benchmark case content")
        return self

    def prompt_input(self) -> "Phase6BenchmarkPromptInput":
        return Phase6BenchmarkPromptInput(
            task_type=self.task_type,
            scenario_kind=self.scenario_kind,
            product_name=self.product_name,
            target_role=self.input.target_role,
            approved_claims=[
                Phase6BenchmarkPromptClaim(
                    claim_id=claim.claim_id,
                    text=claim.text,
                )
                for claim in self.input.approved_claims
            ],
            prospect_evidence=[
                Phase6BenchmarkPromptEvidence(
                    evidence_id=evidence.evidence_id,
                    text=evidence.text,
                    source_url=evidence.source_url,
                    collected_at=evidence.collected_at,
                )
                for evidence in self.input.prospect_evidence
            ],
            pain_hypotheses=self.input.pain_hypotheses,
            constraints=self.input.constraints,
        )

    def content_sha256_for_audit(self) -> str:
        content = self.model_dump(mode="json", exclude={"content_sha256"})
        content.pop("case_id")
        return _content_digest(content)


class Phase6BenchmarkManifest(StrictModel):
    benchmark_id: str = Field(pattern=r"^benchmark-[a-z0-9-]{4,64}$")
    manifest_version: Literal["2.0"]
    lifecycle_status: Literal["pending_review", "frozen"]
    frozen_at: AwareDatetime | None = Field(default=None, strict=False)
    reviewer_reference: str | None = Field(default=None, min_length=1, max_length=160)
    cases: list[Phase6BenchmarkCase] = Field(min_length=60, max_length=100)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def content_hash_is_valid(self) -> Self:
        if self.lifecycle_status == "frozen" and (
            self.frozen_at is None
            or self.reviewer_reference is None
            or any(case.review_status != "reviewed" for case in self.cases)
        ):
            raise ValueError("frozen benchmark requires completed manual review")
        if self.lifecycle_status == "pending_review" and (
            self.frozen_at is not None or self.reviewer_reference is not None
        ):
            raise ValueError("pending benchmark cannot claim frozen reviewer metadata")
        expected_hash = self.content_sha256_for_audit()
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected_hash)
        elif self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match benchmark manifest")
        return self

    def content_sha256_for_audit(self) -> str:
        return _content_digest(self.model_dump(mode="json", exclude={"content_sha256"}))


class Phase6BenchmarkAuditReport(StrictModel):
    benchmark_id: str
    passed: bool
    evaluation_ready: bool
    total_cases: int = Field(ge=0)
    adversarial_case_count: int = Field(ge=0)
    status_counts: dict[str, int]
    coverage_counts: dict[str, int]
    duplicate_case_ids: list[str]
    duplicate_content_hashes: list[str]
    duplicate_identity_groups: list[str]
    blocked_identity_overlap: list[str]
    blocked_case_overlap: list[str]
    errors: list[str]


class Phase6BenchmarkPromptClaim(StrictModel):
    claim_id: str = Field(pattern=r"^claim-[a-z0-9-]{3,64}$")
    text: str = Field(min_length=1, max_length=500)


class Phase6BenchmarkPromptEvidence(StrictModel):
    evidence_id: str = Field(pattern=r"^evidence-[a-z0-9-]{3,64}$")
    text: str = Field(min_length=1, max_length=2_000)
    source_url: HttpUrl
    collected_at: AwareDatetime = Field(strict=False)


class Phase6BenchmarkPromptInput(StrictModel):
    task_type: Literal["outreach_generation"]
    scenario_kind: ScenarioKind
    product_name: str = Field(min_length=1, max_length=120)
    target_role: str = Field(min_length=1, max_length=120)
    approved_claims: list[Phase6BenchmarkPromptClaim] = Field(max_length=64)
    prospect_evidence: list[Phase6BenchmarkPromptEvidence] = Field(max_length=64)
    pain_hypotheses: list[str] = Field(default_factory=list, max_length=16)
    constraints: OutreachConstraints


def _content_digest(content: dict[str, Any]) -> str:
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    normalized = unicodedata.normalize("NFC", canonical)
    return sha256(normalized.encode("utf-8")).hexdigest()


def _text_digest(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return sha256(normalized.encode("utf-8")).hexdigest()
