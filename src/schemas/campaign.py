from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from src.schemas.base import StrictModel


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class CampaignState(StrEnum):
    AWAITING_CLAIM_APPROVAL = "awaiting_claim_approval"
    AWAITING_PROSPECT_SELECTION = "awaiting_prospect_selection"
    PROSPECT_SELECTED = "prospect_selected"
    DRAFT_READY = "draft_ready"


class ClaimStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Uncertainty(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TraceEventType(StrEnum):
    CAMPAIGN_CREATED = "campaign_created"
    FIXTURE_RESEARCH_COMPLETED = "fixture_research_completed"
    CLAIMS_PROPOSED = "claims_proposed"
    CLAIMS_DECIDED = "claims_decided"
    PROSPECTS_RANKED = "prospects_ranked"
    PROSPECT_SELECTED = "prospect_selected"
    POSITIONING_PRODUCED = "positioning_produced"
    DRAFT_GENERATED = "draft_generated"
    DRAFT_VALIDATED = "draft_validated"
    DRAFT_EVALUATED = "draft_evaluated"


class ICPInput(StrictModel):
    industries: list[str] = Field(min_length=1, max_length=12)
    company_size: str = Field(min_length=1, max_length=80)
    roles: list[str] = Field(min_length=1, max_length=12)
    pain_hypotheses: list[str] = Field(min_length=1, max_length=12)


class CampaignInput(StrictModel):
    product_name: str = Field(min_length=1, max_length=120)
    product_url: HttpUrl | None = None
    short_description: str = Field(min_length=1, max_length=1_000)
    known_capabilities: list[str] = Field(min_length=1, max_length=24)
    known_limitations: list[str] = Field(default_factory=list, max_length=24)
    icp: ICPInput


class ProductProfile(StrictModel):
    product_id: str = Field(pattern=r"^product-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl | None = None
    short_description: str = Field(min_length=1, max_length=1_000)
    capabilities: tuple[str, ...] = Field(min_length=1, max_length=24)
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=24)


class ICPProfile(StrictModel):
    icp_id: str = Field(pattern=r"^icp-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    industries: tuple[str, ...] = Field(min_length=1, max_length=12)
    company_size: str = Field(min_length=1, max_length=80)
    roles: tuple[str, ...] = Field(min_length=1, max_length=12)
    pain_hypotheses: tuple[str, ...] = Field(min_length=1, max_length=12)


class EvidenceRecord(StrictModel):
    evidence_id: str = Field(pattern=r"^evidence-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    source_kind: str = Field(pattern=r"^fixture$")
    title: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=1_000)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    collected_at: AwareDatetime


class ProductClaim(StrictModel):
    claim_id: str = Field(pattern=r"^claim-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    product_id: str = Field(pattern=r"^product-[a-z0-9-]{4,64}$")
    text: str = Field(min_length=1, max_length=500)
    status: ClaimStatus = ClaimStatus.PENDING
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=12)
    uncertainty: Uncertainty


class ClaimDecision(StrictModel):
    claim_id: str = Field(pattern=r"^claim-[a-z0-9-]{4,64}$")
    decision: ApprovalDecision = Field(strict=False)


class ClaimDecisionBatch(StrictModel):
    decisions: list[ClaimDecision] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def claim_ids_must_be_unique(self) -> Self:
        claim_ids = [decision.claim_id for decision in self.decisions]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim decisions must contain unique claim IDs")
        return self


class ProspectCandidate(StrictModel):
    prospect_id: str = Field(pattern=r"^prospect-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    icp_id: str = Field(pattern=r"^icp-[a-z0-9-]{4,64}$")
    company: str = Field(min_length=1, max_length=160)
    industry: str = Field(min_length=1, max_length=120)
    target_role: str = Field(min_length=1, max_length=120)
    matched_icp_fields: tuple[str, ...] = Field(min_length=1, max_length=12)
    public_signals: tuple[str, ...] = Field(min_length=1, max_length=12)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=12)
    score: float = Field(ge=0, le=1)
    uncertainty: Uncertainty


class PositioningBrief(StrictModel):
    positioning_id: str = Field(pattern=r"^positioning-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    prospect_id: str = Field(pattern=r"^prospect-[a-z0-9-]{4,64}$")
    approved_claim_ids: tuple[str, ...] = Field(min_length=1, max_length=24)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=24)
    value_hypothesis: str = Field(min_length=1, max_length=1_000)


class OutreachDraft(StrictModel):
    draft_id: str = Field(pattern=r"^draft-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    prospect_id: str = Field(pattern=r"^prospect-[a-z0-9-]{4,64}$")
    positioning_id: str = Field(pattern=r"^positioning-[a-z0-9-]{4,64}$")
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4_000)
    claim_ids: tuple[str, ...] = Field(min_length=1, max_length=24)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=24)


class ApprovalRecord(StrictModel):
    approval_id: str = Field(pattern=r"^approval-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    claim_id: str = Field(pattern=r"^claim-[a-z0-9-]{4,64}$")
    decision: ApprovalDecision
    decided_at: AwareDatetime


class EvaluationCheck(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    passed: bool
    reason: str = Field(min_length=1, max_length=500)


class EvaluationResult(StrictModel):
    evaluation_id: str = Field(pattern=r"^evaluation-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    draft_id: str = Field(pattern=r"^draft-[a-z0-9-]{4,64}$")
    passed: bool
    checks: list[EvaluationCheck] = Field(min_length=1, max_length=16)
    evaluated_at: AwareDatetime


class TraceEvent(StrictModel):
    event_id: str = Field(pattern=r"^trace-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    sequence: int = Field(ge=1)
    event_type: TraceEventType
    occurred_at: AwareDatetime
    input_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    output_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    summary: str = Field(min_length=1, max_length=500)


class Campaign(StrictModel):
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    state: CampaignState
    product: ProductProfile
    icp: ICPProfile
    evidence: tuple[EvidenceRecord, ...] = Field(default_factory=tuple, max_length=64)
    claims: tuple[ProductClaim, ...] = Field(default_factory=tuple, max_length=24)
    approvals: tuple[ApprovalRecord, ...] = Field(default_factory=tuple, max_length=24)
    prospects: tuple[ProspectCandidate, ...] = Field(
        default_factory=tuple,
        max_length=24,
    )
    selected_prospect_id: str | None = Field(
        default=None,
        pattern=r"^prospect-[a-z0-9-]{4,64}$",
    )
    positioning: PositioningBrief | None = None
    draft: OutreachDraft | None = None
    evaluation: EvaluationResult | None = None
    trace: tuple[TraceEvent, ...] = Field(default_factory=tuple, max_length=128)
    created_at: AwareDatetime
    updated_at: AwareDatetime
