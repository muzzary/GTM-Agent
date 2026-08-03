from collections import defaultdict
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.runtime.api import create_app
from src.runtime.fixtures import DeterministicFixturePipeline
from src.runtime.workflow import CampaignWorkflow, InMemoryCampaignRepository


class SequentialIds:
    def __init__(self) -> None:
        self._counts: defaultdict[str, int] = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self._counts[prefix] += 1
        return f"{prefix}-{self._counts[prefix]:08d}"


def build_client() -> TestClient:
    fixed_time = datetime(2026, 8, 2, 10, 30, tzinfo=UTC)
    workflow = CampaignWorkflow(
        repository=InMemoryCampaignRepository(),
        pipeline=DeterministicFixturePipeline(),
        new_id=SequentialIds(),
        clock=lambda: fixed_time,
    )
    return TestClient(create_app(workflow))


def valid_payload() -> dict[str, object]:
    return {
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
    }


def test_campaign_api_completes_fixture_workflow() -> None:
    client = build_client()

    create_response = client.post("/campaigns", json=valid_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    campaign_id = created["campaign_id"]
    assert created["state"] == "awaiting_claim_approval"

    decisions = [
        {
            "claim_id": claim["claim_id"],
            "decision": "approved" if index == 0 else "rejected",
        }
        for index, claim in enumerate(created["claims"])
    ]
    decision_response = client.post(
        f"/campaigns/{campaign_id}/claim-decisions",
        json={"decisions": decisions},
    )

    assert decision_response.status_code == 200
    assert decision_response.json()["state"] == "awaiting_prospect_selection"

    prospects_response = client.get(f"/campaigns/{campaign_id}/prospects")
    assert prospects_response.status_code == 200
    prospects = prospects_response.json()
    assert len(prospects) == 2

    select_response = client.post(
        f"/campaigns/{campaign_id}/prospects/{prospects[0]['prospect_id']}/select"
    )
    assert select_response.status_code == 200
    assert select_response.json()["state"] == "awaiting_prospect_research"

    research_response = client.post(
        f"/campaigns/{campaign_id}/prospects/{prospects[0]['prospect_id']}"
        "/research-runs",
        json={"request_id": "research-request-fixture1"},
    )
    assert research_response.status_code == 200
    researched = research_response.json()
    assert researched["campaign"]["state"] == "prospect_researched"
    run_id = researched["run"]["run_id"]
    assert (
        client.get(f"/campaigns/{campaign_id}/research-runs/{run_id}").status_code
        == 200
    )

    draft_response = client.post(f"/campaigns/{campaign_id}/draft")
    assert draft_response.status_code == 200
    completed = draft_response.json()
    assert completed["state"] == "draft_ready"
    assert completed["evaluation"]["passed"] is True
    assert completed["draft"]["prospect_id"] == prospects[0]["prospect_id"]

    trace_response = client.get(f"/campaigns/{campaign_id}/trace")
    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert len(trace) == 11
    assert [event["sequence"] for event in trace] == list(range(1, 12))
    assert all(event["occurred_at"] == "2026-08-02T10:30:00Z" for event in trace)


def test_campaign_api_maps_unknown_conflict_and_validation_errors() -> None:
    client = build_client()

    missing_response = client.get("/campaigns/campaign-9999")
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "campaign not found: campaign-9999"

    invalid_payload = valid_payload()
    invalid_payload["unexpected"] = True
    invalid_response = client.post("/campaigns", json=invalid_payload)
    assert invalid_response.status_code == 422

    created = client.post("/campaigns", json=valid_payload()).json()
    campaign_id = created["campaign_id"]
    conflict_response = client.post(f"/campaigns/{campaign_id}/draft")

    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == (
        "cannot generate a draft while campaign is awaiting_claim_approval"
    )
    unchanged = client.get(f"/campaigns/{campaign_id}").json()
    assert unchanged == created


def test_campaign_api_accepts_attested_edits_and_rejects_cross_campaign_ids() -> None:
    client = build_client()
    first = client.post("/campaigns", json=valid_payload()).json()
    second = client.post("/campaigns", json=valid_payload()).json()

    cross_campaign = client.post(
        f"/campaigns/{first['campaign_id']}/claim-decisions",
        json={
            "decisions": [
                {"claim_id": claim["claim_id"], "decision": "approved"}
                for claim in second["claims"]
            ]
        },
    )
    assert cross_campaign.status_code == 409

    decisions = [
        {
            "claim_id": first["claims"][0]["claim_id"],
            "decision": "approved",
            "edited_text": "RouteSignal highlights reviewed delivery exceptions.",
            "evidence_attested": True,
        },
        {
            "claim_id": first["claims"][1]["claim_id"],
            "decision": "rejected",
        },
    ]
    reviewed = client.post(
        f"/campaigns/{first['campaign_id']}/claim-decisions",
        json={"decisions": decisions},
    )

    assert reviewed.status_code == 200
    body = reviewed.json()
    assert body["claims"][0]["text"] == first["claims"][0]["text"]
    assert body["approvals"][0]["reviewed_text"] == decisions[0]["edited_text"]
    assert body["approvals"][0]["wording_source"] == "user_edited"
    assert (
        client.post(
            f"/campaigns/{first['campaign_id']}/claim-decisions",
            json={"decisions": decisions},
        ).json()
        == body
    )


def test_campaign_api_rejects_blank_duplicate_and_unattested_input() -> None:
    client = build_client()
    duplicate = valid_payload()
    duplicate["known_capabilities"] = ["reporting", " reporting "]
    assert client.post("/campaigns", json=duplicate).status_code == 422

    created = client.post("/campaigns", json=valid_payload()).json()
    response = client.post(
        f"/campaigns/{created['campaign_id']}/claim-decisions",
        json={
            "decisions": [
                {
                    "claim_id": claim["claim_id"],
                    "decision": "approved",
                    "edited_text": "New wording",
                }
                for claim in created["claims"]
            ]
        },
    )
    assert response.status_code == 422


def test_live_discovery_without_contact_returns_problem_details() -> None:
    client = build_client()
    created = client.post("/campaigns", json=valid_payload()).json()
    decisions = [
        {
            "claim_id": claim["claim_id"],
            "decision": "approved" if index == 0 else "rejected",
        }
        for index, claim in enumerate(created["claims"])
    ]
    client.post(
        f"/campaigns/{created['campaign_id']}/claim-decisions",
        json={"decisions": decisions},
    )

    response = client.post(
        f"/campaigns/{created['campaign_id']}/discovery-runs",
        json={"request_id": "research-request-live0001"},
    )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "research_not_configured"
