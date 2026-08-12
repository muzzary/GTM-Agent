import json
import unicodedata
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from src.agent.tools import CrmToolRegistry
from src.crm.service import CrmService
from src.data.crm_repository import CrmRepository
from src.schemas.base import StrictModel
from src.schemas.crm import DealStatus

CrmCategory = Literal[
    "read_lookup", "approval_required_write", "approved_write", "clarification",
    "refusal", "idempotent_replay", "multi_step",
]
CrmAdversarialTag = Literal[
    "fabricated_tool", "approval_bypass", "injected_instruction", "missing_argument",
    "out_of_scope", "idempotency_violation",
]


class CrmPriorObservation(StrictModel):
    call_id: str = Field(pattern=r"^tool-call-[a-z0-9-]{4,64}$")
    tool_name: str = Field(min_length=1, max_length=120)
    result: dict[str, object]


class CrmBenchmarkSeedCompany(StrictModel):
    company_id: str
    tenant_id: str
    name: str
    normalized_domain: str | None = None
    website: str | None = None
    industry: str | None = None
    region: str | None = None
    custom_fields: dict[str, str] = {}
    source_prospect_id: str | None = None
    source_campaign_id: str | None = None
    source_evidence_ids: list[str] = []
    created_at: AwareDatetime = Field(strict=False)
    updated_at: AwareDatetime = Field(strict=False)


class CrmBenchmarkSeedDeal(StrictModel):
    deal_id: str
    company_id: str
    contact_id: str | None = None
    pipeline_id: str
    stage_id: str
    tenant_id: str
    name: str
    status: DealStatus = Field(strict=False)
    amount_minor: int
    currency: str
    custom_fields: dict[str, str] = {}
    created_at: AwareDatetime = Field(strict=False)
    updated_at: AwareDatetime = Field(strict=False)


class CrmBenchmarkPromptTool(StrictModel):
    name: str
    requires_approval: bool
    argument_schema: dict[str, object]


class CrmBenchmarkPromptInput(StrictModel):
    task_type: Literal["crm_tool_use"]
    tenant_id: str
    goal: str
    prior_observations: list[CrmPriorObservation]
    approved_call_ids: list[str]
    tool_catalog: list[CrmBenchmarkPromptTool]


def _registry() -> CrmToolRegistry:
    repository = CrmRepository(Path(".tmp") / "crm-benchmark-schema.sqlite3")
    return CrmToolRegistry(
        CrmService(repository),
        prospect_reader=lambda _tenant, campaign: {
            "campaign_id": campaign,
            "status": "inspected",
        },
        prospect_linker=lambda _tenant, campaign, key: {
            "campaign_id": campaign,
            "idempotency_key": key,
            "status": "linked",
        },
        revenue_reporter=lambda _tenant, as_of, currency: {
            "as_of": as_of.isoformat(),
            "currency": currency,
            "total_minor": 0,
        },
    )


class CrmBenchmarkCase(StrictModel):
    case_id: str = Field(pattern=r"^case-crm-[a-z0-9-]{3,64}$")
    schema_version: Literal["1.0"]
    task_type: Literal["crm_tool_use"]
    category: CrmCategory
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    goal: str = Field(min_length=1, max_length=2_000)
    prior_observations: list[CrmPriorObservation] = Field(max_length=32)
    seed_companies: list[CrmBenchmarkSeedCompany] = Field(max_length=32)
    seed_deals: list[CrmBenchmarkSeedDeal] = Field(max_length=32)
    available_tools: list[str] = Field(min_length=1, max_length=16)
    approved_call_ids: list[str] = Field(default_factory=list, max_length=16)
    expected_action: Literal["tool_call", "final"]
    expected_call_id: str | None = Field(
        default=None, pattern=r"^tool-call-[a-z0-9-]{4,64}$"
    )
    expected_tool_name: str | None = Field(default=None, min_length=1, max_length=120)
    required_arguments: dict[str, object] = Field(default_factory=dict)
    forbidden_tool_names: list[str] = Field(default_factory=list, max_length=16)
    adversarial_tags: list[CrmAdversarialTag] = Field(
        default_factory=list, max_length=8
    )
    protected_adversarial: bool = False
    review_status: Literal["pending", "reviewed"]
    reviewer_reference: str | None = Field(default=None, min_length=1, max_length=160)
    reviewed_at: AwareDatetime | None = Field(default=None, strict=False)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def contract_is_consistent(self) -> Self:
        if self.review_status == "reviewed" and (
            self.reviewer_reference is None or self.reviewed_at is None
        ):
            raise ValueError("reviewed benchmark cases require reviewer provenance")
        if self.review_status == "pending" and (
            self.reviewer_reference is not None or self.reviewed_at is not None
        ):
            raise ValueError("pending benchmark cases cannot claim reviewer provenance")
        for values, label in (
            (self.available_tools, "available tools"),
            (self.approved_call_ids, "approved call IDs"),
            (self.forbidden_tool_names, "forbidden tool names"),
            (self.adversarial_tags, "adversarial tags"),
        ):
            if values != sorted(set(values)):
                raise ValueError(f"{label} must be unique and sorted")
        if self.protected_adversarial and not self.adversarial_tags:
            raise ValueError("protected adversarial cases require a classification tag")
        if self.expected_action == "tool_call" and self.expected_call_id is None:
            raise ValueError("tool_call cases require an expected call ID")
        if self.expected_action == "tool_call" and self.expected_tool_name is None:
            raise ValueError("tool_call cases require an expected tool")
        if self.expected_action == "final" and (
            self.expected_call_id is not None
            or self.expected_tool_name is not None
            or self.required_arguments
        ):
            raise ValueError("final cases cannot specify expected call details")
        if self.expected_tool_name is not None:
            registry = _registry()
            for name in self.available_tools:
                registry.get(name)
            if self.expected_tool_name not in self.available_tools:
                raise ValueError("expected tool must be available")
            if self.expected_tool_name in self.forbidden_tool_names:
                raise ValueError("expected tool cannot be forbidden")
            fields = registry.get(self.expected_tool_name).argument_model.model_fields
            if not set(self.required_arguments).issubset(fields):
                raise ValueError("required arguments must be real tool fields")
            requires_approval = registry.get(self.expected_tool_name).requires_approval
            if self.category == "approval_required_write" and (
                not requires_approval or self.expected_call_id in self.approved_call_ids
            ):
                raise ValueError("approval_required_write category is inconsistent")
            if self.category == "approved_write" and (
                not requires_approval
                or self.expected_call_id not in self.approved_call_ids
            ):
                raise ValueError("approved_write category is inconsistent")
            if self.category == "read_lookup" and requires_approval:
                raise ValueError("read_lookup requires a non-approval tool")
        if self.category in {"refusal", "clarification"} and (
            self.expected_action != "final"
        ):
            raise ValueError("refusal and clarification cases must end with final")
        expected_hash = self.content_sha256_for_audit()
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected_hash)
        elif self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match benchmark case content")
        return self

    @property
    def call_id_is_scored(self) -> bool:
        """Only approved writes require re-emitting the user-approved call ID."""
        return self.category == "approved_write"

    def prompt_input(self) -> CrmBenchmarkPromptInput:
        registry = _registry()
        return CrmBenchmarkPromptInput(
            task_type=self.task_type,
            tenant_id=self.tenant_id,
            goal=self.goal,
            prior_observations=self.prior_observations,
            approved_call_ids=list(self.approved_call_ids),
            tool_catalog=[
                CrmBenchmarkPromptTool(
                    name=name,
                    requires_approval=registry.get(name).requires_approval,
                    argument_schema=registry.get(name).argument_model.model_json_schema(),
                )
                for name in self.available_tools
            ],
        )

    def content_sha256_for_audit(self) -> str:
        content = self.model_dump(mode="json", exclude={"content_sha256"})
        content.pop("case_id")
        return _content_digest(content)


class CrmBenchmarkManifest(StrictModel):
    benchmark_id: str = Field(pattern=r"^benchmark-[a-z0-9-]{4,64}$")
    manifest_version: Literal["1.0"]
    lifecycle_status: Literal["pending_review", "frozen"]
    frozen_at: AwareDatetime | None = Field(default=None, strict=False)
    reviewer_reference: str | None = Field(default=None, min_length=1, max_length=160)
    cases: list[CrmBenchmarkCase] = Field(min_length=40, max_length=60)
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def lifecycle_is_consistent(self) -> Self:
        if self.lifecycle_status == "frozen" and (
            self.frozen_at is None
            or self.reviewer_reference is None
            or any(case.review_status != "reviewed" for case in self.cases)
        ):
            raise ValueError("frozen benchmark requires completed manual review")
        if self.lifecycle_status == "pending_review" and (
            self.frozen_at is not None or self.reviewer_reference is not None
        ):
            raise ValueError("pending benchmark cannot claim frozen reviewer metadata")
        expected_hash = self.content_sha256_for_audit()
        if self.content_sha256 is None:
            object.__setattr__(self, "content_sha256", expected_hash)
        elif self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match benchmark manifest")
        return self

    def content_sha256_for_audit(self) -> str:
        return _content_digest(self.model_dump(mode="json", exclude={"content_sha256"}))


class CrmBenchmarkAuditReport(StrictModel):
    benchmark_id: str
    passed: bool
    evaluation_ready: bool
    total_cases: int = Field(ge=0)
    category_counts: dict[str, int]
    adversarial_case_count: int = Field(ge=0)
    protected_adversarial_case_count: int = Field(ge=0)
    duplicate_case_ids: list[str]
    duplicate_content_hashes: list[str]
    errors: list[str]


def _content_digest(content: dict[str, Any]) -> str:
    canonical = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(unicodedata.normalize("NFC", canonical).encode("utf-8")).hexdigest()
