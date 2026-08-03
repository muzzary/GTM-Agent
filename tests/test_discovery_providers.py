import json
from datetime import UTC, datetime

from src.data.http_collector import CollectedDocument
from src.data.source_policy import SourcePolicyError
from src.research.discovery import CandidateSuggestion
from src.research.providers import (
    MarketSeedDiscoveryProvider,
    WebsiteCandidateExpander,
    WikidataDiscoveryProvider,
)
from src.schemas.campaign import ICPProfile

NOW = datetime(2026, 8, 3, tzinfo=UTC)


class FakeCollector:
    def __init__(self, documents: dict[str, CollectedDocument]) -> None:
        self.documents = documents
        self.calls: list[str] = []

    def collect(self, url: str, _policy: object) -> CollectedDocument:
        self.calls.append(url)
        return self.documents[url]


def _document(
    url: str,
    *,
    text: str,
    links: tuple[str, ...] = (),
    content_type: str = "text/html",
) -> CollectedDocument:
    return CollectedDocument(
        requested_url=url,
        canonical_url=url,
        title="Source title",
        text=text,
        links=links,
        content_type=content_type,
        body_sha256="c" * 64,
        fetched_at=NOW,
        observed_at=NOW,
        cache_hit=False,
    )


def _icp() -> ICPProfile:
    return ICPProfile(
        icp_id="icp-example1",
        campaign_id="campaign-example1",
        industries=("logistics",),
        company_size="51-200 employees",
        roles=("operations",),
        pain_hypotheses=("manual tracking",),
    )


def test_market_seed_discovers_bounded_external_https_domains() -> None:
    seed = "https://directory.example/vendors"
    collector = FakeCollector(
        {
            seed: _document(
                seed,
                text="Logistics vendors",
                links=(
                    "https://acme.example/",
                    "https://acme.example/about",
                    "https://linkedin.com/company/acme",
                    "https://beta.example/",
                    "http://insecure.example/",
                ),
            )
        }
    )

    suggestions = MarketSeedDiscoveryProvider(collector).discover(_icp(), (seed,))

    assert [item.official_url for item in suggestions] == [
        "https://acme.example/",
        "https://beta.example/",
    ]
    assert all(item.observations[0].url == seed for item in suggestions)


def test_website_expander_fetches_home_and_two_priority_pages_only() -> None:
    home = "https://acme.example/"
    about = "https://acme.example/about"
    products = "https://acme.example/products"
    news = "https://acme.example/news"
    collector = FakeCollector(
        {
            home: _document(
                home,
                text="Acme logistics",
                links=(news, products, about, "https://outside.example/about"),
            ),
            about: _document(about, text="About Acme logistics"),
            products: _document(products, text="Shipment tracking products"),
        }
    )
    seed = "https://directory.example/vendors"
    suggestion = MarketSeedDiscoveryProvider(
        FakeCollector({seed: _document(seed, text="vendors", links=(home,))})
    ).discover(_icp(), (seed,))[0]

    expanded = WebsiteCandidateExpander(collector).expand(suggestion)

    assert collector.calls == [home, about, products]
    assert len(expanded.observations) == 4
    assert expanded.provider == "market_seed+official_site"


def test_website_expander_preserves_candidate_when_source_policy_denies_site() -> None:
    class DeniedCollector:
        def collect(self, _url: str, _policy: object) -> CollectedDocument:
            raise SourcePolicyError("source host is not admitted by policy")

    suggestion = CandidateSuggestion(
        company="Canadian Pacific Railway",
        industry="logistics",
        official_url="https://cpr.ca/",
        provider="wikidata",
        observations=(),
        source_entity_id="Q466222",
    )

    expanded = WebsiteCandidateExpander(DeniedCollector()).expand(suggestion)

    assert expanded.company == suggestion.company
    assert expanded.provider == "wikidata"
    assert expanded.observations == ()
    assert expanded.warnings == (
        "official_site:cpr.ca:source_policy_denied",
    )


def test_wikidata_resolves_industry_then_queries_companies() -> None:
    search_url = WikidataDiscoveryProvider.search_url("logistics")
    query_url = WikidataDiscoveryProvider.company_query_url(("Q100", "Q101"))
    search_payload = {"search": [{"id": "Q100"}, {"id": "Q101"}]}
    query_payload = {
        "results": {
            "bindings": [
                {
                    "company": {"value": "http://www.wikidata.org/entity/Q1"},
                    "companyLabel": {"value": "Acme Logistics"},
                    "website": {"value": "https://acme.example/"},
                    "industryLabel": {"value": "logistics"},
                },
                {
                    "company": {"value": "not-a-wikidata-entity"},
                    "companyLabel": {"value": "Invalid"},
                    "website": {"value": "https://invalid.example/"},
                    "industryLabel": {"value": "logistics"},
                },
            ]
        }
    }
    collector = FakeCollector(
        {
            search_url: _document(
                search_url,
                text=json.dumps(search_payload),
                content_type="application/json",
            ),
            query_url: _document(
                query_url,
                text=json.dumps(query_payload),
                content_type="application/sparql-results+json",
            ),
        }
    )

    suggestions = WikidataDiscoveryProvider(collector).discover(_icp(), ())

    assert len(suggestions) == 1
    assert suggestions[0].company == "Acme Logistics"
    assert suggestions[0].source_entity_id == "Q1"
    assert suggestions[0].official_url == "https://acme.example/"
