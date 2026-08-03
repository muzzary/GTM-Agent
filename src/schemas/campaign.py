import re
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    AwareDatetime,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from src.schemas.base import StrictModel

Text120 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Text200 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Text500 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Text1000 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)
]

_DISALLOWED_CONTROL = re.compile(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]")


def _normalize_unique_items(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    normalized: list[Any] = []
    for item in value:
        if not isinstance(item, str):
            normalized.append(item)
            continue
        item = item.strip()
        if _DISALLOWED_CONTROL.search(item) or "\n" in item or "\r" in item:
            raise ValueError(
                "list items cannot contain control characters or line breaks"
            )
        normalized.append(item)
    if len(normalized) != len(
        set(item for item in normalized if isinstance(item, str))
    ):
        raise ValueError("list items must be unique after normalization")
    return normalized


def _reject_control_characters(value: Any) -> Any:
    if isinstance(value, str) and _DISALLOWED_CONTROL.search(value):
        raise ValueError("text cannot contain control characters")
    return value


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ClaimWordingSource(StrEnum):
    PROPOSED = "proposed"
    USER_EDITED = "user_edited"


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
    industries: list[Text120] = Field(min_length=1, max_length=12)
    company_size: Text120
    roles: list[Text120] = Field(min_length=1, max_length=12)
    pain_hypotheses: list[Text500] = Field(min_length=1, max_length=12)

    _normalize_lists = field_validator(
        "industries", "roles", "pain_hypotheses", mode="before"
    )(_normalize_unique_items)
    _safe_company_size = field_validator("company_size", mode="before")(
        _reject_control_characters
    )


class CampaignInput(StrictModel):
    product_name: Text120
    product_url: HttpUrl | None = None
    short_description: Text1000
    known_capabilities: list[Text200] = Field(min_length=1, max_length=24)
    known_limitations: list[Text200] = Field(default_factory=list, max_length=24)
    icp: ICPInput

    _normalize_lists = field_validator(
        "known_capabilities", "known_limitations", mode="before"
    )(_normalize_unique_items)
    _safe_text = field_validator("product_name", "short_description", mode="before")(
        _reject_control_characters
    )


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
    edited_text: Text500 | None = None
    evidence_attested: bool = False

    _safe_edit = field_validator("edited_text", mode="before")(
        _reject_control_characters
    )

    @model_validator(mode="after")
    def edit_requires_approval_and_attestation(self) -> Self:
        if self.decision is ApprovalDecision.REJECTED:
            if self.edited_text is not None or self.evidence_attested:
                raise ValueError("rejected claim cannot include an edit or attestation")
        elif self.edited_text is not None and not self.evidence_attested:
            raise ValueError("edited claim requires evidence attestation")
        elif self.edited_text is None and self.evidence_attested:
            raise ValueError("unchanged approval cannot include evidence attestation")
        return self


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
    approval_ids: tuple[str, ...] = Field(min_length=1, max_length=24)
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
    approval_ids: tuple[str, ...] = Field(min_length=1, max_length=24)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=24)


class ApprovalRecord(StrictModel):
    approval_id: str = Field(pattern=r"^approval-[a-z0-9-]{4,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    claim_id: str = Field(pattern=r"^claim-[a-z0-9-]{4,64}$")
    decision: ApprovalDecision
    original_text: Text500
    reviewed_text: Text500
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=12)
    wording_source: ClaimWordingSource
    evidence_attested: bool
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def review_provenance_must_be_consistent(self) -> Self:
        changed = self.reviewed_text != self.original_text
        if self.decision is ApprovalDecision.REJECTED:
            if changed or self.wording_source is not ClaimWordingSource.PROPOSED:
                raise ValueError("rejected approval must retain proposed wording")
            if self.evidence_attested:
                raise ValueError("rejected approval cannot attest edited wording")
        elif self.wording_source is ClaimWordingSource.USER_EDITED:
            if not changed or not self.evidence_attested:
                raise ValueError(
                    "edited approval must change wording and attest its evidence"
                )
        elif changed or self.evidence_attested:
            raise ValueError("proposed approval must retain proposed wording")
        return self


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

    @model_validator(mode="after")
    def provenance_references_must_resolve(self) -> Self:
        if self.product.campaign_id != self.campaign_id:
            raise ValueError("product must belong to the campaign")
        if self.icp.campaign_id != self.campaign_id:
            raise ValueError("ICP must belong to the campaign")

        evidence = {item.evidence_id: item for item in self.evidence}
        claims = {item.claim_id: item for item in self.claims}
        approvals = {item.approval_id: item for item in self.approvals}
        prospects = {item.prospect_id: item for item in self.prospects}
        for items, index, label in (
            (self.evidence, evidence, "evidence"),
            (self.claims, claims, "claim"),
            (self.approvals, approvals, "approval"),
            (self.prospects, prospects, "prospect"),
        ):
            if len(items) != len(index):
                raise ValueError(f"campaign contains duplicate {label} IDs")

        for item in self.evidence:
            if item.campaign_id != self.campaign_id:
                raise ValueError("evidence must belong to the campaign")
        for claim in self.claims:
            if (
                claim.campaign_id != self.campaign_id
                or claim.product_id != self.product.product_id
            ):
                raise ValueError("claim must belong to the campaign product")
            if not set(claim.evidence_ids) <= evidence.keys():
                raise ValueError("claim evidence must resolve in the campaign")
        for prospect in self.prospects:
            if (
                prospect.campaign_id != self.campaign_id
                or prospect.icp_id != self.icp.icp_id
            ):
                raise ValueError("prospect must belong to the campaign ICP")
            if not set(prospect.evidence_ids) <= evidence.keys():
                raise ValueError("prospect evidence must resolve in the campaign")

        if self.approvals:
            approval_by_claim = {item.claim_id: item for item in self.approvals}
            if len(approval_by_claim) != len(self.approvals) or set(
                approval_by_claim
            ) != set(claims):
                raise ValueError(
                    "approvals must cover every campaign claim exactly once"
                )
            for claim_id, approval in approval_by_claim.items():
                claim = claims[claim_id]
                expected_status = (
                    ClaimStatus.APPROVED
                    if approval.decision is ApprovalDecision.APPROVED
                    else ClaimStatus.REJECTED
                )
                if approval.campaign_id != self.campaign_id:
                    raise ValueError("approval must belong to the campaign")
                if approval.original_text != claim.text:
                    raise ValueError("approval original wording must match its claim")
                if approval.evidence_ids != claim.evidence_ids:
                    raise ValueError("approval evidence must match its claim")
                if claim.status is not expected_status:
                    raise ValueError("claim status must match its approval")

        approved_records = {
            item.approval_id: item
            for item in self.approvals
            if item.decision is ApprovalDecision.APPROVED
        }
        if self.positioning is not None:
            self._validate_authorized_output(
                self.positioning.campaign_id,
                self.positioning.prospect_id,
                self.positioning.approved_claim_ids,
                self.positioning.approval_ids,
                approved_records,
                prospects,
            )
        if self.draft is not None:
            self._validate_authorized_output(
                self.draft.campaign_id,
                self.draft.prospect_id,
                self.draft.claim_ids,
                self.draft.approval_ids,
                approved_records,
                prospects,
            )
            if (
                self.positioning is None
                or self.draft.positioning_id != self.positioning.positioning_id
            ):
                raise ValueError("draft positioning must resolve in the campaign")
        return self

    def _validate_authorized_output(
        self,
        owner_id: str,
        prospect_id: str,
        claim_ids: tuple[str, ...],
        approval_ids: tuple[str, ...],
        approved_records: dict[str, ApprovalRecord],
        prospects: dict[str, ProspectCandidate],
    ) -> None:
        if owner_id != self.campaign_id or prospect_id not in prospects:
            raise ValueError("downstream output must belong to the campaign")
        if len(claim_ids) != len(approval_ids):
            raise ValueError("claim and approval references must be paired")
        if len(set(approval_ids)) != len(approval_ids):
            raise ValueError("downstream approval IDs must be unique")
        for claim_id, approval_id in zip(claim_ids, approval_ids, strict=True):
            approval = approved_records.get(approval_id)
            if approval is None or approval.claim_id != claim_id:
                raise ValueError("downstream output references an unauthorized claim")
