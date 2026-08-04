from datetime import UTC, datetime
from uuid import uuid4

from src.data.crm_repository import CrmRepository
from src.schemas.crm import (
    Activity,
    ActivityCreate,
    Company,
    CompanyCreate,
    Contact,
    ContactCreate,
    Deal,
    DealCreate,
    DealStatus,
    Pipeline,
    PipelineCreate,
    PipelineStage,
)


class CrmService:
    """Shared CRM mutation/query path for HTTP handlers and agent tools."""

    def __init__(self, repository: CrmRepository) -> None:
        self.repository = repository

    def create_company(
        self,
        tenant_id: str,
        payload: CompanyCreate,
        *,
        source_evidence_ids: tuple[str, ...] | None = None,
    ) -> Company:
        now = _now()
        return self.repository.save_company(
            Company(
                company_id=payload.company_id or _id("company"),
                tenant_id=tenant_id,
                name=payload.name,
                normalized_domain=payload.normalized_domain,
                website=payload.website,
                industry=payload.industry,
                region=payload.region,
                custom_fields=payload.custom_fields,
                source_prospect_id=payload.source_prospect_id,
                source_campaign_id=payload.source_campaign_id,
                source_evidence_ids=(
                    source_evidence_ids
                    if source_evidence_ids is not None
                    else tuple(payload.source_evidence_ids)
                ),
                created_at=now,
                updated_at=now,
            )
        )

    def list_companies(self, tenant_id: str) -> tuple[Company, ...]:
        return self.repository.list_companies(tenant_id)

    def create_pipeline(self, tenant_id: str, payload: PipelineCreate) -> Pipeline:
        pipeline_id = payload.pipeline_id or _id("pipeline")
        return self.repository.save_pipeline(
            Pipeline(
                pipeline_id=pipeline_id,
                tenant_id=tenant_id,
                name=payload.name,
                stages=tuple(
                    PipelineStage(
                        stage_id=stage.stage_id or _id("stage"),
                        pipeline_id=pipeline_id,
                        tenant_id=tenant_id,
                        name=stage.name,
                        position=stage.position,
                        probability=stage.probability,
                    )
                    for stage in payload.stages
                ),
            )
        )

    def create_contact(self, tenant_id: str, payload: ContactCreate) -> Contact:
        now = _now()
        return self.repository.save_contact(
            Contact(
                contact_id=payload.contact_id or _id("contact"),
                company_id=payload.company_id,
                tenant_id=tenant_id,
                full_name=payload.full_name,
                role=payload.role,
                business_email=payload.business_email,
                custom_fields=payload.custom_fields,
                created_at=now,
                updated_at=now,
            )
        )

    def create_deal(self, tenant_id: str, payload: DealCreate) -> Deal:
        now = _now()
        deal = Deal(
            deal_id=payload.deal_id or _id("deal"),
            company_id=payload.company_id,
            contact_id=payload.contact_id,
            pipeline_id=payload.pipeline_id,
            stage_id=payload.stage_id,
            tenant_id=tenant_id,
            name=payload.name,
            status=DealStatus.OPEN,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            custom_fields=payload.custom_fields,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_deal(
            deal,
            idempotency_key=payload.idempotency_key,
            idempotency_fingerprint=payload.model_dump_json(
                exclude={"idempotency_key"}
            ),
        )

    def create_activity(self, tenant_id: str, payload: ActivityCreate) -> Activity:
        return self.repository.save_activity(
            Activity(
                activity_id=payload.activity_id or _id("activity"),
                tenant_id=tenant_id,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                activity_type=payload.activity_type,
                summary=payload.summary,
                occurred_at=payload.occurred_at,
            )
        )


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _now() -> datetime:
    return datetime.now(UTC)
