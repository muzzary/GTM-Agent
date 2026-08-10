import json
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from src.evaluation.phase1 import load_manifest as load_phase1_manifest
from src.evaluation.phase6_benchmark import (
    Phase6BenchmarkValidationError,
    audit_phase6_benchmark,
    load_phase6_benchmark,
)
from src.schemas.dataset import (
    ApprovedClaimRecord,
    DatasetManifest,
    EvidenceRecordV2,
    IdentityGroups,
    TrainingInputV2,
)
from src.schemas.inference import OutreachConstraints
from src.schemas.quality_benchmark import (
    Phase6BenchmarkCase,
    Phase6BenchmarkManifest,
)

BENCHMARK_PATH = Path("configs/phase6/benchmark-v2.json")
PHASE1_PATH = Path("configs/phase1/benchmark.json")
PILOT_PATH = Path("configs/phase6/pilot.json")
REVIEWED_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

PRODUCTS = [
    "reporting_automation",
    "security_asset_inventory",
    "developer_productivity",
    "support_knowledge_workflow",
    "crm_data_hygiene",
]
ICPS = [
    "regulated_mid_market",
    "distributed_operations",
    "high_growth_software",
    "professional_services",
    "enterprise_transformation",
]
ROLES = ["individual_contributor", "manager", "director", "vp", "c_level"]
EVIDENCE = ["strong", "weak", "conflicting", "stale", "absent"]


def benchmark_case(index: int, **updates: object) -> Phase6BenchmarkCase:
    product = PRODUCTS[index % len(PRODUCTS)]
    evidence_condition = EVIDENCE[index % len(EVIDENCE)]
    if index < 30:
        status = "drafted"
    elif index < 45:
        status = "needs_more_evidence"
        if evidence_condition == "strong":
            evidence_condition = "weak"
    elif index < 53:
        status = "disqualified"
    else:
        status = "opted_out"
    tags = ["unsupported_fact_combination"] if index < 15 else []
    if status == "disqualified":
        tags = ["disqualification_signal"]
    if status == "opted_out":
        tags = ["opt_out_signal"]
    claim_id = f"claim-benchmark-{index:03d}"
    evidence_id = f"evidence-benchmark-{index:03d}"
    evidence_text = f"Reviewed prospect signal {index:03d}."
    values: dict[str, object] = {
        "case_id": f"case-phase6-{index:03d}",
        "schema_version": "2.0",
        "task_type": "outreach_generation",
        "product_category": product,
        "icp_pattern": ICPS[index % len(ICPS)],
        "role_tier": ROLES[index % len(ROLES)],
        "evidence_condition": evidence_condition,
        "scenario_kind": "initial_outreach",
        "identity_groups": IdentityGroups(
            product_group=f"product-benchmark-{index:03d}",
            icp_group=f"benchmark_icp_{index:03d}",
            company_group=f"company-benchmark-{index:03d}",
            prospect_group=f"prospect-benchmark-{index:03d}",
        ),
        "product_name": f"Benchmark Product {index:03d}",
        "input": TrainingInputV2(
            target_role=f"Benchmark role {index:03d}",
            approved_claims=[
                ApprovedClaimRecord(
                    claim_id=claim_id,
                    text=f"Approved capability {index:03d}.",
                    source_kind="first_party_synthetic",
                    source_reference=f"benchmark-product-profile-{index:03d}",
                    license_kind="synthetic",
                    license_basis="Project-owned benchmark fixture",
                )
            ],
            prospect_evidence=[]
            if evidence_condition == "absent"
            else [
                EvidenceRecordV2(
                    evidence_id=evidence_id,
                    text=evidence_text,
                    source_url=f"https://example.com/benchmark/{index:03d}",
                    collected_at=REVIEWED_AT,
                    content_sha256=sha256(evidence_text.encode("utf-8")).hexdigest(),
                    source_kind="first_party_synthetic",
                    source_reference=f"benchmark-evidence-{index:03d}",
                    license_kind="synthetic",
                    license_basis="Project-owned benchmark fixture",
                )
            ],
            pain_hypotheses=["The observed workflow may create coordination work."],
            constraints=OutreachConstraints(),
        ),
        "expected_generation_status": status,
        "acceptable_claim_ids": [claim_id] if status == "drafted" else [],
        "required_evidence_ids": [evidence_id]
        if status == "drafted" and evidence_condition != "absent"
        else [],
        "adversarial_tags": tags,
        "protected_adversarial": index < 15,
        "review_status": "reviewed",
        "reviewer_reference": "reviewer-phase6-benchmark-01",
        "reviewed_at": REVIEWED_AT,
    }
    values.update(updates)
    return Phase6BenchmarkCase(**values)


def manifest(
    case_factory: Callable[[int], Phase6BenchmarkCase] = benchmark_case,
) -> Phase6BenchmarkManifest:
    return Phase6BenchmarkManifest(
        benchmark_id="benchmark-phase6-grounded-outreach",
        manifest_version="2.0",
        lifecycle_status="frozen",
        frozen_at=REVIEWED_AT,
        reviewer_reference="reviewer-phase6-benchmark-01",
        cases=[case_factory(index) for index in range(60)],
    )


def low_adversarial_case(index: int) -> Phase6BenchmarkCase:
    updates: dict[str, object] = {
        "product_category": "reporting_automation",
        "adversarial_tags": [],
        "protected_adversarial": False,
    }
    if index >= 45 and index not in {45, 53}:
        updates.update(
            expected_generation_status="needs_more_evidence",
            evidence_condition="weak",
        )
    if index == 45:
        updates["adversarial_tags"] = ["disqualification_signal"]
    if index == 53:
        updates["adversarial_tags"] = ["opt_out_signal"]
    return benchmark_case(index, **updates)


def test_versioned_60_case_benchmark_passes_strict_audit() -> None:
    benchmark = load_phase6_benchmark(BENCHMARK_PATH)
    pilot = DatasetManifest.model_validate_json(PILOT_PATH.read_text(encoding="utf-8"))
    phase1 = load_phase1_manifest(PHASE1_PATH)

    report = audit_phase6_benchmark(
        benchmark,
        blocked_identity_groups={
            *(f"product:{item.product_group}" for item in pilot.examples),
            *(f"icp:{item.icp_group}" for item in pilot.examples),
            *(f"company:{item.company_group}" for item in pilot.examples),
            *(f"prospect:{item.prospect_group}" for item in pilot.examples),
        },
        blocked_case_ids={case.case_id for case in phase1.cases},
    )

    assert report.passed is True
    assert report.evaluation_ready is True
    assert report.total_cases == 60
    assert report.adversarial_case_count == 15
    assert report.status_counts == {
        "disqualified": 8,
        "drafted": 30,
        "needs_more_evidence": 15,
        "opted_out": 7,
    }
    assert set(report.status_counts) == {
        "drafted",
        "needs_more_evidence",
        "disqualified",
        "opted_out",
    }
    assert all(count > 0 for count in report.coverage_counts.values())
    assert report.errors == []


def test_manifest_hash_detects_tampering() -> None:
    benchmark = manifest()
    payload = json.loads(benchmark.model_dump_json())
    payload["cases"][0]["product_name"] = "Tampered Product"

    with pytest.raises(ValueError, match="content_sha256"):
        Phase6BenchmarkManifest.model_validate(payload)


@pytest.mark.parametrize("missing_hash", ["manifest", "case"])
def test_loader_rejects_missing_persisted_hashes(
    tmp_path: Path,
    missing_hash: str,
) -> None:
    payload = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    if missing_hash == "manifest":
        payload.pop("content_sha256")
    else:
        payload["cases"][0].pop("content_sha256")
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="content_sha256"):
        load_phase6_benchmark(path)


def test_audit_rejects_missing_coverage_and_too_few_adversarial_cases() -> None:
    benchmark = manifest(low_adversarial_case)

    report = audit_phase6_benchmark(benchmark, strict=False)

    assert report.passed is False
    assert "missing required coverage" in report.errors
    assert "protected adversarial set must contain exactly 15 cases" in report.errors


def test_audit_rejects_identity_and_phase1_case_leakage() -> None:
    benchmark = manifest()
    first = benchmark.cases[0]

    with pytest.raises(Phase6BenchmarkValidationError, match="overlap"):
        audit_phase6_benchmark(
            benchmark,
            blocked_identity_groups={
                f"product:{first.identity_groups.product_group}",
                f"icp:{first.identity_groups.icp_group}",
            },
            blocked_case_ids={first.case_id},
        )


def test_audit_enforces_exact_status_and_protected_distributions() -> None:
    benchmark = manifest()
    shifted_case = benchmark_case(
        0,
        evidence_condition="weak",
        expected_generation_status="needs_more_evidence",
        acceptable_claim_ids=[],
        required_evidence_ids=[],
    )
    shifted = benchmark.model_copy(
        update={"cases": [shifted_case, *benchmark.cases[1:]]}
    )
    extra_protected = benchmark_case(
        15,
        adversarial_tags=["invented_pain"],
        protected_adversarial=True,
    )
    expanded = benchmark.model_copy(
        update={
            "cases": [*benchmark.cases[:15], extra_protected, *benchmark.cases[16:]]
        }
    )

    shifted_report = audit_phase6_benchmark(shifted, strict=False)
    expanded_report = audit_phase6_benchmark(expanded, strict=False)

    assert "expected status distribution" in " ".join(shifted_report.errors)
    assert "exactly 15" in " ".join(expanded_report.errors)


def test_audit_checks_blocked_icp_identity() -> None:
    benchmark = manifest()
    first = benchmark.cases[0]

    report = audit_phase6_benchmark(
        benchmark,
        blocked_identity_groups={f"icp:{first.identity_groups.icp_group}"},
        strict=False,
    )

    assert f"icp:{first.identity_groups.icp_group}" in report.blocked_identity_overlap


def test_case_rejects_non_controlled_provenance() -> None:
    base = benchmark_case(1)
    external_claim = base.input.approved_claims[0].model_copy(
        update={"source_kind": "public_company_page"}
    )

    with pytest.raises(ValueError, match="controlled synthetic provenance"):
        benchmark_case(
            1,
            input=base.input.model_copy(
                update={
                    "approved_claims": [
                        external_claim,
                        *base.input.approved_claims[1:],
                    ]
                }
            ),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("acceptable_claim_ids", ["claim-unknown"], "claim"),
        ("required_evidence_ids", ["evidence-unknown"], "evidence"),
        ("adversarial_tags", ["opt_out_signal"], "opted_out"),
    ],
)
def test_case_contract_rejects_inconsistent_expected_behavior(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        benchmark_case(0, **{field: value})


def test_abstention_cases_require_the_corresponding_signal() -> None:
    opted_out = benchmark_case(
        40,
        evidence_condition="strong",
        expected_generation_status="opted_out",
        acceptable_claim_ids=[],
        required_evidence_ids=[],
        adversarial_tags=["opt_out_signal"],
    )
    disqualified = benchmark_case(
        41,
        evidence_condition="strong",
        expected_generation_status="disqualified",
        acceptable_claim_ids=[],
        required_evidence_ids=[],
        adversarial_tags=["disqualification_signal"],
    )

    assert opted_out.expected_generation_status == "opted_out"
    assert disqualified.expected_generation_status == "disqualified"


def test_case_content_hash_ignores_case_identifier_but_not_input() -> None:
    first = benchmark_case(1)
    renamed = benchmark_case(1, case_id="case-phase6-renamed")
    changed = benchmark_case(1, product_name="Different Product")

    assert first.content_sha256 == renamed.content_sha256
    assert first.content_sha256 != changed.content_sha256


def test_prompt_projection_excludes_evaluation_labels_and_metadata() -> None:
    payload = benchmark_case(1).prompt_input().model_dump(mode="json")
    serialized = json.dumps(payload)

    for forbidden_key in (
        "expected_generation_status",
        "adversarial_tags",
        "protected_adversarial",
        "content_sha256",
        "identity_groups",
        "reviewer_reference",
        "source_reference",
        "license_kind",
        "license_basis",
    ):
        assert forbidden_key not in serialized


def test_weak_evidence_is_domain_relevant_without_false_presupposition() -> None:
    benchmark = load_phase6_benchmark(BENCHMARK_PATH)
    domain_markers = {
        "reporting_automation": {"report", "scorecard"},
        "security_asset_inventory": {"asset", "cloud"},
        "developer_productivity": {"ci", "build"},
        "support_knowledge_workflow": {"support", "knowledge"},
        "crm_data_hygiene": {"crm", "record"},
    }
    weak_cases = [
        case for case in benchmark.cases if case.evidence_condition == "weak"
    ]

    assert len(weak_cases) == 5
    for case in weak_cases:
        evidence_text = " ".join(
            item.text.casefold() for item in case.input.prospect_evidence
        )
        assert any(
            marker in evidence_text for marker in domain_markers[case.product_category]
        )
        assert "several locations" not in evidence_text
        assert all(
            not hypothesis.casefold().startswith("the observed")
            for hypothesis in case.input.pain_hypotheses
        )


def test_drafts_accept_any_approved_claim_instead_of_one_arbitrary_claim() -> None:
    benchmark = load_phase6_benchmark(BENCHMARK_PATH)

    for case in benchmark.cases:
        approved_ids = sorted(claim.claim_id for claim in case.input.approved_claims)
        if case.expected_generation_status == "drafted":
            assert case.acceptable_claim_ids == approved_ids
        else:
            assert case.acceptable_claim_ids == []


def test_products_use_distinct_domain_role_ladders() -> None:
    benchmark = load_phase6_benchmark(BENCHMARK_PATH)
    roles_by_product = {
        category: {
            case.input.target_role
            for case in benchmark.cases
            if case.product_category == category
        }
        for category in PRODUCTS
    }

    assert all(len(roles) == 5 for roles in roles_by_product.values())
    assert len(set().union(*roles_by_product.values())) == 25


def test_protected_set_includes_abstention_and_invasive_input_traps() -> None:
    benchmark = load_phase6_benchmark(BENCHMARK_PATH)
    protected = [case for case in benchmark.cases if case.protected_adversarial]

    assert len(protected) == 15
    assert {case.expected_generation_status for case in protected} >= {
        "drafted",
        "needs_more_evidence",
    }
    assert any(
        "invasive_personalization" in case.adversarial_tags for case in protected
    )
    invasive_evidence = [
        item.text
        for case in protected
        if "invasive_personalization" in case.adversarial_tags
        for item in case.input.prospect_evidence
    ]
    assert any("personal detail" in text.casefold() for text in invasive_evidence)


def test_case_language_avoids_the_reviewed_shortcut_templates() -> None:
    benchmark = load_phase6_benchmark(BENCHMARK_PATH)
    evidence_text = " ".join(
        evidence.text.casefold()
        for case in benchmark.cases
        for evidence in case.input.prospect_evidence
    )
    hypotheses = [
        hypothesis
        for case in benchmark.cases
        for hypothesis in case.input.pain_hypotheses
    ]

    assert "does not operate the relevant" not in evidence_text
    assert "requests no further sales outreach" not in evidence_text
    assert "2023 archive" not in evidence_text
    assert not any("may create coordination work" in item for item in hypotheses)
