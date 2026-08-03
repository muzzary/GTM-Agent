from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.data.crm_repository import CrmConflictError, CrmNotFoundError, CrmRepository
from src.schemas.crm import (
    Company,
    Contact,
    Deal,
    DealStatus,
    Pipeline,
    PipelineStage,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def company(tenant_id: str = "tenant-0001") -> Company:
    return Company(
        company_id="company-0001" if tenant_id == "tenant-0001" else "company-0002",
        tenant_id=tenant_id,
        name="Acme Logistics",
        normalized_domain="acme.example",
        created_at=NOW,
        updated_at=NOW,
    )


def pipeline(tenant_id: str = "tenant-0001") -> Pipeline:
    pipeline_id = "pipeline-0001" if tenant_id == "tenant-0001" else "pipeline-0002"
    stage_id = "stage-0001" if tenant_id == "tenant-0001" else "stage-0002"
    return Pipeline(
        pipeline_id=pipeline_id,
        tenant_id=tenant_id,
        name="New business",
        stages=(
            PipelineStage(
                stage_id=stage_id,
                pipeline_id=pipeline_id,
                tenant_id=tenant_id,
                name="Qualified",
                position=1,
                probability=0.35,
            ),
        ),
    )


def deal() -> Deal:
    return Deal(
        deal_id="deal-0001",
        company_id="company-0001",
        pipeline_id="pipeline-0001",
        stage_id="stage-0001",
        tenant_id="tenant-0001",
        name="Acme expansion",
        status=DealStatus.OPEN,
        amount_minor=100_000,
        currency="USD",
        created_at=NOW,
        updated_at=NOW,
    )


def test_repository_round_trips_records_and_limits_lists_to_tenant(
    tmp_path: Path,
) -> None:
    repository = CrmRepository(tmp_path / "crm.sqlite3")
    repository.save_company(company())
    repository.save_company(company("tenant-0002"))
    repository.save_pipeline(pipeline())

    contact = Contact(
        contact_id="contact-0001",
        company_id="company-0001",
        tenant_id="tenant-0001",
        full_name="Jordan Lee",
        role="VP Operations",
        created_at=NOW,
        updated_at=NOW,
    )
    repository.save_contact(contact)
    repository.save_deal(deal(), idempotency_key="create-acme-0001")

    assert repository.get_company("tenant-0001", "company-0001") == company()
    assert repository.get_contact("tenant-0001", "contact-0001") == contact
    assert repository.get_deal("tenant-0001", "deal-0001") == deal()
    assert [item.company_id for item in repository.list_companies("tenant-0001")] == [
        "company-0001"
    ]

    with pytest.raises(CrmNotFoundError):
        repository.get_company("tenant-0002", "company-0001")


def test_repository_rejects_cross_tenant_relationships(tmp_path: Path) -> None:
    repository = CrmRepository(tmp_path / "crm.sqlite3")
    repository.save_company(company())

    foreign_contact = Contact(
        contact_id="contact-0001",
        company_id="company-0001",
        tenant_id="tenant-0002",
        full_name="Jordan Lee",
        role="VP Operations",
        created_at=NOW,
        updated_at=NOW,
    )
    with pytest.raises(CrmConflictError, match="same tenant"):
        repository.save_contact(foreign_contact)


def test_deal_creation_is_idempotent_and_detects_key_reuse(tmp_path: Path) -> None:
    repository = CrmRepository(tmp_path / "crm.sqlite3")
    repository.save_company(company())
    repository.save_pipeline(pipeline())

    created = repository.save_deal(deal(), idempotency_key="create-acme-0001")
    repeated = repository.save_deal(deal(), idempotency_key="create-acme-0001")
    assert repeated == created

    changed = deal().model_copy(update={"amount_minor": 200_000})
    with pytest.raises(CrmConflictError, match="idempotency key"):
        repository.save_deal(changed, idempotency_key="create-acme-0001")


def test_repository_rejects_deal_with_unknown_stage(tmp_path: Path) -> None:
    repository = CrmRepository(tmp_path / "crm.sqlite3")
    repository.save_company(company())
    repository.save_pipeline(pipeline())
    invalid = deal().model_copy(update={"stage_id": "stage-9999"})

    with pytest.raises(CrmConflictError, match="stage"):
        repository.save_deal(invalid, idempotency_key="create-invalid-0001")
