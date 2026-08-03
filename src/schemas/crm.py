import re
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

CrmId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,252}[a-z0-9])?$")
_FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class CrmEntityType(StrEnum):
    COMPANY = "company"
    CONTACT = "contact"
    DEAL = "deal"


class ActivityType(StrEnum):
    NOTE = "note"
    RESEARCH = "research"
    OUTREACH = "outreach"
    DEAL_STAGE_CHANGED = "deal_stage_changed"


class CustomFieldType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    SELECT = "select"


class DealStatus(StrEnum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"


class Company(StrictModel):
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    name: str = Field(min_length=1, max_length=160)
    normalized_domain: str | None = Field(default=None, max_length=255)
    website: HttpUrl | None = None
    industry: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    custom_fields: dict[str, str] = Field(default_factory=dict, max_length=32)
    source_prospect_id: str | None = Field(
        default=None, pattern=r"^prospect-[a-z0-9-]{4,64}$"
    )
    source_campaign_id: str | None = Field(
        default=None, pattern=r"^campaign-[a-z0-9-]{4,64}$"
    )
    source_evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=36)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("normalized_domain", mode="before")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().rstrip(".")
        if not _DOMAIN.fullmatch(normalized):
            raise ValueError("normalized_domain must be a valid lowercase domain")
        return normalized


class Contact(StrictModel):
    contact_id: str = Field(pattern=r"^contact-[a-z0-9-]{4,64}$")
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    full_name: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=120)
    business_email: str | None = Field(default=None, max_length=254)
    custom_fields: dict[str, str] = Field(default_factory=dict, max_length=32)
    created_at: AwareDatetime
    updated_at: AwareDatetime


class PipelineStage(StrictModel):
    stage_id: str = Field(pattern=r"^stage-[a-z0-9-]{4,64}$")
    pipeline_id: str = Field(pattern=r"^pipeline-[a-z0-9-]{4,64}$")
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    name: str = Field(min_length=1, max_length=80)
    position: int = Field(ge=0, le=100)
    probability: float = Field(ge=0, le=1)


class Pipeline(StrictModel):
    pipeline_id: str = Field(pattern=r"^pipeline-[a-z0-9-]{4,64}$")
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    name: str = Field(min_length=1, max_length=120)
    stages: tuple[PipelineStage, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def stages_belong_to_pipeline(self) -> Self:
        if any(
            stage.pipeline_id != self.pipeline_id or stage.tenant_id != self.tenant_id
            for stage in self.stages
        ):
            raise ValueError(
                "pipeline stages must belong to the same tenant and pipeline"
            )
        positions = [stage.position for stage in self.stages]
        if len(positions) != len(set(positions)):
            raise ValueError("pipeline stage positions must be unique")
        return self


class Deal(StrictModel):
    deal_id: str = Field(pattern=r"^deal-[a-z0-9-]{4,64}$")
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    contact_id: str | None = Field(default=None, pattern=r"^contact-[a-z0-9-]{4,64}$")
    pipeline_id: str = Field(pattern=r"^pipeline-[a-z0-9-]{4,64}$")
    stage_id: str = Field(pattern=r"^stage-[a-z0-9-]{4,64}$")
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    name: str = Field(min_length=1, max_length=160)
    status: DealStatus = Field(strict=False)
    amount_minor: int = Field(ge=0, le=10**15)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    custom_fields: dict[str, str] = Field(default_factory=dict, max_length=32)
    created_at: AwareDatetime
    updated_at: AwareDatetime


class CustomFieldDefinition(StrictModel):
    field_id: str = Field(pattern=r"^custom-field-[a-z0-9-]{4,64}$")
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    entity_type: CrmEntityType = Field(strict=False)
    key: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    field_type: CustomFieldType = Field(strict=False)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not _FIELD_KEY.fullmatch(value):
            raise ValueError("custom field key must be snake_case")
        return value


class Activity(StrictModel):
    activity_id: str = Field(pattern=r"^activity-[a-z0-9-]{4,64}$")
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    entity_type: CrmEntityType = Field(strict=False)
    entity_id: CrmId
    activity_type: ActivityType = Field(strict=False)
    summary: str = Field(min_length=1, max_length=1_000)
    occurred_at: AwareDatetime


class CompanyCreate(StrictModel):
    company_id: str | None = Field(
        default=None, pattern=r"^company-[a-z0-9-]{4,64}$"
    )
    name: str = Field(min_length=1, max_length=160)
    normalized_domain: str | None = Field(default=None, max_length=255)
    website: HttpUrl | None = None
    industry: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    custom_fields: dict[str, str] = Field(default_factory=dict, max_length=32)
    source_prospect_id: str | None = Field(
        default=None, pattern=r"^prospect-[a-z0-9-]{4,64}$"
    )
    source_campaign_id: str | None = Field(
        default=None, pattern=r"^campaign-[a-z0-9-]{4,64}$"
    )
    source_evidence_ids: list[str] = Field(default_factory=list, max_length=36)


class ContactCreate(StrictModel):
    contact_id: str | None = Field(
        default=None, pattern=r"^contact-[a-z0-9-]{4,64}$"
    )
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    full_name: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=120)
    business_email: str | None = Field(default=None, max_length=254)
    custom_fields: dict[str, str] = Field(default_factory=dict, max_length=32)


class PipelineStageCreate(StrictModel):
    stage_id: str | None = Field(default=None, pattern=r"^stage-[a-z0-9-]{4,64}$")
    name: str = Field(min_length=1, max_length=80)
    position: int = Field(ge=0, le=100)
    probability: float = Field(ge=0, le=1)


class PipelineCreate(StrictModel):
    pipeline_id: str | None = Field(
        default=None, pattern=r"^pipeline-[a-z0-9-]{4,64}$"
    )
    name: str = Field(min_length=1, max_length=120)
    stages: list[PipelineStageCreate] = Field(min_length=1, max_length=32)


class DealCreate(StrictModel):
    deal_id: str | None = Field(default=None, pattern=r"^deal-[a-z0-9-]{4,64}$")
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    contact_id: str | None = Field(
        default=None, pattern=r"^contact-[a-z0-9-]{4,64}$"
    )
    pipeline_id: str = Field(pattern=r"^pipeline-[a-z0-9-]{4,64}$")
    stage_id: str = Field(pattern=r"^stage-[a-z0-9-]{4,64}$")
    name: str = Field(min_length=1, max_length=160)
    amount_minor: int = Field(ge=0, le=10**15)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    custom_fields: dict[str, str] = Field(default_factory=dict, max_length=32)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ActivityCreate(StrictModel):
    activity_id: str | None = Field(
        default=None, pattern=r"^activity-[a-z0-9-]{4,64}$"
    )
    entity_type: CrmEntityType = Field(strict=False)
    entity_id: CrmId
    activity_type: ActivityType = Field(strict=False)
    summary: str = Field(min_length=1, max_length=1_000)
    occurred_at: AwareDatetime = Field(strict=False)
