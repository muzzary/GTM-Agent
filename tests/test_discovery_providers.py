import json
from datetime import UTC, datetime

from src.data.http_collector import CollectedDocument
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

    suggestions = MarketSeedDiscoveryProvider(collector).discover(
        _icp(), (seed,)
    )

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
    suggestion = MarketSeedDiscoveryProvider(
        FakeCollector(
            {
                "https://directory.example/vendors": _document(
                    "https://directory.example/vendors",
                    text="vendors",
                    links=(home,),
                )
            }
        )
    ).discover(_icp(), ("https://directory.example/vendors",))[0]

    expanded = WebsiteCandidateExpander(collector).expand(suggestion)

    assert collector.calls == [home, about, products]
    assert len(expanded.observations) == 4
    assert expanded.provider == "market_seed+official_site"


def test_wikidata_keeps_only_entities_with_company_and_website_claims() -> None:
    search_url = WikidataDiscoveryProvider.search_url("logistics")
    entity_url = WikidataDiscoveryProvider.entity_url(("Q1", "Q2", "Q3"))
    search_payload = {
        "search": [{"id": "Q1"}, {"id": "Q2"}, {"id": "Q3"}]
    }
    entity_payload = {
        "entities": {
            "Q1": {
                "labels": {"en": {"value": "Acme Logistics"}},
                "descriptions": {"en": {"value": "logistics company"}},
                "claims": {
                    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q4830453"}}}}],
                    "P452": [{"mainsnak": {"datavalue": {"value": {"id": "Q物流"}}}}],
                    "P856": [{"mainsnak": {"datavalue": {"value": "https://acme.example/"}}}],
                },
            },
            "Q2": {
                "labels": {"en": {"value": "No Website"}},
                "descriptions": {"en": {"value": "logistics company"}},
                "claims": {"P31": [{}]},
            },
            "Q3": {
                "labels": {"en": {"value": "A Person"}},
                "descriptions": {"en": {"value": "logistics commentator"}},
                "claims": {
                    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                    "P452": [{"mainsnak": {"datavalue": {"value": {"id": "Q物流"}}}}],
                    "P856": [{"mainsnak": {"datavalue": {"value": "https://person.example/"}}}],
                },
            },
        }
    }
    collector = FakeCollector(
        {
            search_url: _document(
                search_url,
                text=json.dumps(search_payload),
                content_type="application/json",
            ),
            entity_url: _document(
                entity_url,
                text=json.dumps(entity_payload),
                content_type="application/json",
            ),
        }
    )

    suggestions = WikidataDiscoveryProvider(collector).discover(_icp(), ())

    assert len(suggestions) == 1
    assert suggestions[0].company == "Acme Logistics"
    assert suggestions[0].source_entity_id == "Q1"
    assert suggestions[0].official_url == "https://acme.example/"
