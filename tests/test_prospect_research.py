from collections import defaultdict
from datetime import UTC, datetime

from src.data.http_collector import CollectedDocument, ResearchCollectionError
from src.research.prospect import ProspectResearchService
from src.research.translation import TranslationResult
from src.schemas.campaign import ProspectCandidate, Uncertainty
from src.schemas.research import TranslationStatus

NOW = datetime(2026, 8, 3, tzinfo=UTC)


class SequentialIds:
    def __init__(self) -> None:
        self.counts: defaultdict[str, int] = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self.counts[prefix] += 1
        return f"{prefix}-deep{self.counts[prefix]:04d}"


class FakeCollector:
    def __init__(self, documents: dict[str, CollectedDocument]) -> None:
        self.documents = documents
        self.calls: list[str] = []

    def collect(self, url: str, _policy: object, **_kwargs) -> CollectedDocument:
        self.calls.append(url)
        value = self.documents.get(url)
        if value is None:
            raise ResearchCollectionError("source_unavailable")
        return value


class SpanishTranslator:
    def translate_to_english(self, _text: str) -> TranslationResult:
        return TranslationResult(
            english_text=(
                "Acme provides route planning software for logistics teams. "
                "The product helps teams review delivery exceptions."
            ),
            source_language="es",
            status=TranslationStatus.TRANSLATED,
        )


def _document(
    url: str,
    text: str,
    links: tuple[str, ...] = (),
    content_type: str = "text/html",
) -> CollectedDocument:
    return CollectedDocument(
        requested_url=url,
        canonical_url=url,
        title=url.rsplit("/", 1)[-1] or "Acme",
        text=text,
        links=links,
        content_type=content_type,
        body_sha256="d" * 64,
        fetched_at=NOW,
        observed_at=NOW,
        cache_hit=False,
    )


def _prospect() -> ProspectCandidate:
    return ProspectCandidate(
        prospect_id="prospect-example1",
        campaign_id="campaign-example1",
        icp_id="icp-example1",
        company="Acme Logistics",
        industry="logistics",
        official_url="https://acme.example/",
        matched_icp_fields=("industry",),
        evidence_ids=("evidence-seed0001",),
        score=0.35,
        uncertainty=Uncertainty.HIGH,
    )


def test_deep_research_is_bounded_sectioned_and_skips_pdf_and_external_links() -> None:
    home = "https://acme.example/"
    links = (
        "https://acme.example/about",
        "https://acme.example/products",
        "https://acme.example/projects",
        "https://acme.example/news",
        "https://acme.example/docs",
        "https://acme.example/blog/1",
        "https://acme.example/blog/2",
        "https://acme.example/blog/3",
        "https://acme.example/blog/4",
        "https://acme.example/blog/5",
        "https://acme.example/blog/6",
        "https://acme.example/blog/7",
        "https://acme.example/blog/8",
        "https://acme.example/report.pdf",
        "https://outside.example/projects",
    )
    documents = {home: _document(home, "Acme logistics company", links)}
    for link in links:
        if link.endswith(".pdf") or "outside.example" in link:
            continue
        documents[link] = _document(link, f"Public information at {link}")
    collector = FakeCollector(documents)

    result = ProspectResearchService(collector).research(
        campaign_id="campaign-example1",
        prospect=_prospect(),
        run_id="research-run-example1",
        new_id=SequentialIds(),
        now=NOW,
    )

    assert len(collector.calls) == 12
    assert all(not url.endswith(".pdf") for url in collector.calls)
    assert all("outside.example" not in url for url in collector.calls)
    assert set(result.profile.covered_sections) >= {
        "company",
        "offerings",
        "projects",
        "news",
        "technical",
    }
    assert result.profile.research_completeness == 1.0
    assert result.profile.evidence_ids == tuple(
        item.evidence_id for item in result.evidence
    )
    assert "pdf_not_extracted" in result.warnings


def test_failed_secondary_page_becomes_warning_without_losing_homepage() -> None:
    home = "https://acme.example/"
    missing = "https://acme.example/projects"
    collector = FakeCollector(
        {home: _document(home, "Acme logistics company", (missing,))}
    )

    result = ProspectResearchService(collector).research(
        campaign_id="campaign-example1",
        prospect=_prospect(),
        run_id="research-run-example1",
        new_id=SequentialIds(),
        now=NOW,
    )

    assert len(result.evidence) == 1
    assert result.profile.covered_sections == ("company",)
    assert "page_failed:source_unavailable" in result.warnings


def test_non_english_sources_produce_plain_english_findings_with_provenance() -> None:
    home = "https://acme.example/"
    collector = FakeCollector(
        {
            home: _document(
                home,
                "Acme ofrece software para planificar rutas y revisar entregas.",
            )
        }
    )

    result = ProspectResearchService(
        collector,
        translator=SpanishTranslator(),
    ).research(
        campaign_id="campaign-example1",
        prospect=_prospect(),
        run_id="research-run-example1",
        new_id=SequentialIds(),
        now=NOW,
    )

    finding = result.profile.findings[0]
    assert finding.section == "company"
    assert finding.source_language == "es"
    assert finding.summary_language == "en"
    assert finding.translation_status is TranslationStatus.TRANSLATED
    assert "route planning software" in finding.summary
    assert finding.evidence_ids == result.profile.evidence_ids


def test_deep_research_follows_relevant_second_level_company_links() -> None:
    home = "https://acme.example/"
    about = "https://acme.example/about"
    case_study = "https://acme.example/customers/route-team"
    collector = FakeCollector(
        {
            home: _document(home, "Acme logistics company", (about,)),
            about: _document(
                about,
                "Our company and team.",
                (case_study,),
            ),
            case_study: _document(
                case_study,
                "Customer project reduced manual delivery review.",
            ),
        }
    )

    result = ProspectResearchService(collector).research(
        campaign_id="campaign-example1",
        prospect=_prospect(),
        run_id="research-run-example1",
        new_id=SequentialIds(),
        now=NOW,
    )

    assert collector.calls == [home, about, case_study]
    assert "projects" in result.profile.covered_sections


def test_deep_research_uses_sitemap_when_homepage_has_no_useful_links() -> None:
    home = "https://acme.example/"
    sitemap = "https://acme.example/sitemap.xml"
    products = "https://acme.example/products"
    projects = "https://acme.example/customer-projects"
    collector = FakeCollector(
        {
            home: _document(home, "Acme logistics company"),
            sitemap: _document(
                sitemap,
                (
                    "<urlset><url><loc>https://acme.example/products</loc></url>"
                    "<url><loc>https://acme.example/customer-projects</loc></url>"
                    "<url><loc>https://outside.example/news</loc></url></urlset>"
                ),
                content_type="application/xml",
            ),
            products: _document(products, "Route planning products and services."),
            projects: _document(projects, "Customer logistics project."),
        }
    )

    result = ProspectResearchService(collector).research(
        campaign_id="campaign-example1",
        prospect=_prospect(),
        run_id="research-run-example1",
        new_id=SequentialIds(),
        now=NOW,
    )

    assert collector.calls == [home, sitemap, products, projects]
    assert "offerings" in result.profile.covered_sections
    assert "projects" in result.profile.covered_sections
    assert all("outside.example" not in url for url in collector.calls)


def test_deep_research_recovers_structured_company_domain_migration() -> None:
    old = "https://old-acme.example/"
    new = "https://acme.example/"
    products = "https://acme.example/products"

    class RedirectingCollector:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def collect(self, url, _policy, *, redirect_admitter=None):
            self.calls.append(url)
            if url == old:
                assert redirect_admitter is not None
                assert redirect_admitter(old, new, 301) is True
                return _document(
                    new,
                    "Acme logistics company",
                    (products,),
                )
            assert url == products
            return _document(products, "Route planning products.")

    prospect = _prospect().model_copy(
        update={"official_url": old, "source_entity_id": "Q123"}
    )
    collector = RedirectingCollector()

    result = ProspectResearchService(collector).research(
        campaign_id="campaign-example1",
        prospect=prospect,
        run_id="research-run-example1",
        new_id=SequentialIds(),
        now=NOW,
    )

    assert collector.calls == [old, products]
    assert result.evidence[0].canonical_url.unicode_string() == new
