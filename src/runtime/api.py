import os
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Header, Request, status
from fastapi.responses import JSONResponse

from src.data.crm_repository import CrmConflictError, CrmNotFoundError, CrmRepository
from src.data.http_collector import ControlledHttpCollector, HttpxTransport
from src.data.research_cache import ResearchCache
from src.data.source_policy import system_resolver
from src.research.discovery import DiscoveryService
from src.research.prospect import ProspectResearchService
from src.research.providers import (
    BraveSearchDiscoveryProvider,
    MarketSeedDiscoveryProvider,
    WebsiteCandidateExpander,
    WikidataDiscoveryProvider,
)
from src.research.translation import ColabResearchTranslator
from src.runtime.fixtures import DeterministicFixturePipeline
from src.runtime.settings import Settings
from src.runtime.workflow import (
    CampaignNotFoundError,
    CampaignWorkflow,
    InMemoryCampaignRepository,
    ResearchExecutionError,
    ResearchUnavailableError,
    WorkflowConflictError,
)
from src.schemas.campaign import (
    Campaign,
    CampaignInput,
    CampaignState,
    ClaimDecisionBatch,
    ProspectCandidate,
    ResearchOutcome,
    TraceEvent,
)
from src.schemas.crm import (
    Activity,
    ActivityCreate,
    Company,
    CompanyCreate,
    Contact,
    ContactCreate,
    Deal,
    DealCreate,
    Pipeline,
    PipelineCreate,
    PipelineStage,
)
from src.schemas.research import (
    ProspectResearchRequest,
    ResearchProblem,
    ResearchRequest,
    ResearchRun,
)

settings = Settings.from_mapping(os.environ)


def create_app(
    workflow: CampaignWorkflow | None = None,
    app_settings: Settings | None = None,
    crm_repository: CrmRepository | None = None,
) -> FastAPI:
    application = FastAPI(title="GTM Agent", version="0.4.0")
    campaign_workflow = workflow or _default_workflow(app_settings or settings)
    crm_store = crm_repository or CrmRepository(
        (app_settings or settings).crm_path
    )

    @application.exception_handler(CampaignNotFoundError)
    async def campaign_not_found(
        _request: Request,
        error: CampaignNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(error)},
        )

    @application.exception_handler(CrmNotFoundError)
    async def crm_not_found(
        _request: Request,
        error: CrmNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(error)},
        )

    @application.exception_handler(CrmConflictError)
    async def crm_conflict(
        _request: Request,
        error: CrmConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(error)},
        )

    @application.exception_handler(WorkflowConflictError)
    async def workflow_conflict(
        _request: Request,
        error: WorkflowConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(error)},
        )

    @application.exception_handler(ResearchUnavailableError)
    async def research_unavailable(
        _request: Request,
        error: ResearchUnavailableError,
    ) -> JSONResponse:
        problem = ResearchProblem(
            title="Public research unavailable",
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
            code="research_not_configured",
        )
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    @application.exception_handler(ResearchExecutionError)
    async def research_failed(
        _request: Request,
        error: ResearchExecutionError,
    ) -> JSONResponse:
        problem = ResearchProblem(
            title="Public research failed",
            status=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
            code=error.code,
            research_run_id=error.run_id,
        )
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"service": "gtm-agent", "status": "ok"}

    @application.post(
        "/campaigns",
        response_model=Campaign,
        status_code=status.HTTP_201_CREATED,
    )
    def create_campaign(campaign_input: CampaignInput) -> Campaign:
        return campaign_workflow.create_campaign(campaign_input)

    @application.get("/campaigns/{campaign_id}", response_model=Campaign)
    def get_campaign(campaign_id: str) -> Campaign:
        return campaign_workflow.get_campaign(campaign_id)

    @application.post(
        "/campaigns/{campaign_id}/claim-decisions",
        response_model=Campaign,
    )
    def decide_claims(
        campaign_id: str,
        batch: ClaimDecisionBatch,
    ) -> Campaign:
        return campaign_workflow.decide_claims(campaign_id, batch)

    @application.post(
        "/campaigns/{campaign_id}/discovery-runs",
        response_model=ResearchOutcome,
    )
    def run_discovery(
        campaign_id: str,
        research_request: ResearchRequest,
    ) -> ResearchOutcome:
        return campaign_workflow.run_discovery(campaign_id, research_request)

    @application.get(
        "/campaigns/{campaign_id}/prospects",
        response_model=list[ProspectCandidate],
    )
    def list_prospects(campaign_id: str) -> tuple[ProspectCandidate, ...]:
        return campaign_workflow.list_prospects(campaign_id)

    @application.post(
        "/campaigns/{campaign_id}/prospects/{prospect_id}/select",
        response_model=Campaign,
    )
    def select_prospect(campaign_id: str, prospect_id: str) -> Campaign:
        return campaign_workflow.select_prospect(campaign_id, prospect_id)

    @application.post(
        "/campaigns/{campaign_id}/prospects/{prospect_id}/research-runs",
        response_model=ResearchOutcome,
    )
    def research_prospect(
        campaign_id: str,
        prospect_id: str,
        research_request: ProspectResearchRequest,
    ) -> ResearchOutcome:
        return campaign_workflow.research_prospect(
            campaign_id, prospect_id, research_request
        )

    @application.get(
        "/campaigns/{campaign_id}/research-runs/{run_id}",
        response_model=ResearchRun,
    )
    def get_research_run(campaign_id: str, run_id: str) -> ResearchRun:
        return campaign_workflow.get_research_run(campaign_id, run_id)

    @application.post(
        "/campaigns/{campaign_id}/draft",
        response_model=Campaign,
    )
    def generate_draft(campaign_id: str) -> Campaign:
        return campaign_workflow.generate_draft(campaign_id)

    @application.get(
        "/campaigns/{campaign_id}/trace",
        response_model=list[TraceEvent],
    )
    def get_trace(campaign_id: str) -> tuple[TraceEvent, ...]:
        return campaign_workflow.get_trace(campaign_id)

    TenantHeader = Annotated[
        str, Header(alias="X-Tenant-ID", pattern=r"^tenant-[a-z0-9-]{4,64}$")
    ]

    @application.post(
        "/crm/companies",
        response_model=Company,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_company(payload: CompanyCreate, tenant_id: TenantHeader) -> Company:
        source_campaign_id = payload.source_campaign_id
        source_evidence_ids: tuple[str, ...] = tuple()
        if (payload.source_prospect_id is None) != (source_campaign_id is None):
            raise CrmConflictError(
                "source campaign and source prospect must be provided together"
            )
        if source_campaign_id is not None and payload.source_prospect_id is not None:
            campaign = campaign_workflow.get_campaign(source_campaign_id)
            if campaign.state is not CampaignState.PROSPECT_RESEARCHED:
                raise CrmConflictError(
                    "only a researched prospect can be linked to a CRM company"
                )
            if campaign.selected_prospect_id != payload.source_prospect_id:
                raise CrmConflictError(
                    "only the selected prospect can be linked to a CRM company"
                )
            prospect = next(
                item
                for item in campaign.prospects
                if item.prospect_id == payload.source_prospect_id
            )
            source_evidence_ids = prospect.evidence_ids
            if (
                payload.source_evidence_ids
                and tuple(payload.source_evidence_ids) != source_evidence_ids
            ):
                raise CrmConflictError(
                    "source evidence does not match the selected prospect"
                )
        now = _crm_now()
        company = Company(
            company_id=payload.company_id or _crm_id("company"),
            tenant_id=tenant_id,
            name=payload.name,
            normalized_domain=payload.normalized_domain,
            website=payload.website,
            industry=payload.industry,
            region=payload.region,
            custom_fields=payload.custom_fields,
            source_prospect_id=payload.source_prospect_id,
            source_campaign_id=source_campaign_id,
            source_evidence_ids=source_evidence_ids,
            created_at=now,
            updated_at=now,
        )
        return crm_store.save_company(company)

    @application.get("/crm/companies", response_model=list[Company])
    def list_crm_companies(tenant_id: TenantHeader) -> tuple[Company, ...]:
        return crm_store.list_companies(tenant_id)

    @application.post(
        "/crm/pipelines",
        response_model=Pipeline,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_pipeline(
        payload: PipelineCreate, tenant_id: TenantHeader
    ) -> Pipeline:
        pipeline_id = payload.pipeline_id or _crm_id("pipeline")
        pipeline = Pipeline(
            pipeline_id=pipeline_id,
            tenant_id=tenant_id,
            name=payload.name,
            stages=tuple(
                PipelineStage(
                    stage_id=stage.stage_id or _crm_id("stage"),
                    pipeline_id=pipeline_id,
                    tenant_id=tenant_id,
                    name=stage.name,
                    position=stage.position,
                    probability=stage.probability,
                )
                for stage in payload.stages
            ),
        )
        return crm_store.save_pipeline(pipeline)

    @application.post(
        "/crm/contacts",
        response_model=Contact,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_contact(payload: ContactCreate, tenant_id: TenantHeader) -> Contact:
        now = _crm_now()
        contact = Contact(
            contact_id=payload.contact_id or _crm_id("contact"),
            company_id=payload.company_id,
            tenant_id=tenant_id,
            full_name=payload.full_name,
            role=payload.role,
            business_email=payload.business_email,
            custom_fields=payload.custom_fields,
            created_at=now,
            updated_at=now,
        )
        return crm_store.save_contact(contact)

    @application.post(
        "/crm/deals",
        response_model=Deal,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_deal(payload: DealCreate, tenant_id: TenantHeader) -> Deal:
        now = _crm_now()
        deal = Deal(
            deal_id=payload.deal_id or _crm_id("deal"),
            company_id=payload.company_id,
            contact_id=payload.contact_id,
            pipeline_id=payload.pipeline_id,
            stage_id=payload.stage_id,
            tenant_id=tenant_id,
            name=payload.name,
            status="open",
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            custom_fields=payload.custom_fields,
            created_at=now,
            updated_at=now,
        )
        return crm_store.save_deal(
            deal,
            idempotency_key=payload.idempotency_key,
            idempotency_fingerprint=payload.model_dump_json(
                exclude={"idempotency_key"}
            ),
        )

    @application.post(
        "/crm/activities",
        response_model=Activity,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_activity(
        payload: ActivityCreate, tenant_id: TenantHeader
    ) -> Activity:
        activity = Activity(
            activity_id=payload.activity_id or _crm_id("activity"),
            tenant_id=tenant_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            activity_type=payload.activity_type,
            summary=payload.summary,
            occurred_at=payload.occurred_at,
        )
        return crm_store.save_activity(activity)

    @application.get(
        "/crm/activities/{entity_type}/{entity_id}",
        response_model=list[Activity],
    )
    def list_crm_activities(
        entity_type: str,
        entity_id: str,
        tenant_id: TenantHeader,
    ) -> tuple[Activity, ...]:
        return crm_store.list_activities(tenant_id, entity_type, entity_id)

    return application


def _default_workflow(app_settings: Settings) -> CampaignWorkflow:
    common = {
        "repository": InMemoryCampaignRepository(),
        "pipeline": DeterministicFixturePipeline(),
    }
    if app_settings.research_contact is None:
        return CampaignWorkflow(**common)
    user_agent = f"GTM-Agent/0.4 ({app_settings.research_contact})"
    transport = HttpxTransport(user_agent)
    collector = ControlledHttpCollector(
        transport=transport,
        resolver=system_resolver,
        research_contact=app_settings.research_contact,
        cache=ResearchCache(app_settings.research_cache_path),
    )
    expander = WebsiteCandidateExpander(collector)
    providers = [
        WikidataDiscoveryProvider(collector),
        MarketSeedDiscoveryProvider(collector),
    ]
    if app_settings.brave_search_api_key is not None:
        providers.append(
            BraveSearchDiscoveryProvider(
                transport,
                app_settings.brave_search_api_key.get_secret_value(),
            )
        )
    discovery = DiscoveryService(
        providers=tuple(providers),
        expander=expander,
    )
    translator = None
    if (
        app_settings.translation_endpoint is not None
        and app_settings.translation_api_key is not None
    ):
        translator = ColabResearchTranslator(
            app_settings.translation_endpoint,
            app_settings.translation_api_key.get_secret_value(),
        )
    return CampaignWorkflow(
        **common,
        discovery_runner=discovery,
        prospect_research_runner=ProspectResearchService(collector, translator),
    )


def _crm_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _crm_now() -> datetime:
    return datetime.now(UTC)


app = create_app()
