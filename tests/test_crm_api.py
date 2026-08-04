from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from src.data.crm_repository import CrmRepository
from src.runtime.api import create_app
from src.runtime.fixtures import DeterministicFixturePipeline
from src.runtime.workflow import CampaignWorkflow, InMemoryCampaignRepository


class SequentialIds:
    def __init__(self) -> None:
        self._counts: defaultdict[str, int] = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self._counts[prefix] += 1
        return f"{prefix}-{self._counts[prefix]:08d}"


def build_client(tmp_path: Path) -> TestClient:
    workflow = CampaignWorkflow(
        repository=InMemoryCampaignRepository(),
        pipeline=DeterministicFixturePipeline(),
        new_id=SequentialIds(),
        clock=lambda: datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
    )
    return TestClient(
        create_app(workflow, crm_repository=CrmRepository(tmp_path / "crm.sqlite3"))
    )


TENANT = {"X-Tenant-ID": "tenant-0001"}


def create_researched_campaign(client: TestClient) -> str:
    created = client.post(
        "/campaigns",
        json={
            "product_name": "RouteSignal",
            "product_url": "https://example.com/routesignal",
            "short_description": "Highlights recurring delivery exceptions.",
            "known_capabilities": ["exception reporting"],
            "known_limitations": ["requires dispatch data"],
            "icp": {
                "industries": ["logistics"],
                "company_size": "mid-market",
                "roles": ["Head of Operations"],
                "pain_hypotheses": ["manual exception review"],
            },
        },
    ).json()
    client.post(
        f"/campaigns/{created['campaign_id']}/claim-decisions",
        json={
            "decisions": [
                {
                    "claim_id": claim["claim_id"],
                    "decision": "approved" if index == 0 else "rejected",
                }
                for index, claim in enumerate(created["claims"])
            ]
        },
    )
    prospect = client.get(f"/campaigns/{created['campaign_id']}/prospects").json()[0]
    client.post(
        f"/campaigns/{created['campaign_id']}/prospects/{prospect['prospect_id']}/select"
    )
    client.post(
        f"/campaigns/{created['campaign_id']}/prospects/{prospect['prospect_id']}"
        "/research-runs",
        json={"request_id": "research-request-agent-0001"},
    )
    return created["campaign_id"]


def test_crm_api_creates_pipeline_company_contact_and_deal(tmp_path: Path) -> None:
    client = build_client(tmp_path)

    pipeline_response = client.post(
        "/crm/pipelines",
        headers=TENANT,
        json={
            "pipeline_id": "pipeline-0001",
            "name": "New business",
            "stages": [
                {
                    "stage_id": "stage-0001",
                    "name": "Qualified",
                    "position": 1,
                    "probability": 0.35,
                }
            ],
        },
    )
    assert pipeline_response.status_code == 201

    company_response = client.post(
        "/crm/companies",
        headers=TENANT,
        json={"company_id": "company-0001", "name": "Acme Logistics"},
    )
    assert company_response.status_code == 201

    contact_response = client.post(
        "/crm/contacts",
        headers=TENANT,
        json={
            "contact_id": "contact-0001",
            "company_id": "company-0001",
            "full_name": "Jordan Lee",
            "role": "VP Operations",
        },
    )
    assert contact_response.status_code == 201

    deal_response = client.post(
        "/crm/deals",
        headers=TENANT,
        json={
            "deal_id": "deal-0001",
            "company_id": "company-0001",
            "contact_id": "contact-0001",
            "pipeline_id": "pipeline-0001",
            "stage_id": "stage-0001",
            "name": "Acme expansion",
            "amount_minor": 100000,
            "currency": "USD",
            "idempotency_key": "deal-create-0001",
        },
    )
    assert deal_response.status_code == 201

    assert deal_response.json()["tenant_id"] == "tenant-0001"

    replay = client.post(
        "/crm/deals",
        headers=TENANT,
        json={
            "deal_id": "deal-0001",
            "company_id": "company-0001",
            "contact_id": "contact-0001",
            "pipeline_id": "pipeline-0001",
            "stage_id": "stage-0001",
            "name": "Acme expansion",
            "amount_minor": 100000,
            "currency": "USD",
            "idempotency_key": "deal-create-0001",
        },
    )
    assert replay.status_code == 201
    assert replay.json() == deal_response.json()


def test_agent_api_inspects_researched_prospect_without_mutation(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    campaign_id = create_researched_campaign(client)

    response = client.post(
        "/agent/runs",
        headers=TENANT,
        json={
            "goal": "Inspect the selected prospect",
            "campaign_id": campaign_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["outputs"][0]["result"]["prospect"]["prospect_id"].startswith(
        "prospect-"
    )
    assert [entry["status"] for entry in body["trace"]] == [
        "tool_called",
        "succeeded",
        "final",
    ]


def test_crm_api_rejects_missing_tenant_and_foreign_company(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    missing_tenant = client.get("/crm/companies")
    assert missing_tenant.status_code == 422

    created = client.post(
        "/crm/companies",
        headers=TENANT,
        json={"company_id": "company-0001", "name": "Acme Logistics"},
    )
    assert created.status_code == 201

    foreign_contact = client.post(
        "/crm/contacts",
        headers={"X-Tenant-ID": "tenant-0002"},
        json={
            "contact_id": "contact-0001",
            "company_id": "company-0001",
            "full_name": "Jordan Lee",
            "role": "VP Operations",
        },
    )
    assert foreign_contact.status_code == 409


def test_crm_api_records_and_lists_activities(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    client.post(
        "/crm/companies",
        headers=TENANT,
        json={"company_id": "company-0001", "name": "Acme Logistics"},
    )
    response = client.post(
        "/crm/activities",
        headers=TENANT,
        json={
            "activity_id": "activity-0001",
            "entity_type": "company",
            "entity_id": "company-0001",
            "activity_type": "research",
            "summary": "Research profile completed.",
            "occurred_at": "2026-08-04T12:00:00Z",
        },
    )
    assert response.status_code == 201

    listed = client.get("/crm/activities/company/company-0001", headers=TENANT)
    assert listed.status_code == 200
    assert listed.json()[0]["activity_id"] == "activity-0001"


def test_crm_api_links_only_the_researched_prospect_and_preserves_evidence(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    created = client.post(
        "/campaigns",
        json={
            "product_name": "RouteSignal",
            "short_description": "Highlights recurring delivery exceptions.",
            "known_capabilities": ["exception reporting"],
            "known_limitations": [],
            "icp": {
                "industries": ["logistics"],
                "company_size": "mid-market",
                "roles": ["Head of Operations"],
                "pain_hypotheses": ["manual exception review"],
            },
        },
    ).json()
    campaign_id = created["campaign_id"]
    client.post(
        f"/campaigns/{campaign_id}/claim-decisions",
        json={
            "decisions": [
                {
                    "claim_id": claim["claim_id"],
                    "decision": "approved" if index == 0 else "rejected",
                }
                for index, claim in enumerate(created["claims"])
            ]
        },
    )
    prospects = client.get(f"/campaigns/{campaign_id}/prospects").json()
    selected = prospects[0]
    client.post(f"/campaigns/{campaign_id}/prospects/{selected['prospect_id']}/select")
    client.post(
        f"/campaigns/{campaign_id}/prospects/{selected['prospect_id']}/research-runs",
        json={"request_id": "research-request-crm00001"},
    )

    linked = client.post(
        "/crm/companies",
        headers=TENANT,
        json={
            "name": selected["company"],
            "source_campaign_id": campaign_id,
            "source_prospect_id": selected["prospect_id"],
        },
    )
    assert linked.status_code == 201
    assert linked.json()["source_campaign_id"] == campaign_id
    assert linked.json()["source_evidence_ids"] == selected["evidence_ids"]

    forged = client.post(
        "/crm/companies",
        headers=TENANT,
        json={
            "name": "Forged company",
            "source_campaign_id": campaign_id,
            "source_prospect_id": prospects[1]["prospect_id"],
        },
    )
    assert forged.status_code == 409
