from pathlib import Path

import pytest

from src.evaluation.phase6_benchmark import load_phase6_benchmark
from src.evaluation.phase6_v2 import (
    Phase6V2EvaluationReport,
    build_phase6_v2_prompt,
    compare_phase6_v2_reports,
    evaluate_phase6_v2_case,
    run_phase6_v2_evaluation,
)
from src.schemas.inference import (
    GroundedOutreachOutput,
    ModelIdentity,
    SupportMapEntry,
)

BENCHMARK_PATH = Path("configs/phase6/benchmark-v2.json")
BASE_MODEL = ModelIdentity(model_id="model/example", model_revision="a" * 40)
ADAPTER_MODEL = ModelIdentity(
    model_id="model/example",
    model_revision="a" * 40,
    adapter_id="adapter-example",
    adapter_revision="b" * 64,
)


def benchmark():
    return load_phase6_benchmark(BENCHMARK_PATH)


def valid_output(case) -> GroundedOutreachOutput:
    if case.expected_generation_status != "drafted":
        return GroundedOutreachOutput(
            generation_status=case.expected_generation_status,
            subject="",
            body="",
            support_map=[],
            uncertainty_notes=["The supplied evidence requires abstention."],
        )

    evidence = next(
        item
        for item in case.input.prospect_evidence
        if item.evidence_id in case.required_evidence_ids
    )
    claim = case.input.approved_claims[0]
    entries = [
        SupportMapEntry(
            sentence=f"The supplied source states: {evidence.text}",
            role="prospect_fact",
            evidence_ids=[evidence.evidence_id],
        ),
        SupportMapEntry(
            sentence=f"{case.product_name} {claim.text}.",
            role="product_claim",
            claim_ids=[claim.claim_id],
        ),
        SupportMapEntry(
            sentence="Would exploring that approved capability be useful to your team?",
            role="cta",
            claim_ids=[claim.claim_id],
            cta_kind="interest_question",
        ),
    ]
    return GroundedOutreachOutput(
        generation_status="drafted",
        subject="A relevant workflow question",
        body=" ".join(entry.sentence for entry in entries),
        support_map=entries,
        uncertainty_notes=[],
    )


def test_v2_prompt_uses_only_the_typed_prompt_projection() -> None:
    case = benchmark().cases[0]

    prompt = build_phase6_v2_prompt(case)

    assert case.product_name in prompt
    assert case.input.target_role in prompt
    assert "expected_generation_status" not in prompt
    assert "adversarial_tags" not in prompt
    assert "protected_adversarial" not in prompt
    assert "reviewer_reference" not in prompt
    assert case.case_id not in prompt
    assert "Draft JSON shape example" in prompt
    assert "Non-draft JSON shape example" in prompt


def test_case_evaluation_checks_status_citations_and_structure() -> None:
    case = benchmark().cases[0]

    evaluation = evaluate_phase6_v2_case(case, valid_output(case))

    assert evaluation.deterministic_passed is True
    assert evaluation.status_matches is True
    assert evaluation.acceptable_claim_used is True
    assert evaluation.missing_required_evidence_ids == []
    assert evaluation.unknown_claim_ids == []
    assert evaluation.unknown_evidence_ids == []
    assert evaluation.structural_violations == []
    assert evaluation.semantic_review_status == "pending"


def test_case_evaluation_fails_wrong_status_and_missing_citations() -> None:
    case = benchmark().cases[0]
    output = GroundedOutreachOutput(
        generation_status="needs_more_evidence",
        subject="",
        body="",
        support_map=[],
        uncertainty_notes=["More evidence is needed."],
    )

    evaluation = evaluate_phase6_v2_case(case, output)

    assert evaluation.deterministic_passed is False
    assert evaluation.status_matches is False
    assert evaluation.acceptable_claim_used is False
    assert evaluation.missing_required_evidence_ids == case.required_evidence_ids


def test_runner_records_failures_without_retrying_or_aborting() -> None:
    manifest = benchmark().model_copy(update={"cases": benchmark().cases[:2]})
    calls = []

    def generate(request):
        calls.append(request.request_id)
        if len(calls) == 1:
            raise ValueError("invalid model output")
        return valid_output(manifest.cases[1])

    report = run_phase6_v2_evaluation(manifest, BASE_MODEL, generate)

    assert len(calls) == 2
    assert report.total_cases == 2
    assert report.valid_output_count == 1
    assert report.cases[0].failure == "invalid model output"
    assert report.cases[0].raw_output_excerpt is None
    assert report.cases[1].output is not None


def test_runner_bounds_raw_failure_diagnostics() -> None:
    manifest = benchmark().model_copy(update={"cases": benchmark().cases[:1]})

    class InvalidOutputError(ValueError):
        raw_output_excerpt = "x" * 3_000

    def generate(request):
        raise InvalidOutputError("invalid model output")

    report = run_phase6_v2_evaluation(manifest, BASE_MODEL, generate)

    assert len(report.cases[0].raw_output_excerpt) == 2_000


def test_runner_covers_the_complete_frozen_benchmark() -> None:
    manifest = benchmark()
    cases_by_request = {
        f"req_phase6v2case{index:04d}": case
        for index, case in enumerate(manifest.cases, start=1)
    }

    report = run_phase6_v2_evaluation(
        manifest,
        BASE_MODEL,
        lambda request: valid_output(cases_by_request[request.request_id]),
    )

    assert report.total_cases == 60
    assert report.valid_output_count == 60
    assert report.deterministic_passed_case_count == 60


def test_comparison_never_auto_accepts_before_semantic_review() -> None:
    manifest = benchmark().model_copy(update={"cases": benchmark().cases[:2]})
    base = run_phase6_v2_evaluation(
        manifest,
        BASE_MODEL,
        lambda request: valid_output(
            manifest.cases[int(request.request_id[-4:]) - 1]
        ),
    )
    adapter = run_phase6_v2_evaluation(
        manifest,
        ADAPTER_MODEL,
        lambda request: valid_output(
            manifest.cases[int(request.request_id[-4:]) - 1]
        ),
    )

    comparison = compare_phase6_v2_reports(base, adapter)

    assert comparison.adapter_valid_output_rate == 1.0
    assert comparison.adapter_deterministic_pass_rate == 1.0
    assert comparison.quality_gate_status == "pending_semantic_review"
    assert comparison.accepted is False


def test_comparison_rejects_mismatched_case_order() -> None:
    manifest = benchmark().model_copy(update={"cases": benchmark().cases[:2]})
    base = run_phase6_v2_evaluation(
        manifest,
        BASE_MODEL,
        lambda request: valid_output(manifest.cases[0]),
    )
    adapter = run_phase6_v2_evaluation(
        manifest,
        ADAPTER_MODEL,
        lambda request: valid_output(manifest.cases[0]),
    )
    adapter = adapter.model_copy(update={"cases": list(reversed(adapter.cases))})

    with pytest.raises(ValueError, match="cases do not match"):
        compare_phase6_v2_reports(base, adapter)


def test_comparison_rejects_invalid_threshold_and_adapter_labeled_base() -> None:
    manifest = benchmark().model_copy(update={"cases": benchmark().cases[:1]})
    base = run_phase6_v2_evaluation(
        manifest,
        BASE_MODEL,
        lambda request: valid_output(manifest.cases[0]),
    )
    adapter = run_phase6_v2_evaluation(
        manifest,
        ADAPTER_MODEL,
        lambda request: valid_output(manifest.cases[0]),
    )

    with pytest.raises(ValueError, match="between zero and one"):
        compare_phase6_v2_reports(base, adapter, minimum_valid_output_rate=1.1)

    mislabeled_base = base.model_copy(update={"model": ADAPTER_MODEL})
    with pytest.raises(ValueError, match="base report cannot include an adapter"):
        compare_phase6_v2_reports(mislabeled_base, adapter)


def test_report_rejects_duplicate_case_ids() -> None:
    manifest = benchmark().model_copy(update={"cases": benchmark().cases[:1]})
    report = run_phase6_v2_evaluation(
        manifest,
        BASE_MODEL,
        lambda request: valid_output(manifest.cases[0]),
    )

    with pytest.raises(ValueError, match="case IDs must be unique"):
        Phase6V2EvaluationReport(
            benchmark_id=report.benchmark_id,
            benchmark_manifest_sha256=report.benchmark_manifest_sha256,
            model=report.model,
            generation=report.generation,
            cases=[report.cases[0], report.cases[0]],
        )
