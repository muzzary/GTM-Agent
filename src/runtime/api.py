import os
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Header, Query, Request, status
from fastapi.responses import JSONResponse

from src.agent.contracts import AgentRunRequest, AgentRunResult
from src.agent.runtime import ControlledAgentRuntime
from src.agent.test_double import DeterministicCrmAgent
from src.agent.tools import CrmToolRegistry
from src.crm.integration import CampaignCrmLinker
from src.crm.service import CrmService
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
from src.revenue.service import RevenueService
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
    ProspectCrmLinkRequest,
    ProspectCrmLinkResult,
)
from src.schemas.research import (
    ProspectResearchRequest,
    ResearchProblem,
    ResearchRequest,
    ResearchRun,
)
from src.schemas.revenue import RevenueEvent, RevenueEventCreate, RevenueReport

settings = Settings.from_mapping(os.environ)


def create_app(
    workflow: CampaignWorkflow | None = None,
    app_settings: Settings | None = None,
    crm_repository: CrmRepository | None = None,
) -> FastAPI:
    application = FastAPI(title="GTM Agent", version="0.4.0")
    campaign_workflow = workflow or _default_workflow(app_settings or settings)
    crm_store = crm_repository or CrmRepository((app_settings or settings).crm_path)
    crm_service = CrmService(crm_store)
    revenue_service = RevenueService(crm_store)
    crm_linker = CampaignCrmLinker(crm_service, crm_store)
    application.state.campaign_workflow = campaign_workflow
    application.state.crm_store = crm_store

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

    def read_selected_prospect(tenant_id: str, campaign_id: str) -> dict[str, object]:
        campaign = campaign_workflow.get_campaign(campaign_id)
        if campaign.state is not CampaignState.PROSPECT_RESEARCHED:
            raise WorkflowConflictError(
                "selected prospect research must be completed first"
            )
        if campaign.selected_prospect_id is None:
            raise WorkflowConflictError("a selected prospect is required")
        prospect = next(
            item
            for item in campaign.prospects
            if item.prospect_id == campaign.selected_prospect_id
        )
        return {
            "tenant_id": tenant_id,
            "campaign_id": campaign_id,
            "prospect": prospect.model_dump(mode="json"),
            "research": (
                campaign.prospect_research.model_dump(mode="json")
                if campaign.prospect_research is not None
                else None
            ),
        }

    @application.post("/agent/runs", response_model=AgentRunResult)
    def run_agent(payload: AgentRunRequest, tenant_id: TenantHeader) -> AgentRunResult:
        def link_for_agent(
            agent_tenant_id: str, agent_campaign_id: str, idempotency_key: str
        ) -> dict[str, object]:
            result = crm_linker.link_selected_prospect(
                agent_tenant_id,
                campaign_workflow.get_campaign(agent_campaign_id),
                idempotency_key,
            )
            return result.model_dump(mode="json")

        registry = CrmToolRegistry(
            crm_service,
            read_selected_prospect,
            link_for_agent,
            lambda report_tenant_id, as_of, currency: revenue_service.report(
                report_tenant_id, as_of, currency
            ).model_dump(mode="json"),
        )
        runtime = ControlledAgentRuntime(registry, max_steps=payload.max_steps)
        return runtime.run(
            tenant_id=tenant_id,
            goal=payload.goal,
            model=DeterministicCrmAgent(payload.campaign_id),
            approved_call_ids=payload.approved_call_ids,
        )

    @application.post(
        "/crm/revenue/events",
        response_model=RevenueEvent,
        status_code=status.HTTP_201_CREATED,
    )
    def create_revenue_event(
        payload: RevenueEventCreate, tenant_id: TenantHeader
    ) -> RevenueEvent:
        return revenue_service.ingest_event(tenant_id, payload)

    @application.get("/crm/revenue/report", response_model=RevenueReport)
    def get_revenue_report(
        tenant_id: TenantHeader,
        as_of: date,
        currency: str = Query(default="USD", pattern=r"^[A-Z]{3}$"),
    ) -> RevenueReport:
        return revenue_service.report(tenant_id, as_of, currency)

    @application.post(
        "/campaigns/{campaign_id}/crm/company",
        response_model=ProspectCrmLinkResult,
    )
    def link_campaign_company(
        campaign_id: str,
        payload: ProspectCrmLinkRequest,
        tenant_id: TenantHeader,
    ) -> ProspectCrmLinkResult:
        campaign = campaign_workflow.get_campaign(campaign_id)
        try:
            return crm_linker.link_selected_prospect(
                tenant_id, campaign, payload.idempotency_key
            )
        except ValueError as error:
            raise WorkflowConflictError(str(error)) from error

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
        return crm_service.create_company(
            tenant_id, payload, source_evidence_ids=source_evidence_ids
        )

    @application.get("/crm/companies", response_model=list[Company])
    def list_crm_companies(tenant_id: TenantHeader) -> tuple[Company, ...]:
        return crm_service.list_companies(tenant_id)

    @application.post(
        "/crm/pipelines",
        response_model=Pipeline,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_pipeline(
        payload: PipelineCreate, tenant_id: TenantHeader
    ) -> Pipeline:
        return crm_service.create_pipeline(tenant_id, payload)

    @application.post(
        "/crm/contacts",
        response_model=Contact,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_contact(payload: ContactCreate, tenant_id: TenantHeader) -> Contact:
        return crm_service.create_contact(tenant_id, payload)

    @application.post(
        "/crm/deals",
        response_model=Deal,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_deal(payload: DealCreate, tenant_id: TenantHeader) -> Deal:
        return crm_service.create_deal(tenant_id, payload)

    @application.post(
        "/crm/activities",
        response_model=Activity,
        status_code=status.HTTP_201_CREATED,
    )
    def create_crm_activity(
        payload: ActivityCreate, tenant_id: TenantHeader
    ) -> Activity:
        return crm_service.create_activity(tenant_id, payload)

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
