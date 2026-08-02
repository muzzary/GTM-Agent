from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from src.runtime.fixtures import DeterministicFixturePipeline
from src.schemas.campaign import (
    ApprovalDecision,
    ApprovalRecord,
    Campaign,
    CampaignInput,
    CampaignState,
    ClaimDecisionBatch,
    ClaimStatus,
    ICPProfile,
    ProductProfile,
    TraceEvent,
    TraceEventType,
)

NewId = Callable[[str], str]
Clock = Callable[[], datetime]


class CampaignNotFoundError(LookupError):
    pass


class WorkflowConflictError(ValueError):
    pass


class InMemoryCampaignRepository:
    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}

    def save(self, campaign: Campaign) -> None:
        self._campaigns[campaign.campaign_id] = campaign.model_copy(deep=True)

    def get(self, campaign_id: str) -> Campaign:
        campaign = self._campaigns.get(campaign_id)
        if campaign is None:
            raise CampaignNotFoundError(f"campaign not found: {campaign_id}")
        return campaign.model_copy(deep=True)


class CampaignWorkflow:
    def __init__(
        self,
        *,
        repository: InMemoryCampaignRepository,
        pipeline: DeterministicFixturePipeline,
        new_id: NewId | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._pipeline = pipeline
        self._new_id = new_id or _random_id
        self._clock = clock or _utc_now

    def create_campaign(self, campaign_input: CampaignInput) -> Campaign:
        campaign_id = self._new_id("campaign")
        product = ProductProfile(
            product_id=self._new_id("product"),
            campaign_id=campaign_id,
            name=campaign_input.product_name,
            url=campaign_input.product_url,
            short_description=campaign_input.short_description,
            capabilities=tuple(campaign_input.known_capabilities),
            limitations=tuple(campaign_input.known_limitations),
        )
        icp = ICPProfile(
            icp_id=self._new_id("icp"),
            campaign_id=campaign_id,
            industries=tuple(campaign_input.icp.industries),
            company_size=campaign_input.icp.company_size,
            roles=tuple(campaign_input.icp.roles),
            pain_hypotheses=tuple(campaign_input.icp.pain_hypotheses),
        )
        created_at = self._clock()
        evidence, claims = self._pipeline.research_product(
            campaign_id=campaign_id,
            product=product,
            new_id=self._new_id,
            collected_at=self._clock(),
        )
        trace = (
            self._trace_event(
                campaign_id,
                1,
                TraceEventType.CAMPAIGN_CREATED,
                input_ids=(product.product_id, icp.icp_id),
                output_ids=(campaign_id,),
                summary="Campaign accepted for deterministic fixture processing.",
            ),
            self._trace_event(
                campaign_id,
                2,
                TraceEventType.FIXTURE_RESEARCH_COMPLETED,
                input_ids=(product.product_id, icp.icp_id),
                output_ids=tuple(item.evidence_id for item in evidence),
                summary="Fixture product research created submitted-input evidence.",
            ),
            self._trace_event(
                campaign_id,
                3,
                TraceEventType.CLAIMS_PROPOSED,
                input_ids=tuple(item.evidence_id for item in evidence),
                output_ids=tuple(claim.claim_id for claim in claims),
                summary="Fixture product claims are awaiting user decisions.",
            ),
        )
        campaign = Campaign(
            campaign_id=campaign_id,
            state=CampaignState.AWAITING_CLAIM_APPROVAL,
            product=product,
            icp=icp,
            evidence=evidence,
            claims=claims,
            trace=trace,
            created_at=created_at,
            updated_at=trace[-1].occurred_at,
        )
        self._repository.save(campaign)
        return campaign.model_copy(deep=True)

    def decide_claims(
        self,
        campaign_id: str,
        batch: ClaimDecisionBatch,
    ) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        self._require_state(
            campaign,
            CampaignState.AWAITING_CLAIM_APPROVAL,
            "decide claims",
        )
        proposed_ids = {claim.claim_id for claim in campaign.claims}
        decision_ids = {decision.claim_id for decision in batch.decisions}
        if proposed_ids != decision_ids:
            raise WorkflowConflictError(
                "claim decisions must cover every proposed claim exactly once"
            )
        if not any(
            decision.decision is ApprovalDecision.APPROVED
            for decision in batch.decisions
        ):
            raise WorkflowConflictError("at least one claim must be approved")

        decisions = {
            decision.claim_id: decision.decision for decision in batch.decisions
        }
        approvals = tuple(
            ApprovalRecord(
                approval_id=self._new_id("approval"),
                campaign_id=campaign_id,
                claim_id=claim.claim_id,
                decision=decisions[claim.claim_id],
                decided_at=self._clock(),
            )
            for claim in campaign.claims
        )
        decided_claims = tuple(
            claim.model_copy(
                update={
                    "status": (
                        ClaimStatus.APPROVED
                        if decisions[claim.claim_id] is ApprovalDecision.APPROVED
                        else ClaimStatus.REJECTED
                    )
                }
            )
            for claim in campaign.claims
        )
        prospect_evidence, prospects = self._pipeline.rank_prospects(
            campaign_id=campaign_id,
            icp=campaign.icp,
            new_id=self._new_id,
            collected_at=self._clock(),
        )
        decision_event = self._trace_event(
            campaign_id,
            len(campaign.trace) + 1,
            TraceEventType.CLAIMS_DECIDED,
            input_ids=tuple(claim.claim_id for claim in campaign.claims),
            output_ids=tuple(item.approval_id for item in approvals),
            summary="Every proposed claim received an explicit user decision.",
        )
        ranking_event = self._trace_event(
            campaign_id,
            decision_event.sequence + 1,
            TraceEventType.PROSPECTS_RANKED,
            input_ids=(
                campaign.icp.icp_id,
                *(
                    claim.claim_id
                    for claim in decided_claims
                    if claim.status is ClaimStatus.APPROVED
                ),
            ),
            output_ids=(
                *(prospect.prospect_id for prospect in prospects),
                *(item.evidence_id for item in prospect_evidence),
            ),
            summary="Fixture prospects were ranked from submitted ICP fields.",
        )
        updated = campaign.model_copy(
            update={
                "state": CampaignState.AWAITING_PROSPECT_SELECTION,
                "claims": decided_claims,
                "approvals": approvals,
                "evidence": campaign.evidence + prospect_evidence,
                "prospects": prospects,
                "trace": campaign.trace + (decision_event, ranking_event),
                "updated_at": ranking_event.occurred_at,
            },
            deep=True,
        )
        self._repository.save(updated)
        return updated.model_copy(deep=True)

    def select_prospect(self, campaign_id: str, prospect_id: str) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        self._require_state(
            campaign,
            CampaignState.AWAITING_PROSPECT_SELECTION,
            "select a prospect",
        )
        if prospect_id not in {item.prospect_id for item in campaign.prospects}:
            raise WorkflowConflictError(
                "selected prospect must be ranked for this campaign"
            )
        event = self._trace_event(
            campaign_id,
            len(campaign.trace) + 1,
            TraceEventType.PROSPECT_SELECTED,
            input_ids=tuple(item.prospect_id for item in campaign.prospects),
            output_ids=(prospect_id,),
            summary="User selected one ranked fixture prospect.",
        )
        updated = campaign.model_copy(
            update={
                "state": CampaignState.PROSPECT_SELECTED,
                "selected_prospect_id": prospect_id,
                "trace": campaign.trace + (event,),
                "updated_at": event.occurred_at,
            },
            deep=True,
        )
        self._repository.save(updated)
        return updated.model_copy(deep=True)

    def generate_draft(self, campaign_id: str) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        self._require_state(
            campaign,
            CampaignState.PROSPECT_SELECTED,
            "generate a draft",
        )
        selected = next(
            prospect
            for prospect in campaign.prospects
            if prospect.prospect_id == campaign.selected_prospect_id
        )
        approved_claims = tuple(
            claim for claim in campaign.claims if claim.status is ClaimStatus.APPROVED
        )
        positioning = self._pipeline.position(
            campaign_id=campaign_id,
            product=campaign.product,
            icp=campaign.icp,
            approved_claims=approved_claims,
            prospect=selected,
            new_id=self._new_id,
        )
        draft = self._pipeline.generate_draft(
            campaign_id=campaign_id,
            product=campaign.product,
            icp=campaign.icp,
            prospect=selected,
            positioning=positioning,
            approved_claims=approved_claims,
            new_id=self._new_id,
        )
        self._validate_draft(
            campaign,
            draft.claim_ids,
            draft.evidence_ids,
            selected.prospect_id,
        )
        evaluation = self._pipeline.evaluate(
            campaign_id=campaign_id,
            draft=draft,
            approved_claims=approved_claims,
            evidence=campaign.evidence,
            selected_prospect=selected,
            new_id=self._new_id,
            evaluated_at=self._clock(),
        )
        if not evaluation.passed:
            raise WorkflowConflictError("fixture draft failed deterministic evaluation")

        events = (
            self._trace_event(
                campaign_id,
                len(campaign.trace) + 1,
                TraceEventType.POSITIONING_PRODUCED,
                input_ids=(
                    selected.prospect_id,
                    *(claim.claim_id for claim in approved_claims),
                ),
                output_ids=(positioning.positioning_id,),
                summary=(
                    "Positioning used approved claims and the selected prospect."
                ),
            ),
            self._trace_event(
                campaign_id,
                len(campaign.trace) + 2,
                TraceEventType.DRAFT_GENERATED,
                input_ids=(positioning.positioning_id,),
                output_ids=(draft.draft_id,),
                summary="Deterministic fixture generation produced a draft.",
            ),
            self._trace_event(
                campaign_id,
                len(campaign.trace) + 3,
                TraceEventType.DRAFT_VALIDATED,
                input_ids=(draft.draft_id,),
                output_ids=(draft.draft_id,),
                summary=(
                    "Draft references resolved approved claims, evidence, and prospect."
                ),
            ),
            self._trace_event(
                campaign_id,
                len(campaign.trace) + 4,
                TraceEventType.DRAFT_EVALUATED,
                input_ids=(draft.draft_id,),
                output_ids=(evaluation.evaluation_id,),
                summary="Draft passed every deterministic Phase 2 evaluation check.",
            ),
        )
        updated = campaign.model_copy(
            update={
                "state": CampaignState.DRAFT_READY,
                "positioning": positioning,
                "draft": draft,
                "evaluation": evaluation,
                "trace": campaign.trace + events,
                "updated_at": events[-1].occurred_at,
            },
            deep=True,
        )
        self._repository.save(updated)
        return updated.model_copy(deep=True)

    def get_campaign(self, campaign_id: str) -> Campaign:
        return self._repository.get(campaign_id)

    def list_prospects(self, campaign_id: str):
        return self.get_campaign(campaign_id).prospects

    def get_trace(self, campaign_id: str) -> tuple[TraceEvent, ...]:
        return self.get_campaign(campaign_id).trace

    def _trace_event(
        self,
        campaign_id: str,
        sequence: int,
        event_type: TraceEventType,
        *,
        input_ids: tuple[str, ...],
        output_ids: tuple[str, ...],
        summary: str,
    ) -> TraceEvent:
        return TraceEvent(
            event_id=self._new_id("trace"),
            campaign_id=campaign_id,
            sequence=sequence,
            event_type=event_type,
            occurred_at=self._clock(),
            input_ids=input_ids,
            output_ids=output_ids,
            summary=summary,
        )

    @staticmethod
    def _require_state(
        campaign: Campaign,
        required: CampaignState,
        action: str,
    ) -> None:
        if campaign.state is not required:
            raise WorkflowConflictError(
                f"cannot {action} while campaign is {campaign.state.value}"
            )

    @staticmethod
    def _validate_draft(
        campaign: Campaign,
        claim_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        prospect_id: str,
    ) -> None:
        approved_ids = {
            claim.claim_id
            for claim in campaign.claims
            if claim.status is ClaimStatus.APPROVED
        }
        if not claim_ids or not set(claim_ids) <= approved_ids:
            raise WorkflowConflictError("draft contains an unapproved product claim")
        available_evidence = {item.evidence_id for item in campaign.evidence}
        if not evidence_ids or not set(evidence_ids) <= available_evidence:
            raise WorkflowConflictError("draft contains unresolved evidence")
        if prospect_id != campaign.selected_prospect_id:
            raise WorkflowConflictError("draft does not target the selected prospect")


def _random_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(UTC)
