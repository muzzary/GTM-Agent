import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
from typing import Protocol
from urllib.parse import urlsplit

from src.data.http_collector import CollectedDocument, ResearchCollectionError
from src.data.source_policy import SourcePolicyError
from src.schemas.campaign import (
    EvidenceRecord,
    ICPProfile,
    ProspectCandidate,
    Uncertainty,
)
from src.schemas.research import (
    CollectionAttempt,
    CollectionStatus,
    FactorMatch,
    RankingFactor,
    SourceCategory,
    SupportedSignal,
)

NewId = Callable[[str], str]


class DiscoveryProvider(Protocol):
    name: str

    def discover(
        self, icp: ICPProfile, seed_urls: Sequence[str]
    ) -> tuple["CandidateSuggestion", ...]: ...


class CandidateExpander(Protocol):
    def expand(self, suggestion: "CandidateSuggestion") -> "CandidateSuggestion": ...


@dataclass(frozen=True)
class SourceObservation:
    provider: str
    publisher: str
    source_category: SourceCategory
    title: str
    url: str
    text: str
    body_sha256: str
    policy_version: str
    license_basis: str
    fetched_at: datetime
    observed_at: datetime
    cache_hit: bool
    retrieval_url: str | None = None

    @classmethod
    def from_document(
        cls,
        document: CollectedDocument,
        *,
        provider: str,
        publisher: str,
        source_category: SourceCategory,
        policy_version: str,
        license_basis: str,
    ) -> "SourceObservation":
        return cls(
            provider=provider,
            publisher=publisher,
            source_category=source_category,
            title=document.title,
            url=document.canonical_url,
            text=document.text,
            body_sha256=document.body_sha256,
            policy_version=policy_version,
            license_basis=license_basis,
            fetched_at=document.fetched_at,
            observed_at=document.observed_at,
            cache_hit=document.cache_hit,
            retrieval_url=document.requested_url,
        )


@dataclass(frozen=True)
class CandidateSuggestion:
    company: str
    industry: str
    official_url: str
    provider: str
    observations: tuple[SourceObservation, ...]
    region: str | None = None
    source_entity_id: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryResult:
    evidence: tuple[EvidenceRecord, ...]
    prospects: tuple[ProspectCandidate, ...]
    attempts: tuple[CollectionAttempt, ...]
    providers: tuple[str, ...]
    warnings: tuple[str, ...]


class DiscoveryService:
    def __init__(
        self,
        *,
        providers: Sequence[DiscoveryProvider],
        expander: CandidateExpander,
        ranker: "DiscoveryRanker | None" = None,
    ) -> None:
        self._providers = tuple(providers)
        self._expander = expander
        self._ranker = ranker or DiscoveryRanker()

    def run(
        self,
        *,
        campaign_id: str,
        icp: ICPProfile,
        run_id: str,
        seed_urls: Sequence[str],
        new_id: NewId,
        now: datetime,
    ) -> DiscoveryResult:
        suggestions: list[CandidateSuggestion] = []
        used_providers: list[str] = []
        warnings: list[str] = []
        for provider in self._providers:
            try:
                discovered = provider.discover(icp, seed_urls)
            except (ResearchCollectionError, SourcePolicyError) as error:
                warnings.append(f"{provider.name}:{_safe_collection_code(error)}")
                continue
            if discovered:
                suggestions.extend(discovered)
                used_providers.append(provider.name)
        if not suggestions:
            raise ResearchCollectionError("no_candidates")
        expanded: list[CandidateSuggestion] = []
        for suggestion in deduplicate_suggestions(suggestions)[:10]:
            expanded_item = self._expander.expand(suggestion)
            expanded.append(expanded_item)
            warnings.extend(expanded_item.warnings)
            if len(expanded_item.observations) > len(suggestion.observations):
                used_providers.append("official_site")
        evidence, prospects = self._ranker.rank(
            campaign_id=campaign_id,
            icp=icp,
            run_id=run_id,
            suggestions=expanded,
            new_id=new_id,
            now=now,
        )
        return DiscoveryResult(
            evidence=evidence,
            prospects=prospects,
            attempts=attempts_from_evidence(evidence, run_id, new_id),
            providers=tuple(dict.fromkeys(used_providers)),
            warnings=tuple(dict.fromkeys(warnings)),
        )


def _safe_collection_code(error: ResearchCollectionError | SourcePolicyError) -> str:
    if isinstance(error, SourcePolicyError):
        return "source_policy_denied"
    return str(error)


class DiscoveryRanker:
    """Converts bounded observations into transparent ICP factors."""

    _weights = {
        "industry": 0.35,
        "company_size": 0.20,
        "role_relevance": 0.15,
        "pain_relevance": 0.20,
        "source_diversity": 0.10,
        "region": 0.0,
    }

    def rank(
        self,
        *,
        campaign_id: str,
        icp: ICPProfile,
        run_id: str,
        suggestions: Sequence[CandidateSuggestion],
        new_id: NewId,
        now: datetime,
    ) -> tuple[tuple[EvidenceRecord, ...], tuple[ProspectCandidate, ...]]:
        merged = deduplicate_suggestions(suggestions)[:10]
        all_evidence: list[EvidenceRecord] = []
        prospects: list[ProspectCandidate] = []
        for suggestion in merged:
            evidence = tuple(
                observation_to_evidence(campaign_id, run_id, item, new_id)
                for item in suggestion.observations
            )
            prospect = self._prospect(
                campaign_id=campaign_id,
                icp=icp,
                run_id=run_id,
                suggestion=suggestion,
                evidence=evidence,
                new_id=new_id,
                now=now,
            )
            region_factor = next(
                (
                    item
                    for item in prospect.ranking_factors
                    if item.icp_field == "region"
                ),
                None,
            )
            if icp.regions and (
                region_factor is None or region_factor.match is not FactorMatch.MATCHED
            ):
                continue
            all_evidence.extend(evidence)
            prospects.append(prospect)
        prospects.sort(
            key=lambda item: (
                -item.score,
                -item.evidence_quality,
                -item.research_completeness,
                item.company.casefold(),
                item.prospect_id,
            )
        )
        return tuple(all_evidence), tuple(prospects)

    def _prospect(
        self,
        *,
        campaign_id: str,
        icp: ICPProfile,
        run_id: str,
        suggestion: CandidateSuggestion,
        evidence: tuple[EvidenceRecord, ...],
        new_id: NewId,
        now: datetime,
    ) -> ProspectCandidate:
        searchable = tuple(
            (item.text.casefold(), record.evidence_id)
            for item, record in zip(suggestion.observations, evidence, strict=True)
        )
        base_factors = (
            self._term_factor("industry", icp.industries, searchable, run_id, new_id),
            self._term_factor(
                "company_size", (icp.company_size,), searchable, run_id, new_id
            ),
            self._term_factor("role_relevance", icp.roles, searchable, run_id, new_id),
            self._term_factor(
                "pain_relevance",
                icp.pain_hypotheses,
                searchable,
                run_id,
                new_id,
            ),
            self._diversity_factor(suggestion, run_id, new_id, evidence),
        )
        region_factors = (
            self._term_factor("region", icp.regions, searchable, run_id, new_id),
        ) if icp.regions else ()
        factors = base_factors + region_factors
        matched = tuple(
            factor.icp_field
            for factor in factors
            if factor.match is FactorMatch.MATCHED
        )
        unknown = tuple(
            factor.icp_field
            for factor in factors
            if factor.match is FactorMatch.UNKNOWN
        )
        score = round(
            sum(
                factor.weight
                for factor in factors
                if factor.match is FactorMatch.MATCHED
            ),
            4,
        )
        authority = {
            SourceCategory.OFFICIAL_WEBSITE: 1.0,
            SourceCategory.STRUCTURED_PUBLIC: 0.8,
            SourceCategory.APPROVED_MARKET_SOURCE: 0.6,
            SourceCategory.FIXTURE: 0.4,
        }
        evidence_quality = round(
            sum(authority[item.source_category] for item in suggestion.observations)
            / len(suggestion.observations),
            4,
        )
        completeness = round(len(matched) / len(factors), 4)
        uncertainty = (
            Uncertainty.LOW
            if len(unknown) <= 1
            else Uncertainty.MEDIUM
            if len(unknown) <= 2
            else Uncertainty.HIGH
        )
        pain_factor = next(
            item for item in factors if item.icp_field == "pain_relevance"
        )
        signals = ()
        public_signals = ()
        if pain_factor.match is FactorMatch.MATCHED:
            signal_text = (
                f"Public evidence contains the submitted pain signal: "
                f"{pain_factor.observed_value}."
            )
            signals = (
                SupportedSignal(
                    signal_id=new_id("signal"),
                    research_run_id=run_id,
                    category="pain_relevance",
                    text=signal_text,
                    evidence_ids=pain_factor.evidence_ids,
                    observed_at=now,
                    uncertainty="medium",
                ),
            )
            public_signals = (signal_text,)
        return ProspectCandidate(
            prospect_id=new_id("prospect"),
            campaign_id=campaign_id,
            icp_id=icp.icp_id,
            company=suggestion.company,
            industry=suggestion.industry,
            region=suggestion.region,
            research_run_id=run_id,
            provider=suggestion.provider,
            source_entity_id=suggestion.source_entity_id,
            official_url=suggestion.official_url,
            target_role=icp.roles[0],
            matched_icp_fields=matched,
            public_signals=public_signals,
            evidence_ids=tuple(item.evidence_id for item in evidence),
            score=score,
            evidence_quality=evidence_quality,
            research_completeness=completeness,
            ranking_factors=factors,
            supported_signals=signals,
            unknown_icp_fields=unknown,
            uncertainty=uncertainty,
        )

    def _term_factor(
        self,
        field: str,
        targets: Sequence[str],
        searchable: Sequence[tuple[str, str]],
        run_id: str,
        new_id: NewId,
    ) -> RankingFactor:
        for target in targets:
            normalized = target.casefold().strip()
            supporting = tuple(
                evidence_id for text, evidence_id in searchable if normalized in text
            )
            if supporting:
                return RankingFactor(
                    factor_id=new_id("factor"),
                    research_run_id=run_id,
                    icp_field=field,
                    target=target,
                    observed_value=target,
                    evidence_ids=supporting,
                    weight=self._weights[field],
                    match=FactorMatch.MATCHED,
                    explanation=(
                        "The normalized submitted term appears in retained public "
                        "evidence."
                    ),
                )
        return RankingFactor(
            factor_id=new_id("factor"),
            research_run_id=run_id,
            icp_field=field,
            target="; ".join(targets)[:200],
            weight=self._weights[field],
            match=FactorMatch.UNKNOWN,
            explanation="No retained evidence supports this submitted ICP factor.",
        )

    def _diversity_factor(
        self,
        suggestion: CandidateSuggestion,
        run_id: str,
        new_id: NewId,
        evidence: tuple[EvidenceRecord, ...],
    ) -> RankingFactor:
        categories = {item.source_category for item in suggestion.observations}
        if len(categories) >= 2:
            return RankingFactor(
                factor_id=new_id("factor"),
                research_run_id=run_id,
                icp_field="source_diversity",
                target="multiple source categories",
                observed_value=f"{len(categories)} source categories",
                evidence_ids=tuple(item.evidence_id for item in evidence),
                weight=self._weights["source_diversity"],
                match=FactorMatch.MATCHED,
                explanation="Evidence comes from at least two source categories.",
            )
        return RankingFactor(
            factor_id=new_id("factor"),
            research_run_id=run_id,
            icp_field="source_diversity",
            target="multiple source categories",
            weight=self._weights["source_diversity"],
            match=FactorMatch.UNKNOWN,
            explanation="Only one source category supports this candidate.",
        )


def observation_to_evidence(
    campaign_id: str,
    run_id: str,
    observation: SourceObservation,
    new_id: NewId,
) -> EvidenceRecord:
    excerpt = (observation.text.strip() or observation.title.strip())[:1_000]
    canonical_projection = json.dumps(
        {
            "canonical_url": observation.url,
            "excerpt": excerpt,
            "fetched_at": observation.fetched_at.isoformat(),
            "provider": observation.provider,
            "publisher": observation.publisher,
            "title": observation.title[:200],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return EvidenceRecord(
        evidence_id=new_id("evidence"),
        campaign_id=campaign_id,
        source_kind=observation.source_category,
        research_run_id=run_id,
        provider=observation.provider,
        publisher=observation.publisher,
        canonical_url=observation.url,
        retrieval_url=observation.retrieval_url or observation.url,
        policy_version=observation.policy_version,
        license_basis=observation.license_basis,
        title=observation.title[:200],
        excerpt=excerpt,
        excerpt_start=0,
        excerpt_end=len(excerpt),
        content_sha256=sha256(canonical_projection.encode("utf-8")).hexdigest(),
        collection_status=(
            CollectionStatus.CACHE_HIT
            if observation.cache_hit
            else CollectionStatus.FETCHED
        ),
        collected_at=observation.observed_at,
        fetched_at=observation.fetched_at,
        observed_at=observation.observed_at,
    )


def deduplicate_suggestions(
    suggestions: Sequence[CandidateSuggestion],
) -> list[CandidateSuggestion]:
    merged: dict[str, CandidateSuggestion] = {}
    for item in suggestions[:20]:
        host = (urlsplit(item.official_url).hostname or "").lower()
        key = host or item.company.casefold().strip()
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue
        observations = {
            (observation.url, observation.provider): observation
            for observation in existing.observations + item.observations
        }
        providers = tuple(
            dict.fromkeys((existing.provider + "+" + item.provider).split("+"))
        )
        merged[key] = replace(
            existing,
            provider="+".join(providers),
            observations=tuple(observations.values()),
            region=existing.region or item.region,
            source_entity_id=existing.source_entity_id or item.source_entity_id,
        )
    return list(merged.values())


def attempts_from_evidence(
    evidence: Sequence[EvidenceRecord],
    run_id: str,
    new_id: NewId,
) -> tuple[CollectionAttempt, ...]:
    attempts: list[CollectionAttempt] = []
    seen_urls: set[str] = set()
    for item in evidence:
        if item.retrieval_url is None or item.fetched_at is None:
            continue
        requested_url = str(item.retrieval_url)
        if requested_url in seen_urls:
            continue
        seen_urls.add(requested_url)
        attempts.append(
            CollectionAttempt(
                attempt_id=new_id("attempt"),
                research_run_id=run_id,
                provider=item.provider,
                source_host=urlsplit(requested_url).hostname or "unknown",
                requested_url=requested_url,
                status=item.collection_status,
                http_status=200,
                cache_hit=item.collection_status is CollectionStatus.CACHE_HIT,
                started_at=item.fetched_at,
                completed_at=max(item.observed_at or item.fetched_at, item.fetched_at),
            )
        )
    return tuple(attempts)
