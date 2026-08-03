from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.schemas.crm import (
    Activity,
    ActivityType,
    Company,
    Contact,
    CustomFieldDefinition,
    CustomFieldType,
    Deal,
    DealStatus,
    Pipeline,
    PipelineStage,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def test_crm_records_round_trip_with_tenant_ownership() -> None:
    stage = PipelineStage(
        stage_id="stage-0001",
        pipeline_id="pipeline-0001",
        tenant_id="tenant-0001",
        name="Qualified",
        position=1,
        probability=0.35,
    )
    pipeline = Pipeline(
        pipeline_id="pipeline-0001",
        tenant_id="tenant-0001",
        name="New business",
        stages=(stage,),
    )
    company = Company(
        company_id="company-0001",
        tenant_id="tenant-0001",
        name="Acme Logistics",
        normalized_domain="acme-logistics.example",
        region="United States",
        created_at=NOW,
        updated_at=NOW,
    )
    contact = Contact(
        contact_id="contact-0001",
        company_id=company.company_id,
        tenant_id=company.tenant_id,
        full_name="Jordan Lee",
        role="VP Operations",
        business_email="jordan@example.com",
        created_at=NOW,
        updated_at=NOW,
    )
    deal = Deal(
        deal_id="deal-0001",
        company_id=company.company_id,
        contact_id=contact.contact_id,
        pipeline_id=pipeline.pipeline_id,
        stage_id=stage.stage_id,
        tenant_id=company.tenant_id,
        name="Acme Logistics expansion",
        status=DealStatus.OPEN,
        amount_minor=240_000,
        currency="USD",
        created_at=NOW,
        updated_at=NOW,
    )
    activity = Activity(
        activity_id="activity-0001",
        tenant_id=company.tenant_id,
        entity_type="deal",
        entity_id=deal.deal_id,
        activity_type=ActivityType.RESEARCH,
        summary="Selected prospect research completed.",
        occurred_at=NOW,
    )

    assert Pipeline.model_validate_json(pipeline.model_dump_json()) == pipeline
    assert Company.model_validate_json(company.model_dump_json()) == company
    assert Contact.model_validate_json(contact.model_dump_json()) == contact
    assert Deal.model_validate_json(deal.model_dump_json()) == deal
    assert Activity.model_validate_json(activity.model_dump_json()) == activity


def test_crm_models_reject_unknown_fields_and_invalid_ids() -> None:
    with pytest.raises(ValidationError):
        Company(
            company_id="company-0001",
            tenant_id="tenant-0001",
            name="Acme",
            created_at=NOW,
            updated_at=NOW,
            unexpected="not allowed",
        )

    with pytest.raises(ValidationError):
        Contact(
            contact_id="contact-0001",
            company_id="company-0001",
            tenant_id="tenant_bad",
            full_name="Jordan Lee",
            role="VP Operations",
            created_at=NOW,
            updated_at=NOW,
        )


def test_custom_field_definition_is_bounded_and_strict() -> None:
    definition = CustomFieldDefinition(
        field_id="custom-field-0001",
        tenant_id="tenant-0001",
        entity_type="company",
        key="account_tier",
        label="Account tier",
        field_type=CustomFieldType.TEXT,
    )

    assert (
        CustomFieldDefinition.model_validate_json(definition.model_dump_json())
        == definition
    )

    with pytest.raises(ValidationError):
        CustomFieldDefinition(
            field_id="custom-field-0001",
            tenant_id="tenant-0001",
            entity_type="company",
            key="bad key",
            label="Account tier",
            field_type=CustomFieldType.TEXT,
        )


def test_deal_rejects_invalid_money_and_probability() -> None:
    with pytest.raises(ValidationError):
        Deal(
            deal_id="deal-0001",
            company_id="company-0001",
            pipeline_id="pipeline-0001",
            stage_id="stage-0001",
            tenant_id="tenant-0001",
            name="Invalid deal",
            status=DealStatus.OPEN,
            amount_minor=-1,
            currency="USD",
            created_at=NOW,
            updated_at=NOW,
        )

    with pytest.raises(ValidationError):
        PipelineStage(
            stage_id="stage-0001",
            pipeline_id="pipeline-0001",
            tenant_id="tenant-0001",
            name="Qualified",
            position=1,
            probability=1.1,
        )
