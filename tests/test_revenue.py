from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.data.crm_repository import CrmConflictError, CrmRepository
from src.revenue.service import RevenueService
from src.schemas.crm import Company, Pipeline, PipelineStage
from src.schemas.revenue import RevenueEvent, RevenueEventCreate, RevenueEventType

NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def test_revenue_event_requires_effective_time_order_and_valid_amount() -> None:
    event = RevenueEvent(
        event_id="revenue-event-0001",
        tenant_id="tenant-0001",
        subscription_id="subscription-0001",
        company_id="company-0001",
        event_type=RevenueEventType.CONVERTED,
        effective_at=NOW,
        recorded_at=NOW,
        mrr_minor_after=10000,
        currency="USD",
        idempotency_key="revenue-0001",
    )

    assert event.mrr_minor_after == 10000

    with pytest.raises(ValidationError):
        RevenueEvent(
            **event.model_dump(exclude={"event_type", "mrr_minor_after"}),
            event_type=RevenueEventType.TRIAL_STARTED,
            mrr_minor_after=10000,
        )


def test_revenue_event_rejects_recorded_time_before_effective_time() -> None:
    with pytest.raises(ValidationError):
        RevenueEvent(
            event_id="revenue-event-0001",
            tenant_id="tenant-0001",
            subscription_id="subscription-0001",
            company_id="company-0001",
            event_type=RevenueEventType.CONVERTED,
            effective_at=NOW,
            recorded_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
            mrr_minor_after=10000,
            currency="USD",
            idempotency_key="revenue-0001",
        )


def _service(tmp_path: Path) -> RevenueService:
    repository = CrmRepository(tmp_path / "crm.sqlite3")
    repository.save_company(
        Company(
            company_id="company-0001",
            tenant_id="tenant-0001",
            name="Acme Logistics",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repository.save_pipeline(
        Pipeline(
            pipeline_id="pipeline-0001",
            tenant_id="tenant-0001",
            name="New business",
            stages=(
                PipelineStage(
                    stage_id="stage-0001",
                    pipeline_id="pipeline-0001",
                    tenant_id="tenant-0001",
                    name="Qualified",
                    position=1,
                    probability=0.5,
                ),
            ),
        )
    )
    return RevenueService(repository)


def _event(
    event_id: str,
    event_type: RevenueEventType,
    effective_at: datetime,
    recorded_at: datetime = NOW,
    mrr_minor_after: int = 10000,
    idempotency_key: str | None = None,
) -> RevenueEventCreate:
    return RevenueEventCreate(
        event_id=event_id,
        subscription_id="subscription-0001",
        company_id="company-0001",
        event_type=event_type,
        effective_at=effective_at,
        recorded_at=recorded_at,
        mrr_minor_after=mrr_minor_after,
        currency="USD",
        idempotency_key=idempotency_key or event_id,
    )


def test_revenue_report_orders_late_events_by_effective_time(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.ingest_event(
        "tenant-0001",
        _event(
            "revenue-event-expansion1",
            RevenueEventType.EXPANDED,
            datetime(2026, 8, 3, 12, 0, tzinfo=UTC),
            mrr_minor_after=15000,
        ),
    )
    service.ingest_event(
        "tenant-0001",
        _event(
            "revenue-event-converted1",
            RevenueEventType.CONVERTED,
            datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
            mrr_minor_after=10000,
        ),
    )
    service.ingest_event(
        "tenant-0001",
        _event(
            "revenue-event-cancelled1",
            RevenueEventType.CANCELLED,
            datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
            recorded_at=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
            mrr_minor_after=0,
        ),
    )

    report = service.report("tenant-0001", date(2026, 8, 5), "USD")

    assert report.mrr_minor == 0
    assert report.new_business.amount_minor == 10000
    assert report.expansion.amount_minor == 5000
    assert report.churn.amount_minor == 15000
    assert {warning.code for warning in report.warnings} == {"late_arrival"}
    assert report.expansion.event_ids == ("revenue-event-expansion1",)


def test_revenue_event_replay_is_idempotent_and_conflicts_are_rejected(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    payload = _event("revenue-event-replay1", RevenueEventType.CONVERTED, NOW)

    first = service.ingest_event("tenant-0001", payload)
    replay = service.ingest_event("tenant-0001", payload)

    assert replay == first
    with pytest.raises(CrmConflictError):
        service.ingest_event(
            "tenant-0001",
            payload.model_copy(update={"mrr_minor_after": 20000}),
        )


def test_revenue_event_cannot_reference_a_foreign_company(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(CrmConflictError, match="same tenant"):
        service.ingest_event(
            "tenant-0002",
            _event("revenue-event-foreign1", RevenueEventType.CONVERTED, NOW),
        )
