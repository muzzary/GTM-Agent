import os

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.data.http_collector import ControlledHttpCollector, HttpxTransport
from src.data.research_cache import ResearchCache
from src.data.source_policy import system_resolver
from src.research.discovery import DiscoveryService
from src.research.prospect import ProspectResearchService
from src.research.providers import (
    MarketSeedDiscoveryProvider,
    WebsiteCandidateExpander,
    WikidataDiscoveryProvider,
)
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
    ClaimDecisionBatch,
    ProspectCandidate,
    ResearchOutcome,
    TraceEvent,
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
) -> FastAPI:
    application = FastAPI(title="GTM Agent", version="0.4.0")
    campaign_workflow = workflow or _default_workflow(app_settings or settings)

    @application.exception_handler(CampaignNotFoundError)
    async def campaign_not_found(
        _request: Request,
        error: CampaignNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
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

    return application


def _default_workflow(app_settings: Settings) -> CampaignWorkflow:
    common = {
        "repository": InMemoryCampaignRepository(),
        "pipeline": DeterministicFixturePipeline(),
    }
    if app_settings.research_contact is None:
        return CampaignWorkflow(**common)
    user_agent = f"GTM-Agent/0.4 ({app_settings.research_contact})"
    collector = ControlledHttpCollector(
        transport=HttpxTransport(user_agent),
        resolver=system_resolver,
        research_contact=app_settings.research_contact,
        cache=ResearchCache(app_settings.research_cache_path),
    )
    expander = WebsiteCandidateExpander(collector)
    discovery = DiscoveryService(
        providers=(
            WikidataDiscoveryProvider(collector),
            MarketSeedDiscoveryProvider(collector),
        ),
        expander=expander,
    )
    return CampaignWorkflow(
        **common,
        discovery_runner=discovery,
        prospect_research_runner=ProspectResearchService(collector),
    )


app = create_app()
