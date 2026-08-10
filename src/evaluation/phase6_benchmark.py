import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from src.schemas.quality_benchmark import (
    Phase6BenchmarkAuditReport,
    Phase6BenchmarkManifest,
)

REQUIRED_COVERAGE = {
    "product_category": {
        "reporting_automation",
        "security_asset_inventory",
        "developer_productivity",
        "support_knowledge_workflow",
        "crm_data_hygiene",
    },
    "icp_pattern": {
        "regulated_mid_market",
        "distributed_operations",
        "high_growth_software",
        "professional_services",
        "enterprise_transformation",
    },
    "role_tier": {"individual_contributor", "manager", "director", "vp", "c_level"},
    "evidence_condition": {"strong", "weak", "conflicting", "stale", "absent"},
    "scenario_kind": {"initial_outreach", "follow_up"},
    "expected_generation_status": {
        "drafted",
        "needs_more_evidence",
        "disqualified",
        "opted_out",
    },
}
EXPECTED_STATUS_COUNTS = {
    "drafted": 30,
    "needs_more_evidence": 15,
    "disqualified": 8,
    "opted_out": 7,
}
EXPECTED_PROTECTED_ADVERSARIAL_CASES = 15


class Phase6BenchmarkValidationError(ValueError):
    def __init__(self, report: Phase6BenchmarkAuditReport) -> None:
        self.report = report
        super().__init__(
            "Phase 6 benchmark validation failed: " + "; ".join(report.errors)
        )


def load_phase6_benchmark(path: Path) -> Phase6BenchmarkManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        _require_persisted_hashes(payload)
        return Phase6BenchmarkManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Unable to load Phase 6 benchmark: {exc}") from exc


def audit_phase6_benchmark(
    benchmark: Phase6BenchmarkManifest,
    *,
    blocked_identity_groups: set[str] | None = None,
    blocked_case_ids: set[str] | None = None,
    strict: bool = True,
) -> Phase6BenchmarkAuditReport:
    blocked_identity_groups = blocked_identity_groups or set()
    blocked_case_ids = blocked_case_ids or set()
    errors: list[str] = []

    case_ids = [case.case_id for case in benchmark.cases]
    duplicate_case_ids = _duplicates(case_ids)
    content_hashes = [case.content_sha256 or "" for case in benchmark.cases]
    duplicate_content_hashes = _duplicates(content_hashes)

    identities: list[str] = []
    unique_case_identities: list[str] = []
    for case in benchmark.cases:
        identities.extend(
            (
                f"product:{case.identity_groups.product_group}",
                f"icp:{case.identity_groups.icp_group}",
                f"company:{case.identity_groups.company_group}",
                f"prospect:{case.identity_groups.prospect_group}",
            )
        )
        unique_case_identities.extend(
            (
                f"company:{case.identity_groups.company_group}",
                f"prospect:{case.identity_groups.prospect_group}",
            )
        )
    duplicate_identity_groups = _duplicates(unique_case_identities)
    blocked_identity_overlap = sorted(set(identities) & blocked_identity_groups)
    blocked_case_overlap = sorted(set(case_ids) & blocked_case_ids)

    coverage_counts = {
        f"{field}:{value}": sum(
            getattr(case, field) == value for case in benchmark.cases
        )
        for field, values in REQUIRED_COVERAGE.items()
        for value in sorted(values)
    }
    status_counts = dict(
        sorted(
            Counter(case.expected_generation_status for case in benchmark.cases).items()
        )
    )
    adversarial_case_count = sum(case.protected_adversarial for case in benchmark.cases)

    if len(benchmark.cases) != 60:
        errors.append("first frozen release must contain exactly 60 cases")
    if duplicate_case_ids:
        errors.append("duplicate case IDs")
    if duplicate_content_hashes:
        errors.append("duplicate benchmark content")
    if duplicate_identity_groups:
        errors.append("benchmark company and prospect groups must be case-disjoint")
    if blocked_identity_overlap:
        errors.append("benchmark identity overlap with training or pilot data")
    if blocked_case_overlap:
        errors.append("benchmark case overlap with an existing held-out benchmark")
    if any(count == 0 for count in coverage_counts.values()):
        errors.append("missing required coverage")
    if status_counts != EXPECTED_STATUS_COUNTS:
        errors.append("expected status distribution must be exactly 30/15/8/7")
    if adversarial_case_count != EXPECTED_PROTECTED_ADVERSARIAL_CASES:
        errors.append("protected adversarial set must contain exactly 15 cases")

    report = Phase6BenchmarkAuditReport(
        benchmark_id=benchmark.benchmark_id,
        passed=not errors,
        evaluation_ready=not errors and benchmark.lifecycle_status == "frozen",
        total_cases=len(benchmark.cases),
        adversarial_case_count=adversarial_case_count,
        status_counts=status_counts,
        coverage_counts=coverage_counts,
        duplicate_case_ids=duplicate_case_ids,
        duplicate_content_hashes=duplicate_content_hashes,
        duplicate_identity_groups=duplicate_identity_groups,
        blocked_identity_overlap=blocked_identity_overlap,
        blocked_case_overlap=blocked_case_overlap,
        errors=errors,
    )
    if strict and not report.passed:
        raise Phase6BenchmarkValidationError(report)
    return report


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _require_persisted_hashes(payload: object) -> None:
    if not isinstance(payload, dict) or not payload.get("content_sha256"):
        raise ValueError("persisted benchmark manifest requires content_sha256")
    cases = payload.get("cases")
    if not isinstance(cases, list) or any(
        not isinstance(case, dict) or not case.get("content_sha256") for case in cases
    ):
        raise ValueError("every persisted benchmark case requires content_sha256")
