from pathlib import Path

import pytest

from src.evaluation.phase5 import benchmark_evidence_ids, build_baseline_report
from src.evaluation.phase6 import compare_baseline_reports
from src.schemas.benchmark import BaselineCaseResult
from src.schemas.inference import (
    GenerationSettings,
    InferenceResponse,
    ModelIdentity,
    OutreachOutput,
    RuntimeMetadata,
)


def response(
    case_index: int,
    output: OutreachOutput,
    *,
    adapter: bool = False,
) -> InferenceResponse:
    return InferenceResponse(
        request_id=f"req_phase6case{case_index:04d}",
        model=ModelIdentity(
            model_id="Qwen/Qwen3-4B-Instruct-2507",
            model_revision="a" * 40,
            adapter_id="gtm-agent-outreach-pilot" if adapter else None,
            adapter_revision="b" * 64 if adapter else None,
        ),
        generation=GenerationSettings(max_new_tokens=256, seed=42),
        output=output,
        runtime=RuntimeMetadata(
            python_version="3.12",
            torch_version="test",
            transformers_version="test",
            gpu_name="test-double",
            gpu_memory_mb=1,
            latency_ms=10.0,
        ),
    )


def reports(*, adapter_output: OutreachOutput | None = None):
    from src.evaluation.phase1 import load_manifest

    manifest = load_manifest(Path("configs/phase1/benchmark.json")).model_copy(
        update={"cases": load_manifest(Path("configs/phase1/benchmark.json")).cases[:2]}
    )
    base_responses = []
    adapter_responses = []
    for index, case in enumerate(manifest.cases, start=1):
        output = OutreachOutput(
            subject="A subject",
            body="A body.",
            claims_used=[case.approved_claims[0].claim_id],
            evidence_used=[benchmark_evidence_ids(case)[0]],
        )
        base_responses.append(response(index, output))
        adapter_responses.append(
            response(index, adapter_output or output, adapter=True)
        )
    return (
        build_baseline_report(manifest, base_responses),
        build_baseline_report(manifest, adapter_responses),
    )


def test_comparison_marks_identical_quality_unchanged_and_passes_gates() -> None:
    base, adapter = reports()

    comparison = compare_baseline_reports(base, adapter, "c" * 64)

    assert comparison.quality_change == "unchanged"
    assert comparison.factuality_gates_passed is True
    assert comparison.no_case_regressions is True
    assert comparison.accepted is True
    assert comparison.passed_case_count_delta == 0


def test_comparison_rejects_adapter_claim_or_evidence_regressions() -> None:
    base, _ = reports()
    adapter = reports(
        adapter_output=OutreachOutput(
            subject="A subject",
            body="A body.",
            claims_used=["claim-not-approved"],
            evidence_used=["evidence-not-present"],
        )
    )[1]

    comparison = compare_baseline_reports(base, adapter, "c" * 64)

    assert comparison.factuality_gates_passed is False
    assert comparison.accepted is False
    assert comparison.adapter_unsupported_claim_count == 2
    assert comparison.adapter_unresolved_evidence_count == 2


def test_comparison_rejects_base_identity_or_case_mismatch() -> None:
    base, adapter = reports()
    mismatched = adapter.model_copy(
        update={"model": adapter.model.model_copy(update={"model_revision": "d" * 40})}
    )

    with pytest.raises(ValueError, match="base model revision"):
        compare_baseline_reports(base, mismatched, "c" * 64)


def test_comparison_rejects_zero_valid_outputs_as_inconclusive() -> None:
    base, adapter = reports()

    def failed(report):
        return report.model_copy(
            update={
                "cases": [
                    BaselineCaseResult(
                        case_id=case.case_id,
                        request_id=case.request_id,
                        prompt_sha256=case.prompt_sha256,
                        retry_count=0,
                        failure="model output is invalid",
                        raw_output_excerpt="<think>not JSON</think>",
                    )
                    for case in report.cases
                ]
            }
        )

    comparison = compare_baseline_reports(failed(base), failed(adapter), "c" * 64)

    assert comparison.quality_change == "inconclusive"
    assert comparison.report_version == "1.1"
    assert comparison.valid_output_gate_passed is False
    assert comparison.accepted is False
