from collections import defaultdict
from datetime import UTC, datetime

from src.data.http_collector import CollectedDocument, ResearchCollectionError
from src.research.prospect import ProspectResearchService
from src.schemas.campaign import ProspectCandidate, Uncertainty

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

    def collect(self, url: str, _policy: object) -> CollectedDocument:
        self.calls.append(url)
        value = self.documents.get(url)
        if value is None:
            raise ResearchCollectionError("source_unavailable")
        return value


def _document(
    url: str,
    text: str,
    links: tuple[str, ...] = (),
) -> CollectedDocument:
    return CollectedDocument(
        requested_url=url,
        canonical_url=url,
        title=url.rsplit("/", 1)[-1] or "Acme",
        text=text,
        links=links,
        content_type="text/html",
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
