from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, Field, model_validator

from src.schemas.base import StrictModel


class RevenueEventType(StrEnum):
    TRIAL_STARTED = "trial_started"
    CONVERTED = "converted"
    EXPANDED = "expanded"
    CONTRACTED = "contracted"
    CANCELLED = "cancelled"
    REACTIVATED = "reactivated"


class RevenueEvent(StrictModel):
    event_id: str = Field(pattern=r"^revenue-event-[a-z0-9-]{4,64}$")
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    subscription_id: str = Field(pattern=r"^subscription-[a-z0-9-]{4,64}$")
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    deal_id: str | None = Field(default=None, pattern=r"^deal-[a-z0-9-]{4,64}$")
    event_type: RevenueEventType = Field(strict=False)
    effective_at: AwareDatetime
    recorded_at: AwareDatetime
    mrr_minor_after: int = Field(ge=0, le=10**15)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    idempotency_key: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_event_amount(self) -> "RevenueEvent":
        if self.event_type is RevenueEventType.TRIAL_STARTED and self.mrr_minor_after:
            raise ValueError("trial_started must have zero MRR")
        if (
            self.event_type
            in {
                RevenueEventType.CONVERTED,
                RevenueEventType.EXPANDED,
                RevenueEventType.REACTIVATED,
            }
            and self.mrr_minor_after <= 0
        ):
            raise ValueError("revenue activation events must have positive MRR")
        if self.recorded_at < self.effective_at:
            raise ValueError("recorded_at cannot precede effective_at")
        return self


class RevenueEventCreate(StrictModel):
    event_id: str | None = Field(
        default=None, pattern=r"^revenue-event-[a-z0-9-]{4,64}$"
    )
    subscription_id: str = Field(pattern=r"^subscription-[a-z0-9-]{4,64}$")
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    deal_id: str | None = Field(default=None, pattern=r"^deal-[a-z0-9-]{4,64}$")
    event_type: RevenueEventType = Field(strict=False)
    effective_at: AwareDatetime = Field(strict=False)
    recorded_at: AwareDatetime = Field(strict=False)
    mrr_minor_after: int = Field(ge=0, le=10**15)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    idempotency_key: str = Field(min_length=1, max_length=128)


class RevenueMetric(StrictModel):
    amount_minor: int = Field(ge=0, le=10**15)
    event_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=128)
    explanation: str = Field(min_length=1, max_length=500)


class SubscriptionSnapshot(StrictModel):
    subscription_id: str = Field(pattern=r"^subscription-[a-z0-9-]{4,64}$")
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    as_of: date
    mrr_minor: int = Field(ge=0, le=10**15)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    last_event_id: str | None = Field(
        default=None, pattern=r"^revenue-event-[a-z0-9-]{4,64}$"
    )


class RevenueWarning(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    detail: str = Field(min_length=1, max_length=500)
    event_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=64)


class RevenueReport(StrictModel):
    tenant_id: str = Field(pattern=r"^tenant-[a-z0-9-]{4,64}$")
    as_of: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    mrr_minor: int = Field(ge=0, le=10**15)
    new_business: RevenueMetric
    expansion: RevenueMetric
    contraction: RevenueMetric
    churn: RevenueMetric
    pipeline_value: RevenueMetric
    forecast_value: RevenueMetric
    warnings: tuple[RevenueWarning, ...] = Field(default_factory=tuple, max_length=64)


class RevenueReportRequest(StrictModel):
    as_of: date = Field(strict=False)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
