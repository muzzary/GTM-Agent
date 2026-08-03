import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from src.data.http_collector import ControlledHttpCollector, ResearchCollectionError
from src.research.discovery import (
    SourceObservation,
    attempts_from_evidence,
    observation_to_evidence,
)
from src.research.providers import website_policy
from src.research.translation import (
    ConservativeEnglishTranslator,
    ResearchTranslator,
)
from src.schemas.campaign import EvidenceRecord, ProspectCandidate
from src.schemas.research import (
    CollectionAttempt,
    CollectionStatus,
    ProspectResearchProfile,
    ResearchFinding,
    SourceCategory,
    SupportedSignal,
    TranslationStatus,
)

NewId = Callable[[str], str]

_SECTIONS = {
    "company": ("about", "company", "team"),
    "offerings": ("product", "service", "solution", "platform"),
    "projects": ("project", "case-stud", "customer", "portfolio"),
    "news": ("news", "press", "blog", "launch", "partnership", "initiative"),
    "technical": ("docs", "technical", "developer", "documentation"),
}
_REQUIRED_SECTIONS = tuple(_SECTIONS)


@dataclass(frozen=True)
class ProspectResearchResult:
    evidence: tuple[EvidenceRecord, ...]
    profile: ProspectResearchProfile
    attempts: tuple[CollectionAttempt, ...]
    providers: tuple[str, ...]
    policy_versions: tuple[str, ...]
    warnings: tuple[str, ...]


class ProspectResearchService:
    def __init__(
        self,
        collector: ControlledHttpCollector,
        translator: ResearchTranslator | None = None,
    ) -> None:
        self._collector = collector
        self._translator = translator or ConservativeEnglishTranslator()

    def research(
        self,
        *,
        campaign_id: str,
        prospect: ProspectCandidate,
        run_id: str,
        new_id: NewId,
        now: datetime,
    ) -> ProspectResearchResult:
        if prospect.official_url is None:
            raise ResearchCollectionError("official_url_missing")
        official_url = str(prospect.official_url)
        host = (urlsplit(official_url).hostname or "").lower()
        policy = website_policy(
            host,
            policy_version="official-website-v1",
        )
        homepage = self._collector.collect(official_url, policy)
        documents = [homepage]
        warnings: list[str] = []
        failed_attempts: list[CollectionAttempt] = []
        links, pdf_seen = self._select_links(homepage.links, policy.allowed_hosts)
        if pdf_seen:
            warnings.append("pdf_not_extracted")
        queue = list(links)
        queued = set(queue)
        while queue and len(documents) < 12:
            link = queue.pop(0)
            try:
                document = self._collector.collect(link, policy)
            except ResearchCollectionError as error:
                warnings.append(f"page_failed:{error}")
                code = str(error)
                if not code.replace("_", "").isalnum():
                    code = "source_failure"
                failed_attempts.append(
                    CollectionAttempt(
                        attempt_id=new_id("attempt"),
                        research_run_id=run_id,
                        provider="official_site",
                        source_host=urlsplit(link).hostname or "unknown",
                        requested_url=link,
                        status=CollectionStatus.FAILED,
                        error_code=code,
                        started_at=now,
                        completed_at=now,
                    )
                )
                continue
            documents.append(document)
            nested_links, nested_pdf_seen = self._select_links(
                document.links,
                policy.allowed_hosts,
            )
            if nested_pdf_seen:
                warnings.append("pdf_not_extracted")
            for nested_link in nested_links:
                if nested_link not in queued and nested_link != official_url:
                    queue.append(nested_link)
                    queued.add(nested_link)

        observations = tuple(
            SourceObservation.from_document(
                document,
                provider="official_site",
                publisher=prospect.company,
                source_category=SourceCategory.OFFICIAL_WEBSITE,
                policy_version=policy.policy_version,
                license_basis="public_excerpt",
            )
            for document in documents
        )
        evidence = tuple(
            observation_to_evidence(campaign_id, run_id, item, new_id)
            for item in observations
        )
        section_evidence = self._section_evidence(documents, evidence)
        covered = tuple(
            section for section in _REQUIRED_SECTIONS if section_evidence[section]
        )
        unknown = tuple(
            section for section in _REQUIRED_SECTIONS if not section_evidence[section]
        )
        signals = tuple(
            SupportedSignal(
                signal_id=new_id("signal"),
                research_run_id=run_id,
                category=section,
                text=(
                    f"The official site contains retained public evidence "
                    f"classified as {section}."
                ),
                evidence_ids=section_evidence[section],
                observed_at=now,
                uncertainty="medium",
            )
            for section in covered
        )
        findings = self._findings(documents, evidence, section_evidence)
        if any(
            finding.translation_status is TranslationStatus.UNAVAILABLE
            for finding in findings
        ):
            warnings.append("english_translation_unavailable")
        completeness = round(len(covered) / len(_REQUIRED_SECTIONS), 4)
        profile = ProspectResearchProfile(
            profile_id=new_id("research-profile"),
            campaign_id=campaign_id,
            prospect_id=prospect.prospect_id,
            research_run_id=run_id,
            evidence_ids=tuple(item.evidence_id for item in evidence),
            signals=signals,
            findings=findings,
            covered_sections=covered,
            unknown_sections=unknown,
            evidence_quality=1.0,
            research_completeness=completeness,
            completed_at=now,
        )
        return ProspectResearchResult(
            evidence=evidence,
            profile=profile,
            attempts=(
                attempts_from_evidence(evidence, run_id, new_id)
                + tuple(failed_attempts)
            ),
            providers=("official_site",),
            policy_versions=(policy.policy_version,),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _findings(
        self,
        documents: Sequence,
        evidence: Sequence[EvidenceRecord],
        section_evidence: dict[str, tuple[str, ...]],
    ) -> tuple[ResearchFinding, ...]:
        documents_by_evidence = {
            record.evidence_id: document
            for document, record in zip(documents, evidence, strict=True)
        }
        findings: list[ResearchFinding] = []
        for section in _REQUIRED_SECTIONS:
            evidence_ids = section_evidence[section]
            if not evidence_ids:
                continue
            document = documents_by_evidence[evidence_ids[0]]
            translation = self._translator.translate_to_english(document.text)
            summary = (
                self._plain_summary(translation.english_text)
                if translation.status is not TranslationStatus.UNAVAILABLE
                else (
                    "An English summary is unavailable. "
                    "Review the linked source evidence."
                )
            )
            findings.append(
                ResearchFinding(
                    section=section,
                    heading=section.replace("_", " ").title(),
                    summary=summary,
                    source_language=translation.source_language,
                    translation_status=translation.status,
                    evidence_ids=evidence_ids[:12],
                )
            )
        return tuple(findings)

    @staticmethod
    def _plain_summary(text: str) -> str:
        compact = " ".join(text.split())
        sentences = re.split(r"(?<=[.!?])\s+", compact)
        summary = " ".join(sentences[:2]).strip()
        if len(summary) > 360:
            summary = summary[:357].rstrip() + "..."
        return summary or "The source page does not contain readable summary text."

    @staticmethod
    def _select_links(
        links: Sequence[str], allowed_hosts: frozenset[str]
    ) -> tuple[tuple[str, ...], bool]:
        ranked: list[tuple[int, str]] = []
        pdf_seen = False
        for link in links:
            parsed = urlsplit(link)
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or host not in allowed_hosts:
                continue
            if parsed.path.casefold().endswith(".pdf"):
                pdf_seen = True
                continue
            searchable = (parsed.path + " " + parsed.query).casefold()
            priorities = [
                index
                for index, terms in enumerate(_SECTIONS.values())
                if any(term in searchable for term in terms)
            ]
            if priorities:
                ranked.append((min(priorities), link))
        ordered = sorted(set(ranked), key=lambda item: (item[0], item[1]))
        selected: list[str] = []
        for priority in range(len(_SECTIONS)):
            first = next(
                (link for rank, link in ordered if rank == priority),
                None,
            )
            if first is not None:
                selected.append(first)
        selected.extend(link for _, link in ordered if link not in selected)
        return tuple(selected), pdf_seen

    @staticmethod
    def _section_evidence(
        documents: Sequence,
        evidence: Sequence[EvidenceRecord],
    ) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {section: [] for section in _REQUIRED_SECTIONS}
        result["company"].append(evidence[0].evidence_id)
        for document, record in zip(documents, evidence, strict=True):
            searchable = (
                f"{document.canonical_url} {document.title} {document.text}"
            ).casefold()
            for section, terms in _SECTIONS.items():
                if any(term in searchable for term in terms):
                    result[section].append(record.evidence_id)
        return {
            section: tuple(dict.fromkeys(evidence_ids))
            for section, evidence_ids in result.items()
        }
