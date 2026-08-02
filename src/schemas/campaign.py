from enum import StrEnum

from pydantic import AwareDatetime, Field, HttpUrl

from src.schemas.base import StrictModel


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


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
