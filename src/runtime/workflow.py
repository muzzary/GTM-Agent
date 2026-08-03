import re
from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol
from uuid import uuid4

from src.data.http_collector import ResearchCollectionError
from src.data.source_policy import SourcePolicyError
from src.research.discovery import DiscoveryResult
from src.research.prospect import ProspectResearchResult
from src.runtime.fixtures import DeterministicFixturePipeline
from src.schemas.campaign import (
    ApprovalDecision,
    ApprovalRecord,
    Campaign,
    CampaignInput,
    CampaignState,
    ClaimDecisionBatch,
    ClaimStatus,
    ClaimWordingSource,
    ICPProfile,
    ProductProfile,
    ProspectCandidate,
    ResearchOutcome,
    TraceEvent,
    TraceEventType,
)
from src.schemas.research import (
    ProspectResearchRequest,
    ResearchRequest,
    ResearchRun,
    ResearchStage,
    ResearchStatus,
)

NewId = Callable[[str], str]
Clock = Callable[[], datetime]


class CampaignNotFoundError(LookupError):
    pass


class WorkflowConflictError(ValueError):
    pass


class ResearchUnavailableError(RuntimeError):
    pass


class ResearchExecutionError(RuntimeError):
    def __init__(self, code: str, run_id: str) -> None:
        self.code = code
        self.run_id = run_id
        super().__init__(f"public research failed: {code}")


class DiscoveryRunner(Protocol):
    def run(
        self,
        *,
        campaign_id: str,
        icp: ICPProfile,
        run_id: str,
        seed_urls: tuple[str, ...],
        new_id: NewId,
        now: datetime,
    ) -> DiscoveryResult: ...


class ProspectResearchRunner(Protocol):
    def research(
        self,
        *,
        campaign_id: str,
        prospect: ProspectCandidate,
        run_id: str,
        new_id: NewId,
        now: datetime,
    ) -> ProspectResearchResult: ...


class InMemoryCampaignRepository:
    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}

    def save(self, campaign: Campaign) -> None:
        validated = Campaign.model_validate(campaign.model_dump())
        self._campaigns[campaign.campaign_id] = validated.model_copy(deep=True)

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
        discovery_runner: DiscoveryRunner | None = None,
        prospect_research_runner: ProspectResearchRunner | None = None,
        new_id: NewId | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._pipeline = pipeline
        self._discovery_runner = discovery_runner
        self._prospect_research_runner = prospect_research_runner
        self._new_id = new_id or _random_id
        self._clock = clock or _utc_now
        self._mutation_lock = RLock()
        self._active_research_campaigns: set[str] = set()

    def create_campaign(self, campaign_input: CampaignInput) -> Campaign:
        with self._mutation_lock:
            return self._create_campaign(campaign_input)

    def _create_campaign(self, campaign_input: CampaignInput) -> Campaign:
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
            regions=tuple(campaign_input.icp.regions),
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
        with self._mutation_lock:
            return self._decide_claims(campaign_id, batch)

    def _decide_claims(
        self,
        campaign_id: str,
        batch: ClaimDecisionBatch,
    ) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        if campaign.state is not CampaignState.AWAITING_CLAIM_APPROVAL:
            if self._matches_locked_decisions(campaign, batch):
                return campaign
            raise WorkflowConflictError("claim decisions are already locked")
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

        decisions = {decision.claim_id: decision for decision in batch.decisions}
        for claim in campaign.claims:
            decision = decisions[claim.claim_id]
            if decision.edited_text == claim.text:
                raise WorkflowConflictError(
                    f"edited wording must change proposed claim {claim.claim_id}"
                )
        approvals = tuple(
            ApprovalRecord(
                approval_id=self._new_id("approval"),
                campaign_id=campaign_id,
                claim_id=claim.claim_id,
                decision=decisions[claim.claim_id].decision,
                original_text=claim.text,
                reviewed_text=decisions[claim.claim_id].edited_text or claim.text,
                evidence_ids=claim.evidence_ids,
                wording_source=(
                    ClaimWordingSource.USER_EDITED
                    if decisions[claim.claim_id].edited_text is not None
                    else ClaimWordingSource.PROPOSED
                ),
                evidence_attested=decisions[claim.claim_id].evidence_attested,
                decided_at=self._clock(),
            )
            for claim in campaign.claims
        )
        decided_claims = tuple(
            claim.model_copy(
                update={
                    "status": (
                        ClaimStatus.APPROVED
                        if decisions[claim.claim_id].decision
                        is ApprovalDecision.APPROVED
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

    def run_discovery(
        self,
        campaign_id: str,
        request: ResearchRequest,
    ) -> ResearchOutcome:
        if self._discovery_runner is None:
            raise ResearchUnavailableError(
                "live research requires GTM_RESEARCH_CONTACT configuration"
            )
        with self._mutation_lock:
            campaign = self.get_campaign(campaign_id)
            existing = self._find_request(campaign, request.request_id)
            if existing is not None:
                if existing.stage is not ResearchStage.DISCOVERY:
                    raise WorkflowConflictError(
                        "research request ID is already used by another stage"
                    )
                if existing.status is ResearchStatus.FAILED:
                    raise ResearchExecutionError(
                        existing.failure_code or "source_failure",
                        existing.run_id,
                    )
                return ResearchOutcome(run=existing, campaign=campaign)
            self._require_state(
                campaign,
                CampaignState.AWAITING_PROSPECT_SELECTION,
                "run prospect discovery",
            )
            if len(campaign.icp.industries) > 3:
                raise WorkflowConflictError(
                    "live discovery supports at most three ICP industries"
                )
            self._begin_research(campaign, ResearchStage.DISCOVERY)
            snapshot = campaign
            run_id = self._new_id("research-run")
            started_at = self._clock()
        try:
            result = self._discovery_runner.run(
                campaign_id=campaign_id,
                icp=campaign.icp,
                run_id=run_id,
                seed_urls=tuple(str(url) for url in request.market_seed_urls),
                new_id=self._new_id,
                now=self._clock(),
            )
        except (ResearchCollectionError, SourcePolicyError) as error:
            code = self._safe_failure_code(error)
            try:
                self._persist_failed_run(
                    campaign_id=campaign_id,
                    request_id=request.request_id,
                    run_id=run_id,
                    stage=ResearchStage.DISCOVERY,
                    prospect_id=None,
                    started_at=started_at,
                    code=code,
                    snapshot=snapshot,
                )
            finally:
                with self._mutation_lock:
                    self._active_research_campaigns.discard(campaign_id)
            raise ResearchExecutionError(code, run_id) from error
        except Exception:
            with self._mutation_lock:
                self._active_research_campaigns.discard(campaign_id)
            raise

        with self._mutation_lock:
            try:
                current = self.get_campaign(campaign_id)
                self._require_unchanged(current, snapshot)
                if len(current.evidence) + len(result.evidence) > 64:
                    raise WorkflowConflictError("campaign evidence capacity reached")
                if len(current.collection_attempts) + len(result.attempts) > 64:
                    raise WorkflowConflictError("collection-attempt capacity reached")
                completed_at = self._clock()
                run = ResearchRun(
                    run_id=run_id,
                    request_id=request.request_id,
                    campaign_id=campaign_id,
                    icp_id=current.icp.icp_id,
                    stage=ResearchStage.DISCOVERY,
                    status=ResearchStatus.COMPLETED,
                    providers=result.providers,
                    attempt_ids=tuple(item.attempt_id for item in result.attempts),
                    evidence_ids=tuple(item.evidence_id for item in result.evidence),
                    prospect_ids=tuple(item.prospect_id for item in result.prospects),
                    policy_versions=tuple(
                        dict.fromkeys(item.policy_version for item in result.evidence)
                    ),
                    warnings=result.warnings,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                event = self._trace_event(
                    campaign_id,
                    len(current.trace) + 1,
                    TraceEventType.LIVE_DISCOVERY_COMPLETED,
                    input_ids=(current.icp.icp_id, request.request_id),
                    output_ids=(run.run_id,),
                    summary=(
                        "Bounded public-source discovery produced evidence-backed "
                        "prospect priorities."
                    ),
                )
                updated = current.model_copy(
                    update={
                        "evidence": current.evidence + result.evidence,
                        "prospects": result.prospects,
                        "collection_attempts": (
                            current.collection_attempts + result.attempts
                        ),
                        "research_runs": current.research_runs + (run,),
                        "trace": current.trace + (event,),
                        "updated_at": event.occurred_at,
                    },
                    deep=True,
                )
                self._repository.save(updated)
                return ResearchOutcome(run=run, campaign=updated.model_copy(deep=True))
            finally:
                self._active_research_campaigns.discard(campaign_id)

    def select_prospect(self, campaign_id: str, prospect_id: str) -> Campaign:
        with self._mutation_lock:
            return self._select_prospect(campaign_id, prospect_id)

    def _select_prospect(self, campaign_id: str, prospect_id: str) -> Campaign:
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
                "state": CampaignState.AWAITING_PROSPECT_RESEARCH,
                "selected_prospect_id": prospect_id,
                "trace": campaign.trace + (event,),
                "updated_at": event.occurred_at,
            },
            deep=True,
        )
        self._repository.save(updated)
        return updated.model_copy(deep=True)

    def research_prospect(
        self,
        campaign_id: str,
        prospect_id: str,
        request: ProspectResearchRequest,
    ) -> ResearchOutcome:
        with self._mutation_lock:
            campaign = self.get_campaign(campaign_id)
            existing = self._find_request(campaign, request.request_id)
            if existing is not None:
                if (
                    existing.stage is not ResearchStage.PROSPECT
                    or existing.prospect_id != prospect_id
                ):
                    raise WorkflowConflictError(
                        "research request ID is already used by another target"
                    )
                if existing.status is ResearchStatus.FAILED:
                    raise ResearchExecutionError(
                        existing.failure_code or "source_failure",
                        existing.run_id,
                    )
                return ResearchOutcome(run=existing, campaign=campaign)
            self._require_state(
                campaign,
                CampaignState.AWAITING_PROSPECT_RESEARCH,
                "research a prospect",
            )
            if campaign.selected_prospect_id != prospect_id:
                raise WorkflowConflictError(
                    "prospect research must target the selected prospect"
                )
            selected = next(
                item for item in campaign.prospects if item.prospect_id == prospect_id
            )
            is_live = selected.research_run_id is not None
            if is_live and self._prospect_research_runner is None:
                raise ResearchUnavailableError(
                    "live research requires GTM_RESEARCH_CONTACT configuration"
                )
            self._begin_research(campaign, ResearchStage.PROSPECT)
            snapshot = campaign
            run_id = self._new_id("research-run")
            started_at = self._clock()
        try:
            if is_live:
                assert self._prospect_research_runner is not None
                result = self._prospect_research_runner.research(
                    campaign_id=campaign_id,
                    prospect=selected,
                    run_id=run_id,
                    new_id=self._new_id,
                    now=self._clock(),
                )
            else:
                evidence, profile = self._pipeline.research_prospect(
                    campaign_id=campaign_id,
                    prospect=selected,
                    run_id=run_id,
                    new_id=self._new_id,
                    collected_at=self._clock(),
                )
                result = ProspectResearchResult(
                    evidence=evidence,
                    profile=profile,
                    attempts=(),
                    providers=("fixture",),
                    policy_versions=("fixture-v1",),
                    warnings=(),
                )
        except (ResearchCollectionError, SourcePolicyError) as error:
            code = self._safe_failure_code(error)
            try:
                self._persist_failed_run(
                    campaign_id=campaign_id,
                    request_id=request.request_id,
                    run_id=run_id,
                    stage=ResearchStage.PROSPECT,
                    prospect_id=prospect_id,
                    started_at=started_at,
                    code=code,
                    snapshot=snapshot,
                )
            finally:
                with self._mutation_lock:
                    self._active_research_campaigns.discard(campaign_id)
            raise ResearchExecutionError(code, run_id) from error
        except Exception:
            with self._mutation_lock:
                self._active_research_campaigns.discard(campaign_id)
            raise

        with self._mutation_lock:
            try:
                campaign = self.get_campaign(campaign_id)
                self._require_unchanged(campaign, snapshot)
                if len(campaign.evidence) + len(result.evidence) > 64:
                    raise WorkflowConflictError("campaign evidence capacity reached")
                if len(campaign.collection_attempts) + len(result.attempts) > 64:
                    raise WorkflowConflictError("collection-attempt capacity reached")
                completed_at = self._clock()
                run = ResearchRun(
                    run_id=run_id,
                    request_id=request.request_id,
                    campaign_id=campaign_id,
                    icp_id=campaign.icp.icp_id,
                    prospect_id=prospect_id,
                    stage=ResearchStage.PROSPECT,
                    status=ResearchStatus.COMPLETED,
                    providers=result.providers,
                    attempt_ids=tuple(item.attempt_id for item in result.attempts),
                    evidence_ids=tuple(item.evidence_id for item in result.evidence),
                    profile_id=result.profile.profile_id,
                    policy_versions=result.policy_versions,
                    warnings=result.warnings,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                event = self._trace_event(
                    campaign_id,
                    len(campaign.trace) + 1,
                    TraceEventType.PROSPECT_RESEARCH_COMPLETED,
                    input_ids=(prospect_id, request.request_id),
                    output_ids=(
                        run.run_id,
                        result.profile.profile_id,
                    ),
                    summary=(
                        "Evidence-backed prospect research completed the Phase 4 "
                        "authorization gate."
                    ),
                )
                updated = campaign.model_copy(
                    update={
                        "state": CampaignState.PROSPECT_RESEARCHED,
                        "evidence": campaign.evidence + result.evidence,
                        "collection_attempts": (
                            campaign.collection_attempts + result.attempts
                        ),
                        "research_runs": campaign.research_runs + (run,),
                        "prospect_research": result.profile,
                        "trace": campaign.trace + (event,),
                        "updated_at": event.occurred_at,
                    },
                    deep=True,
                )
                self._repository.save(updated)
                return ResearchOutcome(run=run, campaign=updated.model_copy(deep=True))
            finally:
                self._active_research_campaigns.discard(campaign_id)

    def generate_draft(self, campaign_id: str) -> Campaign:
        with self._mutation_lock:
            return self._generate_draft(campaign_id)

    def _generate_draft(self, campaign_id: str) -> Campaign:
        campaign = self.get_campaign(campaign_id)
        self._require_state(
            campaign,
            CampaignState.PROSPECT_RESEARCHED,
            "generate a draft",
        )
        selected = next(
            prospect
            for prospect in campaign.prospects
            if prospect.prospect_id == campaign.selected_prospect_id
        )
        approved_approvals = tuple(
            approval
            for approval in campaign.approvals
            if approval.decision is ApprovalDecision.APPROVED
        )
        if campaign.prospect_research is None:
            raise WorkflowConflictError("completed prospect research is required")
        positioning = self._pipeline.position(
            campaign_id=campaign_id,
            product=campaign.product,
            icp=campaign.icp,
            approved_approvals=approved_approvals,
            prospect=selected,
            prospect_research=campaign.prospect_research,
            new_id=self._new_id,
        )
        draft = self._pipeline.generate_draft(
            campaign_id=campaign_id,
            product=campaign.product,
            icp=campaign.icp,
            prospect=selected,
            positioning=positioning,
            approved_approvals=approved_approvals,
            new_id=self._new_id,
        )
        self._validate_draft(
            campaign,
            draft.claim_ids,
            draft.approval_ids,
            draft.evidence_ids,
            selected.prospect_id,
        )
        evaluation = self._pipeline.evaluate(
            campaign_id=campaign_id,
            draft=draft,
            approved_approvals=approved_approvals,
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
                    *(approval.claim_id for approval in approved_approvals),
                    *(approval.approval_id for approval in approved_approvals),
                ),
                output_ids=(positioning.positioning_id,),
                summary=("Positioning used approved claims and the selected prospect."),
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

    def get_research_run(self, campaign_id: str, run_id: str) -> ResearchRun:
        campaign = self.get_campaign(campaign_id)
        run = next(
            (item for item in campaign.research_runs if item.run_id == run_id),
            None,
        )
        if run is None:
            raise CampaignNotFoundError(f"research run not found: {run_id}")
        return run

    def get_trace(self, campaign_id: str) -> tuple[TraceEvent, ...]:
        return self.get_campaign(campaign_id).trace

    @staticmethod
    def _find_request(campaign: Campaign, request_id: str) -> ResearchRun | None:
        return next(
            (run for run in campaign.research_runs if run.request_id == request_id),
            None,
        )

    def _begin_research(
        self,
        campaign: Campaign,
        stage: ResearchStage,
    ) -> None:
        if campaign.campaign_id in self._active_research_campaigns:
            raise WorkflowConflictError("another research run is already active")
        stage_count = sum(run.stage is stage for run in campaign.research_runs)
        if stage_count >= 3 or len(campaign.research_runs) >= 6:
            raise WorkflowConflictError("campaign research-run capacity reached")
        self._active_research_campaigns.add(campaign.campaign_id)

    @staticmethod
    def _require_unchanged(campaign: Campaign, snapshot: Campaign) -> None:
        if campaign != snapshot:
            raise WorkflowConflictError(
                "campaign changed while public research was running"
            )

    @staticmethod
    def _safe_failure_code(
        error: ResearchCollectionError | SourcePolicyError,
    ) -> str:
        if isinstance(error, SourcePolicyError):
            return "source_policy_denied"
        candidate = str(error)
        if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", candidate):
            return candidate
        return "source_failure"

    def _persist_failed_run(
        self,
        *,
        campaign_id: str,
        request_id: str,
        run_id: str,
        stage: ResearchStage,
        prospect_id: str | None,
        started_at: datetime,
        code: str,
        snapshot: Campaign,
    ) -> None:
        with self._mutation_lock:
            campaign = self.get_campaign(campaign_id)
            self._require_unchanged(campaign, snapshot)
            run = ResearchRun(
                run_id=run_id,
                request_id=request_id,
                campaign_id=campaign_id,
                icp_id=campaign.icp.icp_id,
                prospect_id=prospect_id,
                stage=stage,
                status=ResearchStatus.FAILED,
                providers=("public_research",),
                failure_code=code,
                started_at=started_at,
                completed_at=self._clock(),
            )
            event = self._trace_event(
                campaign_id,
                len(campaign.trace) + 1,
                TraceEventType.RESEARCH_FAILED,
                input_ids=(request_id,),
                output_ids=(run_id,),
                summary=f"Public research failed with code {code}.",
            )
            updated = campaign.model_copy(
                update={
                    "research_runs": campaign.research_runs + (run,),
                    "trace": campaign.trace + (event,),
                    "updated_at": event.occurred_at,
                },
                deep=True,
            )
            self._repository.save(updated)

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
        approval_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        prospect_id: str,
    ) -> None:
        approved_records = {
            approval.approval_id: approval
            for approval in campaign.approvals
            if approval.decision is ApprovalDecision.APPROVED
        }
        if len(claim_ids) != len(approval_ids) or not claim_ids:
            raise WorkflowConflictError("draft claim approvals are incomplete")
        if any(
            approval_id not in approved_records
            or approved_records[approval_id].claim_id != claim_id
            for claim_id, approval_id in zip(claim_ids, approval_ids, strict=True)
        ):
            raise WorkflowConflictError("draft contains an unapproved product claim")
        available_evidence = {item.evidence_id for item in campaign.evidence}
        if not evidence_ids or not set(evidence_ids) <= available_evidence:
            raise WorkflowConflictError("draft contains unresolved evidence")
        if prospect_id != campaign.selected_prospect_id:
            raise WorkflowConflictError("draft does not target the selected prospect")

    @staticmethod
    def _matches_locked_decisions(
        campaign: Campaign,
        batch: ClaimDecisionBatch,
    ) -> bool:
        existing = {approval.claim_id: approval for approval in campaign.approvals}
        if {decision.claim_id for decision in batch.decisions} != set(existing):
            return False
        for decision in batch.decisions:
            approval = existing[decision.claim_id]
            expected_edit = (
                approval.reviewed_text
                if approval.wording_source is ClaimWordingSource.USER_EDITED
                else None
            )
            if (
                decision.decision is not approval.decision
                or decision.edited_text != expected_edit
                or decision.evidence_attested is not approval.evidence_attested
            ):
                return False
        return True


def _random_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(UTC)
