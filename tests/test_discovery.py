from datetime import UTC, datetime
from threading import Barrier

import pytest

from src.data.http_collector import CollectedDocument, ResearchCollectionError
from src.research.discovery import (
    CandidateSuggestion,
    DiscoveryRanker,
    DiscoveryService,
    SourceObservation,
)
from src.schemas.campaign import ICPProfile
from src.schemas.research import FactorMatch, SourceCategory

NOW = datetime(2026, 8, 3, tzinfo=UTC)


def _icp() -> ICPProfile:
    return ICPProfile(
        icp_id="icp-example1",
        campaign_id="campaign-example1",
        industries=("logistics",),
        company_size="51-200 employees",
        roles=("operations",),
        pain_hypotheses=("manual shipment tracking",),
    )


def _observation(
    *,
    provider: str,
    category: SourceCategory,
    url: str,
    text: str,
) -> SourceObservation:
    return SourceObservation(
        provider=provider,
        publisher="Example publisher",
        source_category=category,
        title="Example source",
        url=url,
        text=text,
        body_sha256="a" * 64,
        policy_version=f"{provider}-v1",
        license_basis="public_excerpt",
        fetched_at=NOW,
        observed_at=NOW,
        cache_hit=False,
    )


def test_ranker_awards_only_supported_factors_and_preserves_unknowns() -> None:
    suggestion = CandidateSuggestion(
        company="Acme Logistics",
        industry="logistics",
        official_url="https://acme.example/",
        provider="wikidata",
        source_entity_id="Q123",
        observations=(
            _observation(
                provider="wikidata",
                category=SourceCategory.STRUCTURED_PUBLIC,
                url="https://www.wikidata.org/wiki/Q123",
                text="Acme Logistics is a logistics company.",
            ),
            _observation(
                provider="official_site",
                category=SourceCategory.OFFICIAL_WEBSITE,
                url="https://acme.example/projects",
                text=(
                    "Our operations team is replacing manual shipment tracking "
                    "across regional projects."
                ),
            ),
        ),
    )

    evidence, prospects = DiscoveryRanker().rank(
        campaign_id="campaign-example1",
        icp=_icp(),
        run_id="research-run-example1",
        suggestions=(suggestion,),
        new_id=lambda prefix: f"{prefix}-example1",
        now=NOW,
    )

    assert len(evidence) == 2
    prospect = prospects[0]
    factors = {factor.icp_field: factor for factor in prospect.ranking_factors}
    assert factors["industry"].match is FactorMatch.MATCHED
    assert factors["role_relevance"].match is FactorMatch.MATCHED
    assert factors["pain_relevance"].match is FactorMatch.MATCHED
    assert factors["source_diversity"].match is FactorMatch.MATCHED
    assert factors["company_size"].match is FactorMatch.UNKNOWN
    assert factors["company_size"].evidence_ids == ()
    assert prospect.score == 0.8
    assert prospect.unknown_icp_fields == ("company_size",)


def test_ranker_deduplicates_by_official_host_and_sorts_deterministically() -> None:
    source = _observation(
        provider="market_seed",
        category=SourceCategory.APPROVED_MARKET_SOURCE,
        url="https://directory.example/list",
        text="Logistics vendors include Beta Freight.",
    )
    suggestions = (
        CandidateSuggestion(
            company="Beta Freight",
            industry="logistics",
            official_url="https://beta.example/",
            provider="market_seed",
            observations=(source,),
        ),
        CandidateSuggestion(
            company="Beta Freight Ltd",
            industry="logistics",
            official_url="https://beta.example/about",
            provider="official_site",
            observations=(
                _observation(
                    provider="official_site",
                    category=SourceCategory.OFFICIAL_WEBSITE,
                    url="https://beta.example/about",
                    text="Beta Freight provides logistics services.",
                ),
            ),
        ),
    )

    _, prospects = DiscoveryRanker().rank(
        campaign_id="campaign-example1",
        icp=_icp(),
        run_id="research-run-example1",
        suggestions=suggestions,
        new_id=lambda prefix: f"{prefix}-example2",
        now=NOW,
    )

    assert len(prospects) == 1
    assert len(prospects[0].evidence_ids) == 2


def test_no_keyword_overlap_produces_zero_score_not_a_false_match() -> None:
    suggestion = CandidateSuggestion(
        company="Unknown Company",
        industry="software",
        official_url="https://unknown.example/",
        provider="market_seed",
        observations=(
            _observation(
                provider="market_seed",
                category=SourceCategory.APPROVED_MARKET_SOURCE,
                url="https://directory.example/list",
                text="Unknown Company appears in this public directory.",
            ),
        ),
    )

    _, prospects = DiscoveryRanker().rank(
        campaign_id="campaign-example1",
        icp=_icp(),
        run_id="research-run-example1",
        suggestions=(suggestion,),
        new_id=lambda prefix: f"{prefix}-example3",
        now=NOW,
    )

    prospect = prospects[0]
    assert prospect.score == 0
    assert all(
        factor.match is FactorMatch.UNKNOWN for factor in prospect.ranking_factors
    )
    assert prospect.uncertainty.value == "high"


def test_source_observation_can_be_built_from_collected_document() -> None:
    document = CollectedDocument(
        requested_url="https://acme.example/",
        canonical_url="https://acme.example/",
        title="Acme",
        text="Acme provides logistics software.",
        links=(),
        content_type="text/html",
        body_sha256="b" * 64,
        fetched_at=NOW,
        observed_at=NOW,
        cache_hit=True,
    )

    observation = SourceObservation.from_document(
        document,
        provider="official_site",
        publisher="Acme",
        source_category=SourceCategory.OFFICIAL_WEBSITE,
        policy_version="website-v1",
        license_basis="public_excerpt",
    )

    assert observation.url == document.canonical_url
    assert observation.cache_hit is True
    assert observation.body_sha256 == "b" * 64


def test_discovery_service_combines_providers_and_shallow_expands() -> None:
    source = _observation(
        provider="wikidata",
        category=SourceCategory.STRUCTURED_PUBLIC,
        url="https://www.wikidata.org/wiki/Q123",
        text="Acme is a logistics company.",
    )
    official = _observation(
        provider="official_site",
        category=SourceCategory.OFFICIAL_WEBSITE,
        url="https://acme.example/",
        text="Acme logistics operations use manual shipment tracking.",
    )

    class Provider:
        name = "wikidata"

        def discover(self, _icp, _seed_urls):
            return (
                CandidateSuggestion(
                    company="Acme",
                    industry="logistics",
                    official_url="https://acme.example/",
                    provider="wikidata",
                    observations=(source,),
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
                warnings=("official_site:acme.example:source_http_error",),
            )

    sequence = iter(range(100))
    result = DiscoveryService(
        providers=(Provider(),),
        expander=Expander(),
    ).run(
        campaign_id="campaign-example1",
        icp=_icp(),
        run_id="research-run-example1",
        seed_urls=(),
        new_id=lambda prefix: f"{prefix}-example{next(sequence)}",
        now=NOW,
    )

    assert result.providers == ("wikidata", "official_site")
    assert result.warnings == ("official_site:acme.example:source_http_error",)
    assert result.prospects[0].score == 0.8


def test_discovery_service_runs_independent_providers_concurrently() -> None:
    started = Barrier(2)
    source = _observation(
        provider="wikidata",
        category=SourceCategory.STRUCTURED_PUBLIC,
        url="https://www.wikidata.org/wiki/Q123",
        text="Acme is a logistics company.",
    )

    class Provider:
        def __init__(self, name: str, host: str) -> None:
            self.name = name
            self.host = host

        def discover(self, _icp, _seed_urls):
            started.wait(timeout=1)
            return (
                CandidateSuggestion(
                    company=self.name,
                    industry="logistics",
                    official_url=f"https://{self.host}/",
                    provider=self.name,
                    observations=(source,),
                ),
            )

    class IdentityExpander:
        def expand(self, suggestion):
            return suggestion

    result = DiscoveryService(
        providers=(
            Provider("wikidata", "acme.example"),
            Provider("market_seed", "beta.example"),
        ),
        expander=IdentityExpander(),
    ).run(
        campaign_id="campaign-example1",
        icp=_icp(),
        run_id="research-run-example1",
        seed_urls=(),
        new_id=lambda prefix: f"{prefix}-example1",
        now=NOW,
    )

    assert {item.company for item in result.prospects} == {"wikidata", "market_seed"}


def test_discovery_service_shallow_expands_unique_sites_concurrently() -> None:
    started = Barrier(2)
    source = _observation(
        provider="wikidata",
        category=SourceCategory.STRUCTURED_PUBLIC,
        url="https://www.wikidata.org/wiki/Q123",
        text="A logistics company.",
    )

    class Provider:
        name = "wikidata"

        def discover(self, _icp, _seed_urls):
            return tuple(
                CandidateSuggestion(
                    company=company,
                    industry="logistics",
                    official_url=url,
                    provider="wikidata",
                    observations=(source,),
                )
                for company, url in (
                    ("Acme", "https://acme.example/"),
                    ("Beta", "https://beta.example/"),
                )
            )

    class CoordinatedExpander:
        def expand(self, suggestion):
            started.wait(timeout=1)
            return suggestion

    result = DiscoveryService(
        providers=(Provider(),),
        expander=CoordinatedExpander(),
    ).run(
        campaign_id="campaign-example1",
        icp=_icp(),
        run_id="research-run-example1",
        seed_urls=(),
        new_id=lambda prefix: f"{prefix}-example1",
        now=NOW,
    )

    assert len(result.prospects) == 2


def test_ranker_drops_unverified_search_hint_without_evidence() -> None:
    evidence, prospects = DiscoveryRanker().rank(
        campaign_id="campaign-example1",
        icp=_icp(),
        run_id="research-run-example1",
        suggestions=(
            CandidateSuggestion(
                company="Unverified",
                industry="logistics",
                official_url="https://unverified.example/",
                provider="brave_search",
                observations=(),
            ),
        ),
        new_id=lambda prefix: f"{prefix}-example1",
        now=NOW,
    )

    assert evidence == ()
    assert prospects == ()


def test_discovery_service_preserves_total_provider_failure() -> None:
    class FailedProvider:
        name = "wikidata"

        def discover(self, _icp, _seed_urls):
            raise ResearchCollectionError("source_unavailable")

    class UnusedExpander:
        def expand(self, suggestion):
            raise AssertionError(f"unexpected expansion: {suggestion}")

    with pytest.raises(ResearchCollectionError, match="^source_failure$"):
        DiscoveryService(
            providers=(FailedProvider(),),
            expander=UnusedExpander(),
        ).run(
            campaign_id="campaign-example1",
            icp=_icp(),
            run_id="research-run-example1",
            seed_urls=(),
            new_id=lambda prefix: f"{prefix}-example1",
            now=NOW,
        )


def test_discovery_service_preserves_total_provider_timeout() -> None:
    class TimedOutProvider:
        name = "wikidata"

        def discover(self, _icp, _seed_urls):
            raise ResearchCollectionError("source_timeout")

    class UnusedExpander:
        def expand(self, suggestion):
            raise AssertionError(f"unexpected expansion: {suggestion}")

    with pytest.raises(ResearchCollectionError, match="^source_timeout$"):
        DiscoveryService(
            providers=(TimedOutProvider(),),
            expander=UnusedExpander(),
        ).run(
            campaign_id="campaign-example1",
            icp=_icp(),
            run_id="research-run-example1",
            seed_urls=(),
            new_id=lambda prefix: f"{prefix}-example1",
            now=NOW,
        )


def test_ranker_excludes_candidates_without_matching_region_evidence() -> None:
    united_states = _observation(
        provider="wikidata",
        category=SourceCategory.STRUCTURED_PUBLIC,
        url="https://www.wikidata.org/wiki/Q1",
        text="Acme Logistics. Industry: logistics. Region: United States.",
    )
    canada = _observation(
        provider="wikidata",
        category=SourceCategory.STRUCTURED_PUBLIC,
        url="https://www.wikidata.org/wiki/Q2",
        text="North Freight. Industry: logistics. Region: Canada.",
    )
    icp = _icp().model_copy(update={"regions": ("United States",)})

    evidence, prospects = DiscoveryRanker().rank(
        campaign_id="campaign-example1",
        icp=icp,
        run_id="research-run-example1",
        suggestions=(
            CandidateSuggestion(
                company="Acme Logistics",
                industry="logistics",
                region="United States",
                official_url="https://acme.example/",
                provider="wikidata",
                observations=(united_states,),
            ),
            CandidateSuggestion(
                company="North Freight",
                industry="logistics",
                region="Canada",
                official_url="https://north.example/",
                provider="wikidata",
                observations=(canada,),
            ),
        ),
        new_id=lambda prefix: f"{prefix}-example1",
        now=NOW,
    )

    assert len(evidence) == 1
    assert [prospect.company for prospect in prospects] == ["Acme Logistics"]
    assert prospects[0].region == "United States"
    region_factor = next(
        factor
        for factor in prospects[0].ranking_factors
        if factor.icp_field == "region"
    )
    assert region_factor.match is FactorMatch.MATCHED
    assert region_factor.weight == 0
