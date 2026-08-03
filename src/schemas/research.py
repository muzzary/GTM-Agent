from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from src.schemas.base import StrictModel

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{7,80}$")]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
LongText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)
]


class EvidenceType(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


class SourceCategory(StrEnum):
    FIXTURE = "fixture"
    STRUCTURED_PUBLIC = "structured_public"
    OFFICIAL_WEBSITE = "official_website"
    APPROVED_MARKET_SOURCE = "approved_market_source"


class CollectionStatus(StrEnum):
    FIXTURE = "fixture"
    FETCHED = "fetched"
    CACHE_HIT = "cache_hit"
    DENIED = "denied"
    FAILED = "failed"


class ResearchStage(StrEnum):
    DISCOVERY = "discovery"
    PROSPECT = "prospect"


class ResearchStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class FactorMatch(StrEnum):
    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    UNKNOWN = "unknown"


class ResearchRequest(StrictModel):
    request_id: str = Field(pattern=r"^research-request-[a-z0-9-]{8,64}$")
    market_seed_urls: list[HttpUrl] = Field(default_factory=list, max_length=10)

    @field_validator("market_seed_urls")
    @classmethod
    def seed_urls_must_be_unique_https(
        cls, urls: list[HttpUrl]
    ) -> list[HttpUrl]:
        normalized = tuple(str(url) for url in urls)
        if any(url.scheme != "https" for url in urls):
            raise ValueError("market seed URLs must use HTTPS")
        if len(normalized) != len(set(normalized)):
            raise ValueError("market seed URLs must be unique")
        return urls


class ProspectResearchRequest(StrictModel):
    request_id: str = Field(pattern=r"^research-request-[a-z0-9-]{8,64}$")


class CollectionAttempt(StrictModel):
    attempt_id: Identifier
    research_run_id: Identifier
    provider: ShortText
    source_host: ShortText
    requested_url: HttpUrl
    status: CollectionStatus
    http_status: int | None = Field(default=None, ge=100, le=599)
    cache_hit: bool = False
    error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{2,63}$")
    started_at: AwareDatetime
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def outcome_is_consistent(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("collection attempt cannot finish before it starts")
        if self.status in {CollectionStatus.DENIED, CollectionStatus.FAILED}:
            if self.error_code is None:
                raise ValueError("failed collection attempt requires an error code")
        elif self.error_code is not None:
            raise ValueError("successful collection attempt cannot include an error")
        if self.cache_hit and self.status is not CollectionStatus.CACHE_HIT:
            raise ValueError("cache_hit requires cache_hit status")
        return self


class RankingFactor(StrictModel):
    factor_id: Identifier
    research_run_id: Identifier
    icp_field: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    target: ShortText
    observed_value: ShortText | None = None
    evidence_ids: tuple[Identifier, ...] = Field(default_factory=tuple, max_length=12)
    weight: float = Field(ge=0, le=1)
    match: FactorMatch
    explanation: LongText

    @model_validator(mode="after")
    def evidence_matches_state(self) -> Self:
        if self.match is FactorMatch.MATCHED:
            if self.observed_value is None or not self.evidence_ids:
                raise ValueError("matched factor requires observed evidence")
        elif self.match is FactorMatch.UNKNOWN:
            if self.observed_value is not None or self.evidence_ids:
                raise ValueError("unknown factor cannot claim observed evidence")
        return self


class SupportedSignal(StrictModel):
    signal_id: Identifier
    research_run_id: Identifier
    category: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    text: LongText
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=12)
    observed_at: AwareDatetime
    uncertainty: str = Field(pattern=r"^(low|medium|high)$")


class ResearchRun(StrictModel):
    run_id: str = Field(pattern=r"^research-run-[a-z0-9-]{8,64}$")
    request_id: str = Field(pattern=r"^research-request-[a-z0-9-]{8,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    icp_id: str = Field(pattern=r"^icp-[a-z0-9-]{4,64}$")
    prospect_id: str | None = Field(
        default=None, pattern=r"^prospect-[a-z0-9-]{4,64}$"
    )
    stage: ResearchStage
    status: ResearchStatus
    providers: tuple[ShortText, ...] = Field(min_length=1, max_length=8)
    attempt_ids: tuple[Identifier, ...] = Field(default_factory=tuple, max_length=24)
    evidence_ids: tuple[Identifier, ...] = Field(default_factory=tuple, max_length=36)
    prospect_ids: tuple[Identifier, ...] = Field(default_factory=tuple, max_length=20)
    profile_id: Identifier | None = None
    policy_versions: tuple[ShortText, ...] = Field(default_factory=tuple, max_length=8)
    warnings: tuple[LongText, ...] = Field(default_factory=tuple, max_length=16)
    failure_code: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9_]{2,63}$"
    )
    started_at: AwareDatetime
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def terminal_outcome_is_consistent(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError("research run cannot finish before it starts")
        outputs = bool(self.evidence_ids or self.prospect_ids or self.profile_id)
        if self.status is ResearchStatus.FAILED:
            if outputs:
                raise ValueError("failed run cannot authorize outputs")
            if self.failure_code is None:
                raise ValueError("failed run requires a failure code")
        else:
            if not outputs:
                raise ValueError("completed run requires outputs")
            if self.failure_code is not None:
                raise ValueError("completed run cannot include a failure code")
        if self.stage is ResearchStage.DISCOVERY and self.prospect_id is not None:
            raise ValueError("discovery run cannot target a selected prospect")
        if self.stage is ResearchStage.PROSPECT and self.prospect_id is None:
            raise ValueError("prospect research run requires a prospect")
        return self


class ProspectResearchProfile(StrictModel):
    profile_id: str = Field(pattern=r"^research-profile-[a-z0-9-]{8,64}$")
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    prospect_id: str = Field(pattern=r"^prospect-[a-z0-9-]{4,64}$")
    research_run_id: str = Field(pattern=r"^research-run-[a-z0-9-]{8,64}$")
    evidence_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=36)
    factors: tuple[RankingFactor, ...] = Field(default_factory=tuple, max_length=16)
    signals: tuple[SupportedSignal, ...] = Field(default_factory=tuple, max_length=24)
    covered_sections: tuple[ShortText, ...] = Field(min_length=1, max_length=12)
    unknown_sections: tuple[ShortText, ...] = Field(
        default_factory=tuple, max_length=12
    )
    conflict_evidence_ids: tuple[Identifier, ...] = Field(
        default_factory=tuple, max_length=12
    )
    evidence_quality: float = Field(ge=0, le=1)
    research_completeness: float = Field(ge=0, le=1)
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def provenance_is_same_run_and_resolved(self) -> Self:
        if any(
            factor.research_run_id != self.research_run_id
            for factor in self.factors
        ) or any(
            signal.research_run_id != self.research_run_id
            for signal in self.signals
        ):
            raise ValueError("profile records must use the same research run")
        evidence = set(self.evidence_ids)
        references = {
            evidence_id
            for factor in self.factors
            for evidence_id in factor.evidence_ids
        } | {
            evidence_id
            for signal in self.signals
            for evidence_id in signal.evidence_ids
        } | set(self.conflict_evidence_ids)
        if not references <= evidence:
            raise ValueError("profile references must resolve to profile evidence")
        if set(self.covered_sections) & set(self.unknown_sections):
            raise ValueError("research sections cannot be both covered and unknown")
        return self


class ResearchProblem(StrictModel):
    type: str = "about:blank"
    title: ShortText
    status: int = Field(ge=400, le=599)
    detail: LongText
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    research_run_id: Identifier | None = None
