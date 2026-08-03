import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.data.http_collector import CollectedDocument, ResearchCollectionError
from src.research.discovery import (
    CandidateSuggestion,
    DiscoveryRanker,
    DiscoveryResult,
    DiscoveryService,
    SourceObservation,
    attempts_from_evidence,
)
from src.research.prospect import ProspectResearchService
from src.runtime.fixtures import DeterministicFixturePipeline
from src.runtime.workflow import (
    CampaignNotFoundError,
    CampaignWorkflow,
    InMemoryCampaignRepository,
    ResearchExecutionError,
    WorkflowConflictError,
)
from src.schemas.campaign import (
    ApprovalDecision,
    Campaign,
    CampaignInput,
    CampaignState,
    ClaimDecision,
    ClaimDecisionBatch,
    ClaimStatus,
    ClaimWordingSource,
    TraceEventType,
)
from src.schemas.research import (
    ProspectResearchRequest,
    ResearchRequest,
    SourceCategory,
)


class SequentialIds:
    def __init__(self) -> None:
        self._counts: defaultdict[str, int] = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self._counts[prefix] += 1
        return f"{prefix}-{self._counts[prefix]:08d}"


class AdvancingClock:
    def __init__(self) -> None:
        self._current = datetime(2026, 8, 2, 10, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        value = self._current
        self._current += timedelta(seconds=1)
        return value


def campaign_input(
    *,
    product_name: str = "RouteSignal",
    capability: str = "exception reporting",
    industry: str = "logistics",
    role: str = "Head of Operations",
    pain: str = "manual exception review",
) -> CampaignInput:
    payload = {
        "product_name": product_name,
        "product_url": "https://example.com/product",
        "short_description": f"{product_name} supports operational teams.",
        "known_capabilities": [capability],
        "known_limitations": ["requires source-system access"],
        "icp": {
            "industries": [industry],
            "company_size": "mid-market",
            "roles": [role],
            "pain_hypotheses": [pain],
        },
    }
    return CampaignInput.model_validate_json(json.dumps(payload))


def build_workflow(
    pipeline: DeterministicFixturePipeline | None = None,
    **research_runners: object,
) -> tuple[CampaignWorkflow, InMemoryCampaignRepository]:
    repository = InMemoryCampaignRepository()
    workflow = CampaignWorkflow(
        repository=repository,
        pipeline=pipeline or DeterministicFixturePipeline(),
        new_id=SequentialIds(),
        clock=AdvancingClock(),
        **research_runners,
    )
    return workflow, repository


def decide_claims(workflow: CampaignWorkflow, campaign_id: str) -> None:
    campaign = workflow.get_campaign(campaign_id)
    decisions = [
        ClaimDecision(
            claim_id=claim.claim_id,
            decision=(
                ApprovalDecision.APPROVED if index == 0 else ApprovalDecision.REJECTED
            ),
        )
        for index, claim in enumerate(campaign.claims)
    ]
    workflow.decide_claims(
        campaign_id,
        ClaimDecisionBatch(decisions=decisions),
    )


def research_selected(workflow: CampaignWorkflow, campaign_id: str) -> None:
    campaign = workflow.get_campaign(campaign_id)
    assert campaign.selected_prospect_id is not None
    workflow.research_prospect(
        campaign_id,
        campaign.selected_prospect_id,
        ProspectResearchRequest(request_id="research-request-fixture1"),
    )


def test_fixture_workflow_propagates_inputs_and_produces_complete_trace() -> None:
    workflow, _ = build_workflow()

    created = workflow.create_campaign(campaign_input())
    decide_claims(workflow, created.campaign_id)
    ranked = workflow.get_campaign(created.campaign_id)
    selected = workflow.select_prospect(
        created.campaign_id,
        ranked.prospects[0].prospect_id,
    )
    assert selected.state is CampaignState.AWAITING_PROSPECT_RESEARCH
    research_selected(workflow, selected.campaign_id)
    completed = workflow.generate_draft(selected.campaign_id)

    assert completed.state is CampaignState.DRAFT_READY
    assert completed.draft is not None
    assert completed.positioning is not None
    assert completed.evaluation is not None
    assert completed.evaluation.passed is True
    assert completed.product.name in completed.draft.body
    assert completed.icp.roles[0] in completed.draft.body
    assert completed.icp.pain_hypotheses[0] in completed.draft.body
    approved_ids = {
        approval.claim_id
        for approval in completed.approvals
        if approval.decision is ApprovalDecision.APPROVED
    }
    assert set(completed.draft.claim_ids) == approved_ids
    assert all(
        evidence_id in {item.evidence_id for item in completed.evidence}
        for evidence_id in completed.draft.evidence_ids
    )
    assert [event.event_type for event in completed.trace] == [
        TraceEventType.CAMPAIGN_CREATED,
        TraceEventType.FIXTURE_RESEARCH_COMPLETED,
        TraceEventType.CLAIMS_PROPOSED,
        TraceEventType.CLAIMS_DECIDED,
        TraceEventType.PROSPECTS_RANKED,
        TraceEventType.PROSPECT_SELECTED,
        TraceEventType.PROSPECT_RESEARCH_COMPLETED,
        TraceEventType.POSITIONING_PRODUCED,
        TraceEventType.DRAFT_GENERATED,
        TraceEventType.DRAFT_VALIDATED,
        TraceEventType.DRAFT_EVALUATED,
    ]
    assert [event.sequence for event in completed.trace] == list(range(1, 12))
    ranking_event = completed.trace[4]
    prospect_evidence_ids = {
        evidence_id
        for prospect in completed.prospects
        for evidence_id in prospect.evidence_ids
    }
    assert {prospect.prospect_id for prospect in completed.prospects} <= set(
        ranking_event.output_ids
    )
    assert prospect_evidence_ids <= set(ranking_event.output_ids)
    assert Campaign.model_validate_json(completed.model_dump_json()) == completed


def test_contrasting_inputs_change_ranked_prospect_and_draft_content() -> None:
    workflow, _ = build_workflow()
    logistics = workflow.create_campaign(campaign_input())
    security = workflow.create_campaign(
        campaign_input(
            product_name="GuardLedger",
            capability="access review summaries",
            industry="cybersecurity",
            role="Security Operations Lead",
            pain="manual access review",
        )
    )

    for campaign in (logistics, security):
        decide_claims(workflow, campaign.campaign_id)
        ranked = workflow.get_campaign(campaign.campaign_id)
        workflow.select_prospect(campaign.campaign_id, ranked.prospects[0].prospect_id)
        research_selected(workflow, campaign.campaign_id)

    logistics_result = workflow.generate_draft(logistics.campaign_id)
    security_result = workflow.generate_draft(security.campaign_id)

    assert logistics_result.prospects[0].industry == "logistics"
    assert security_result.prospects[0].industry == "cybersecurity"
    assert logistics_result.draft is not None
    assert security_result.draft is not None
    assert logistics_result.draft.body != security_result.draft.body


def test_claim_decisions_must_be_complete_and_include_one_approval() -> None:
    workflow, repository = build_workflow()
    created = workflow.create_campaign(campaign_input())
    before = repository.get(created.campaign_id)

    with pytest.raises(WorkflowConflictError, match="every proposed claim"):
        workflow.decide_claims(
            created.campaign_id,
            ClaimDecisionBatch(
                decisions=[
                    ClaimDecision(
                        claim_id=created.claims[0].claim_id,
                        decision=ApprovalDecision.APPROVED,
                    )
                ]
            ),
        )

    assert repository.get(created.campaign_id) == before

    with pytest.raises(WorkflowConflictError, match="at least one claim"):
        workflow.decide_claims(
            created.campaign_id,
            ClaimDecisionBatch(
                decisions=[
                    ClaimDecision(
                        claim_id=claim.claim_id,
                        decision=ApprovalDecision.REJECTED,
                    )
                    for claim in created.claims
                ]
            ),
        )

    assert repository.get(created.campaign_id) == before


def test_illegal_transitions_and_unknown_ids_do_not_mutate_campaign() -> None:
    workflow, repository = build_workflow()
    created = workflow.create_campaign(campaign_input())
    before = repository.get(created.campaign_id)

    with pytest.raises(WorkflowConflictError, match="cannot select a prospect"):
        workflow.select_prospect(created.campaign_id, "prospect-9999")
    with pytest.raises(WorkflowConflictError, match="cannot generate a draft"):
        workflow.generate_draft(created.campaign_id)
    with pytest.raises(CampaignNotFoundError):
        workflow.get_campaign("campaign-9999")

    assert repository.get(created.campaign_id) == before


def test_identical_decision_retry_is_idempotent_and_other_replays_conflict() -> None:
    workflow, repository = build_workflow()
    created = workflow.create_campaign(campaign_input())
    decide_claims(workflow, created.campaign_id)
    after_decisions = repository.get(created.campaign_id)

    repeated_batch = ClaimDecisionBatch(
        decisions=[
            ClaimDecision(
                claim_id=claim.claim_id,
                decision=(
                    ApprovalDecision.APPROVED
                    if claim.status is ClaimStatus.APPROVED
                    else ApprovalDecision.REJECTED
                ),
            )
            for claim in after_decisions.claims
        ]
    )
    retried = workflow.decide_claims(created.campaign_id, repeated_batch)
    assert retried == after_decisions

    conflicting = repeated_batch.model_copy(
        update={
            "decisions": [
                decision.model_copy(
                    update={
                        "decision": (
                            ApprovalDecision.REJECTED
                            if decision.decision is ApprovalDecision.APPROVED
                            else ApprovalDecision.APPROVED
                        )
                    }
                )
                for decision in repeated_batch.decisions
            ]
        }
    )
    with pytest.raises(WorkflowConflictError, match="already locked"):
        workflow.decide_claims(created.campaign_id, conflicting)
    with pytest.raises(WorkflowConflictError, match="ranked for this campaign"):
        workflow.select_prospect(created.campaign_id, "prospect-9999")
    assert repository.get(created.campaign_id) == after_decisions

    selected = workflow.select_prospect(
        created.campaign_id,
        after_decisions.prospects[0].prospect_id,
    )
    research_selected(workflow, selected.campaign_id)
    researched = repository.get(created.campaign_id)
    with pytest.raises(WorkflowConflictError, match="cannot select a prospect"):
        workflow.select_prospect(
            created.campaign_id,
            after_decisions.prospects[0].prospect_id,
        )
    assert repository.get(created.campaign_id) == researched

    completed = workflow.generate_draft(created.campaign_id)
    with pytest.raises(WorkflowConflictError, match="cannot generate a draft"):
        workflow.generate_draft(created.campaign_id)
    assert repository.get(created.campaign_id) == completed


def test_edited_approval_is_immutable_and_drives_downstream_wording() -> None:
    workflow, _ = build_workflow()
    created = workflow.create_campaign(campaign_input())
    edited_text = "RouteSignal highlights reviewed delivery exceptions."
    original_text = created.claims[0].text
    batch = ClaimDecisionBatch(
        decisions=[
            ClaimDecision(
                claim_id=created.claims[0].claim_id,
                decision=ApprovalDecision.APPROVED,
                edited_text=edited_text,
                evidence_attested=True,
            ),
            ClaimDecision(
                claim_id=created.claims[1].claim_id,
                decision=ApprovalDecision.REJECTED,
            ),
        ]
    )

    reviewed = workflow.decide_claims(created.campaign_id, batch)
    assert reviewed.claims[0].text == original_text
    approval = reviewed.approvals[0]
    assert approval.original_text == original_text
    assert approval.reviewed_text == edited_text
    assert approval.wording_source is ClaimWordingSource.USER_EDITED
    assert approval.evidence_attested is True

    selected = workflow.select_prospect(
        reviewed.campaign_id, reviewed.prospects[0].prospect_id
    )
    research_selected(workflow, selected.campaign_id)
    completed = workflow.generate_draft(selected.campaign_id)

    assert completed.positioning is not None
    assert completed.draft is not None
    assert completed.positioning.approval_ids == (approval.approval_id,)
    assert completed.draft.approval_ids == (approval.approval_id,)
    assert edited_text in completed.draft.body
    assert original_text not in completed.draft.body


def test_edit_must_meaningly_change_the_proposed_wording() -> None:
    workflow, repository = build_workflow()
    created = workflow.create_campaign(campaign_input())
    before = repository.get(created.campaign_id)
    batch = ClaimDecisionBatch(
        decisions=[
            ClaimDecision(
                claim_id=created.claims[0].claim_id,
                decision=ApprovalDecision.APPROVED,
                edited_text=f"  {created.claims[0].text}  ",
                evidence_attested=True,
            ),
            ClaimDecision(
                claim_id=created.claims[1].claim_id,
                decision=ApprovalDecision.REJECTED,
            ),
        ]
    )

    with pytest.raises(WorkflowConflictError, match="must change"):
        workflow.decide_claims(created.campaign_id, batch)

    assert repository.get(created.campaign_id) == before


def test_campaign_contract_rejects_tampered_approval_provenance() -> None:
    workflow, _ = build_workflow()
    created = workflow.create_campaign(campaign_input())
    decide_claims(workflow, created.campaign_id)
    reviewed = workflow.get_campaign(created.campaign_id)
    payload = reviewed.model_dump()
    payload["approvals"][0]["original_text"] = "Tampered wording"
    payload["approvals"][0]["reviewed_text"] = "Tampered wording"

    with pytest.raises(ValidationError, match="original wording must match"):
        Campaign.model_validate(payload)


class FailingEvaluationPipeline(DeterministicFixturePipeline):
    def evaluate(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        raise RuntimeError("fixture evaluation failed")


def test_generation_failure_does_not_partially_save_campaign() -> None:
    workflow, repository = build_workflow(FailingEvaluationPipeline())
    created = workflow.create_campaign(campaign_input())
    decide_claims(workflow, created.campaign_id)
    ranked = workflow.get_campaign(created.campaign_id)
    workflow.select_prospect(created.campaign_id, ranked.prospects[0].prospect_id)
    research_selected(workflow, created.campaign_id)
    before = repository.get(created.campaign_id)

    with pytest.raises(RuntimeError, match="fixture evaluation failed"):
        workflow.generate_draft(created.campaign_id)

    assert repository.get(created.campaign_id) == before


def test_live_discovery_and_deep_research_authorize_positioning() -> None:
    observed_at = datetime(2026, 8, 2, 10, 30, tzinfo=UTC)
    structured = SourceObservation(
        provider="wikidata",
        publisher="Wikidata",
        source_category=SourceCategory.STRUCTURED_PUBLIC,
        title="Acme Logistics",
        url="https://www.wikidata.org/wiki/Q123",
        retrieval_url="https://www.wikidata.org/w/api.php?action=wbgetentities",
        text="Acme Logistics is a logistics company.",
        body_sha256="a" * 64,
        policy_version="wikidata-v1",
        license_basis="CC0 structured data; excerpt only",
        fetched_at=observed_at,
        observed_at=observed_at,
        cache_hit=False,
    )
    official = SourceObservation(
        provider="official_site",
        publisher="Acme Logistics",
        source_category=SourceCategory.OFFICIAL_WEBSITE,
        title="Acme",
        url="https://acme.example/",
        text="Acme logistics operations address manual exception review.",
        body_sha256="b" * 64,
        policy_version="official-website-v1",
        license_basis="public_excerpt",
        fetched_at=observed_at,
        observed_at=observed_at,
        cache_hit=False,
    )

    class Provider:
        name = "wikidata"

        def discover(self, _icp, _seed_urls):
            return (
                CandidateSuggestion(
                    company="Acme Logistics",
                    industry="logistics",
                    official_url="https://acme.example/",
                    provider="wikidata",
                    observations=(structured,),
                    source_entity_id="Q123",
                ),
            )

    class Expander:
        def expand(self, suggestion):
            return CandidateSuggestion(
                company=suggestion.company,
                industry=suggestion.industry,
                official_url=suggestion.official_url,
                provider="wikidata+official_site",
                observations=suggestion.observations + (official,),
                source_entity_id=suggestion.source_entity_id,
            )

    class Collector:
        def collect(self, url, _policy):
            return CollectedDocument(
                requested_url=url,
                canonical_url=url,
                title="Acme public site",
                text=(
                    "Company products projects news documentation for logistics "
                    "operations."
                ),
                links=(),
                content_type="text/html",
                body_sha256="c" * 64,
                fetched_at=observed_at,
                observed_at=observed_at,
                cache_hit=False,
            )

    workflow, _ = build_workflow(
        discovery_runner=DiscoveryService(
            providers=(Provider(),),
            expander=Expander(),
        ),
        prospect_research_runner=ProspectResearchService(Collector()),
    )
    created = workflow.create_campaign(campaign_input())
    decide_claims(workflow, created.campaign_id)
    discovery = workflow.run_discovery(
        created.campaign_id,
        ResearchRequest(request_id="research-request-live0001"),
    )
    prospect = discovery.campaign.prospects[0]
    assert prospect.research_run_id == discovery.run.run_id
    workflow.select_prospect(created.campaign_id, prospect.prospect_id)
    with pytest.raises(WorkflowConflictError, match="cannot generate a draft"):
        workflow.generate_draft(created.campaign_id)

    researched = workflow.research_prospect(
        created.campaign_id,
        prospect.prospect_id,
        ProspectResearchRequest(request_id="research-request-live0002"),
    )
    assert researched.campaign.state is CampaignState.PROSPECT_RESEARCHED
    completed = workflow.generate_draft(created.campaign_id)
    assert completed.prospect_research is not None
    assert completed.positioning is not None
    assert set(completed.prospect_research.evidence_ids) <= set(
        completed.positioning.evidence_ids
    )


def test_failed_discovery_is_persisted_with_stable_error_and_no_outputs() -> None:
    class FailingDiscovery:
        def run(self, **_kwargs):
            raise ResearchCollectionError("source_unavailable")

    workflow, repository = build_workflow(discovery_runner=FailingDiscovery())
    created = workflow.create_campaign(campaign_input())
    decide_claims(workflow, created.campaign_id)

    with pytest.raises(ResearchExecutionError) as raised:
        workflow.run_discovery(
            created.campaign_id,
            ResearchRequest(request_id="research-request-failure1"),
        )

    failed = repository.get(created.campaign_id)
    assert raised.value.code == "source_unavailable"
    assert failed.state is CampaignState.AWAITING_PROSPECT_SELECTION
    assert failed.research_runs[-1].failure_code == "source_unavailable"
    assert failed.research_runs[-1].evidence_ids == ()
    assert failed.trace[-1].event_type is TraceEventType.RESEARCH_FAILED


def test_new_discovery_supersedes_candidates_and_retains_prior_evidence() -> None:
    observed_at = datetime(2026, 8, 2, 10, 30, tzinfo=UTC)

    class ChangingDiscovery:
        calls = 0

        def run(self, *, campaign_id, icp, run_id, new_id, **_kwargs):
            self.calls += 1
            company = f"Candidate {self.calls}"
            observation = SourceObservation(
                provider="market_seed",
                publisher="Market directory",
                source_category=SourceCategory.APPROVED_MARKET_SOURCE,
                title=company,
                url=f"https://directory.example/{self.calls}",
                text=f"{company} is a logistics company.",
                body_sha256="d" * 64,
                policy_version="market-seed-v1",
                license_basis="public_excerpt",
                fetched_at=observed_at,
                observed_at=observed_at,
                cache_hit=False,
            )
            evidence, prospects = DiscoveryRanker().rank(
                campaign_id=campaign_id,
                icp=icp,
                run_id=run_id,
                suggestions=(
                    CandidateSuggestion(
                        company=company,
                        industry="logistics",
                        official_url=f"https://candidate{self.calls}.example/",
                        provider="market_seed",
                        observations=(observation,),
                    ),
                ),
                new_id=new_id,
                now=observed_at,
            )
            return DiscoveryResult(
                evidence=evidence,
                prospects=prospects,
                attempts=attempts_from_evidence(evidence, run_id, new_id),
                providers=("market_seed",),
                warnings=(),
            )

    workflow, _ = build_workflow(discovery_runner=ChangingDiscovery())
    created = workflow.create_campaign(campaign_input())
    decide_claims(workflow, created.campaign_id)
    first = workflow.run_discovery(
        created.campaign_id,
        ResearchRequest(request_id="research-request-refresh1"),
    )
    second = workflow.run_discovery(
        created.campaign_id,
        ResearchRequest(request_id="research-request-refresh2"),
    )

    assert second.campaign.prospects[0].company == "Candidate 2"
    assert len(second.campaign.research_runs) == 2
    assert set(first.run.evidence_ids) <= {
        item.evidence_id for item in second.campaign.evidence
    }
    assert first.run.prospect_ids[0] not in {
        item.prospect_id for item in second.campaign.prospects
    }
