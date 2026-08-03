from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.schemas.campaign import EvidenceRecord
from src.schemas.research import (
    CollectionStatus,
    EvidenceType,
    FactorMatch,
    ProspectResearchProfile,
    RankingFactor,
    ResearchRequest,
    ResearchRun,
    ResearchStage,
    ResearchStatus,
    SourceCategory,
)

NOW = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def test_discovery_request_bounds_and_normalizes_seed_urls() -> None:
    request = ResearchRequest(
        request_id="research-request-12345678",
        market_seed_urls=["https://example.com/market"],
    )

    assert str(request.market_seed_urls[0]) == "https://example.com/market"

    with pytest.raises(ValidationError):
        ResearchRequest(
            request_id="research-request-12345678",
            market_seed_urls=["http://example.com"],
        )
    with pytest.raises(ValidationError):
        ResearchRequest(
            request_id="research-request-12345678",
            market_seed_urls=[f"https://example{i}.com" for i in range(11)],
        )


def test_failed_run_cannot_authorize_evidence_or_prospects() -> None:
    with pytest.raises(ValidationError, match="failed run cannot authorize"):
        ResearchRun(
            run_id="research-run-12345678",
            request_id="research-request-12345678",
            campaign_id="campaign-0001",
            icp_id="icp-0001",
            stage=ResearchStage.DISCOVERY,
            status=ResearchStatus.FAILED,
            providers=("wikidata",),
            evidence_ids=("evidence-0001",),
            failure_code="source_unavailable",
            started_at=NOW,
            completed_at=NOW,
        )


def test_completed_run_requires_outputs_and_no_failure_code() -> None:
    with pytest.raises(ValidationError, match="completed run requires outputs"):
        ResearchRun(
            run_id="research-run-12345678",
            request_id="research-request-12345678",
            campaign_id="campaign-0001",
            icp_id="icp-0001",
            stage=ResearchStage.DISCOVERY,
            status=ResearchStatus.COMPLETED,
            providers=("wikidata",),
            started_at=NOW,
            completed_at=NOW,
        )


def test_profile_requires_same_run_supported_factors() -> None:
    factor = RankingFactor(
        factor_id="factor-12345678",
        research_run_id="research-run-12345678",
        icp_field="industry",
        target="logistics",
        observed_value="logistics",
        evidence_ids=("evidence-0001",),
        weight=0.35,
        match=FactorMatch.MATCHED,
        explanation="The official profile identifies logistics operations.",
    )

    profile = ProspectResearchProfile(
        profile_id="research-profile-12345678",
        campaign_id="campaign-0001",
        prospect_id="prospect-0001",
        research_run_id="research-run-12345678",
        evidence_ids=("evidence-0001",),
        factors=(factor,),
        covered_sections=("company_summary",),
        unknown_sections=("projects",),
        evidence_quality=0.7,
        research_completeness=0.5,
        completed_at=NOW,
    )

    assert profile.factors[0].match is FactorMatch.MATCHED
    assert EvidenceType.FACT.value == "fact"

    with pytest.raises(ValidationError, match="same research run"):
        ProspectResearchProfile(
            **profile.model_dump(exclude={"factors"}),
            factors=(
                factor.model_copy(update={"research_run_id": "research-run-87654321"}),
            ),
        )


def test_live_evidence_requires_run_urls_and_source_timestamps() -> None:
    evidence = EvidenceRecord(
        evidence_id="evidence-0001",
        campaign_id="campaign-0001",
        source_kind=SourceCategory.OFFICIAL_WEBSITE,
        research_run_id="research-run-12345678",
        provider="website",
        publisher="Example Logistics",
        canonical_url="https://example.com/about",
        retrieval_url="https://example.com/about",
        policy_version="website-v1",
        license_basis="public_excerpt",
        title="About Example Logistics",
        excerpt="Example Logistics provides freight services.",
        excerpt_end=45,
        content_sha256="a" * 64,
        collection_status=CollectionStatus.FETCHED,
        collected_at=NOW,
        fetched_at=NOW,
        observed_at=NOW,
    )

    assert evidence.research_run_id == "research-run-12345678"

    with pytest.raises(ValidationError, match="complete source provenance"):
        EvidenceRecord.model_validate(evidence.model_dump(exclude={"research_run_id"}))
