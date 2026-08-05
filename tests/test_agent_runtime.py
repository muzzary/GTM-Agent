from datetime import UTC, datetime
from pathlib import Path

from src.agent.contracts import AgentFinal
from src.agent.runtime import ControlledAgentRuntime
from src.agent.tools import CrmToolRegistry
from src.crm.service import CrmService
from src.data.crm_repository import CrmRepository
from src.schemas.crm import Company, Pipeline, PipelineStage

TENANT = "tenant-0001"
NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


class ScriptedModel:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = iter(outputs)

    def next_output(
        self, _goal: str, _observations: tuple[dict[str, object], ...]
    ) -> object:
        return next(self.outputs)


def seeded_repository(tmp_path: Path) -> CrmRepository:
    repository = CrmRepository(tmp_path / "crm.sqlite3")
    repository.save_company(
        Company(
            company_id="company-0001",
            tenant_id=TENANT,
            name="Acme Logistics",
            industry="logistics",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repository.save_pipeline(
        Pipeline(
            pipeline_id="pipeline-0001",
            tenant_id=TENANT,
            name="New business",
            stages=(
                PipelineStage(
                    stage_id="stage-0001",
                    pipeline_id="pipeline-0001",
                    tenant_id=TENANT,
                    name="Qualified",
                    position=1,
                    probability=0.4,
                ),
            ),
        )
    )
    return repository


def test_read_tool_can_observe_state_and_finish(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path)
    model = ScriptedModel(
        [
            {
                "kind": "tool_call",
                "call_id": "tool-call-search-0001",
                "tool_name": "crm.search_companies",
                "arguments": {"query": "logistics"},
            },
            {"kind": "final", "message": "Found the logistics company."},
        ]
    )

    result = ControlledAgentRuntime(CrmToolRegistry(CrmService(repository))).run(
        tenant_id=TENANT, goal="Find logistics companies", model=model
    )

    assert result.status == "completed"
    assert result.outputs[0]["result"]["count"] == 1
    assert [entry.status for entry in result.trace] == [
        "tool_called",
        "succeeded",
        "final",
    ]


def test_sensitive_tool_pauses_before_mutation(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path)
    model = ScriptedModel(
        [
            {
                "kind": "tool_call",
                "call_id": "tool-call-company-0001",
                "tool_name": "crm.create_company",
                "arguments": {
                    "idempotency_key": "company-new-prospect-0001",
                    "name": "New Prospect",
                },
            }
        ]
    )

    result = ControlledAgentRuntime(CrmToolRegistry(CrmService(repository))).run(
        tenant_id=TENANT, goal="Create the company", model=model
    )

    assert result.status == "approval_required"
    assert [entry.status for entry in result.trace] == [
        "tool_called",
        "approval_required",
    ]
    assert [company.name for company in repository.list_companies(TENANT)] == [
        "Acme Logistics"
    ]


def test_approved_deal_call_is_idempotent_on_replay(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path)
    call = {
        "kind": "tool_call",
        "call_id": "tool-call-deal-0001",
        "tool_name": "crm.create_deal",
        "arguments": {
            "company_id": "company-0001",
            "pipeline_id": "pipeline-0001",
            "stage_id": "stage-0001",
            "name": "Acme expansion",
            "amount_minor": 100000,
            "currency": "USD",
            "idempotency_key": "deal-acme-0001",
        },
    }
    runtime = ControlledAgentRuntime(CrmToolRegistry(CrmService(repository)))

    result = runtime.run(
        tenant_id=TENANT,
        goal="Create a deal",
        model=ScriptedModel([call, AgentFinal(kind="final", message="done")]),
        approved_call_ids={"tool-call-deal-0001"},
    )
    replay = runtime.run(
        tenant_id=TENANT,
        goal="Create a deal again",
        model=ScriptedModel([call, AgentFinal(kind="final", message="done")]),
        approved_call_ids={"tool-call-deal-0001"},
    )

    assert result.status == replay.status == "completed"
    assert len(repository.list_companies(TENANT)) == 1
    assert repository.get_deal(
        TENANT, result.outputs[0]["result"]["deal"]["deal_id"]
    ) == repository.get_deal(TENANT, replay.outputs[0]["result"]["deal"]["deal_id"])


def test_adversarial_output_cannot_select_unknown_or_invalid_tool(
    tmp_path: Path,
) -> None:
    repository = seeded_repository(tmp_path)
    model = ScriptedModel(
        [
            {
                "kind": "tool_call",
                "call_id": "tool-call-bad-0001",
                "tool_name": "crm.raw_sql",
                "arguments": {"statement": "DELETE FROM crm_companies"},
            }
        ]
    )

    result = ControlledAgentRuntime(CrmToolRegistry(CrmService(repository))).run(
        tenant_id=TENANT, goal="Do something", model=model
    )

    assert result.status == "failed"
    assert "validation" in result.message
    assert [company.name for company in repository.list_companies(TENANT)] == [
        "Acme Logistics"
    ]


def test_link_selected_prospect_tool_is_approval_gated(tmp_path: Path) -> None:
    repository = seeded_repository(tmp_path)
    calls: list[tuple[str, str, str]] = []

    def linker(
        tenant_id: str, campaign_id: str, idempotency_key: str
    ) -> dict[str, object]:
        calls.append((tenant_id, campaign_id, idempotency_key))
        return {"status": "linked"}

    registry = CrmToolRegistry(CrmService(repository), prospect_linker=linker)
    call = {
        "kind": "tool_call",
        "call_id": "tool-call-link-0001",
        "tool_name": "crm.link_selected_prospect",
        "arguments": {
            "campaign_id": "campaign-0001",
            "idempotency_key": "link-0001",
        },
    }

    paused = ControlledAgentRuntime(registry).run(
        tenant_id=TENANT,
        goal="Link the researched prospect",
        model=ScriptedModel([call]),
    )
    assert paused.status == "approval_required"
    assert calls == []

    approved = ControlledAgentRuntime(registry).run(
        tenant_id=TENANT,
        goal="Link the researched prospect",
        model=ScriptedModel([call, AgentFinal(kind="final", message="linked")]),
        approved_call_ids={"tool-call-link-0001"},
    )

    assert approved.status == "completed"
    assert calls == [(TENANT, "campaign-0001", "link-0001")]
