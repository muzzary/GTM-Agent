from collections import Counter
from pathlib import Path

from src.agent.contracts import AgentFinal
from src.agent.runtime import ControlledAgentRuntime
from src.agent.tools import CrmToolRegistry
from src.crm.service import CrmService
from src.data.crm_repository import CrmRepository
from src.schemas.crm import Company, Deal, Pipeline, PipelineStage
from src.schemas.crm_benchmark import (
    CrmBenchmarkAuditReport,
    CrmBenchmarkManifest,
)


class _ExpectedCallModel:
    def __init__(self, call: dict[str, object]) -> None:
        self.call = call
        self.used = False

    def next_output(
        self, _goal: str, _observations: tuple[dict[str, object], ...]
    ) -> object:
        if not self.used:
            self.used = True
            return self.call
        return AgentFinal(kind="final", message="expected call completed")


def audit_crm_benchmark(
    benchmark: CrmBenchmarkManifest, *, strict: bool = False
) -> CrmBenchmarkAuditReport:
    errors: list[str] = []
    case_ids = [case.case_id for case in benchmark.cases]
    hashes = [case.content_sha256 or "" for case in benchmark.cases]
    duplicate_case_ids = _duplicates(case_ids)
    duplicate_content_hashes = _duplicates(hashes)
    for case in benchmark.cases:
        if case.expected_action != "tool_call":
            continue
        try:
            repository = CrmRepository(
                Path(".tmp") / f"crm-benchmark-{case.case_id}.sqlite3"
            )
            _seed(repository, case)
            registry = _registry(repository)
            if case.expected_tool_name not in case.available_tools:
                raise ValueError("expected tool is not allowlisted")
            spec = registry.get(case.expected_tool_name or "")
            arguments = spec.argument_model.model_validate(case.required_arguments)
            model = _ExpectedCallModel(
                {
                    "kind": "tool_call",
                    "call_id": case.expected_call_id,
                    "tool_name": case.expected_tool_name,
                    "arguments": arguments.model_dump(mode="json"),
                }
            )
            result = ControlledAgentRuntime(registry).run(
                tenant_id=case.tenant_id,
                goal=case.goal,
                model=model,
                approved_call_ids=case.approved_call_ids,
            )
            expected_status = (
                "approval_required"
                if case.category == "approval_required_write"
                else "completed"
            )
            if result.status != expected_status:
                raise ValueError(
                    f"expected runtime status {expected_status}, got {result.status}"
                )
            if (
                case.call_id_is_scored
                and result.trace[0].call_id != case.expected_call_id
            ):
                raise ValueError("approved write did not re-emit expected call ID")
        except Exception as error:
            errors.append(f"{case.case_id}: expected call execution failed: {error}")
    if duplicate_case_ids:
        errors.append("duplicate case IDs")
    if duplicate_content_hashes:
        errors.append("duplicate benchmark content")
    report = CrmBenchmarkAuditReport(
        benchmark_id=benchmark.benchmark_id,
        passed=not errors,
        evaluation_ready=not errors and benchmark.lifecycle_status == "frozen",
        total_cases=len(benchmark.cases),
        category_counts=dict(
            sorted(Counter(case.category for case in benchmark.cases).items())
        ),
        adversarial_case_count=sum(
            bool(case.adversarial_tags) for case in benchmark.cases
        ),
        protected_adversarial_case_count=sum(
            case.protected_adversarial for case in benchmark.cases
        ),
        duplicate_case_ids=duplicate_case_ids,
        duplicate_content_hashes=duplicate_content_hashes,
        errors=errors,
    )
    if strict and not report.passed:
        raise ValueError("CRM benchmark validation failed: " + "; ".join(report.errors))
    return report


def _seed(repository: CrmRepository, case: CrmBenchmarkManifest | object) -> None:
    for company in case.seed_companies:  # type: ignore[union-attr]
        company_data = company.model_dump()
        company_data["source_evidence_ids"] = tuple(company.source_evidence_ids)
        repository.save_company(
            Company(**company_data)
        )
    for deal in case.seed_deals:  # type: ignore[union-attr]
        saved_deal = Deal(**deal.model_dump())
        repository.save_pipeline(
            Pipeline(
                pipeline_id=saved_deal.pipeline_id,
                tenant_id=saved_deal.tenant_id,
                name="Benchmark pipeline",
                stages=(PipelineStage(
                    stage_id=saved_deal.stage_id,
                    pipeline_id=saved_deal.pipeline_id,
                    tenant_id=saved_deal.tenant_id,
                    name="Benchmark stage",
                    position=1,
                    probability=0.5,
                ),),
            )
        )
        repository.save_deal(saved_deal, idempotency_key=f"seed-{saved_deal.deal_id}")


def _registry(repository: CrmRepository) -> CrmToolRegistry:
    return CrmToolRegistry(
        CrmService(repository),
        prospect_reader=lambda _tenant, campaign: {
            "campaign_id": campaign,
            "status": "inspected",
        },
        prospect_linker=lambda _tenant, campaign, key: {
            "campaign_id": campaign,
            "idempotency_key": key,
            "status": "linked",
        },
        revenue_reporter=lambda _tenant, as_of, currency: {
            "as_of": as_of.isoformat(),
            "currency": currency,
            "total_minor": 0,
        },
    )


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)
