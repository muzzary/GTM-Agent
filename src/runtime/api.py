import os

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.runtime.fixtures import DeterministicFixturePipeline
from src.runtime.settings import Settings
from src.runtime.workflow import (
    CampaignNotFoundError,
    CampaignWorkflow,
    InMemoryCampaignRepository,
    WorkflowConflictError,
)
from src.schemas.campaign import (
    Campaign,
    CampaignInput,
    ClaimDecisionBatch,
    ProspectCandidate,
    TraceEvent,
)

settings = Settings.from_mapping(os.environ)


def create_app(workflow: CampaignWorkflow | None = None) -> FastAPI:
    application = FastAPI(title="GTM Agent", version="0.2.0")
    campaign_workflow = workflow or CampaignWorkflow(
        repository=InMemoryCampaignRepository(),
        pipeline=DeterministicFixturePipeline(),
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

    @application.exception_handler(WorkflowConflictError)
    async def workflow_conflict(
        _request: Request,
        error: WorkflowConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(error)},
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


app = create_app()
