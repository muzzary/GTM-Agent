import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.evaluation.phase1 import load_manifest
from src.evaluation.phase5 import (
    benchmark_evidence_ids,
    build_baseline_report,
    evaluate_baseline_output,
)
from src.schemas.inference import (
    GenerationSettings,
    InferenceResponse,
    ModelIdentity,
    OutreachOutput,
    RuntimeMetadata,
)

MANIFEST_PATH = Path("configs/phase1/benchmark.json")


def inference_response(case_index: int, output: OutreachOutput) -> InferenceResponse:
    return InferenceResponse(
        request_id=f"req_phase5case{case_index:02d}",
        model=ModelIdentity(
            model_id="Qwen/Qwen3-4B-Instruct-2507",
            model_revision="a" * 40,
        ),
        generation=GenerationSettings(max_new_tokens=256, seed=42),
        output=output,
        runtime=RuntimeMetadata(
            python_version="3.12",
            torch_version="test",
            transformers_version="test",
            gpu_name="test-double",
            gpu_memory_mb=1,
            latency_ms=10.0 + case_index,
        ),
    )


def test_phase5_output_records_supported_claims_and_evidence() -> None:
    case = load_manifest(MANIFEST_PATH).cases[0]
    evidence_ids = benchmark_evidence_ids(case)
    output = OutreachOutput(
        subject="A question about compliance reporting",
        body="Could scheduled reporting reduce manual consolidation?",
        claims_used=[case.approved_claims[0].claim_id],
        evidence_used=[evidence_ids[0]],
        uncertainty_notes=[],
    )

    result = evaluate_baseline_output(case, output)

    assert result.passed is True
    assert result.unsupported_claims == []
    assert result.unresolved_evidence == []
    assert result.supported_claim_count == 1


def test_phase5_evaluation_rejects_unknown_claim_and_evidence_ids() -> None:
    case = load_manifest(MANIFEST_PATH).cases[0]
    output = OutreachOutput(
        subject="A question",
        body="A concise message.",
        claims_used=["claim-not-approved"],
        evidence_used=["evidence-not-present"],
        uncertainty_notes=["The prospect need is a hypothesis."],
    )

    result = evaluate_baseline_output(case, output)

    assert result.passed is False
    assert result.unsupported_claims == ["claim-not-approved"]
    assert result.unresolved_evidence == ["evidence-not-present"]


def test_phase5_evidence_ids_are_stable_and_output_contract_is_strict() -> None:
    case = load_manifest(MANIFEST_PATH).cases[0]

    assert benchmark_evidence_ids(case) == benchmark_evidence_ids(case)
    assert benchmark_evidence_ids(case) == (
        f"evidence-{case.case_id}-1",
    )

    raw = {
        "subject": "A subject",
        "body": "A body.",
        "claims_used": [],
        "evidence_used": [],
        "uncertainty_notes": [],
        "unexpected": True,
    }
    with pytest.raises(ValidationError):
        OutreachOutput.model_validate(json.loads(json.dumps(raw)))


def test_baseline_report_is_reproducible_and_summarizes_failures() -> None:
    manifest = load_manifest(MANIFEST_PATH).model_copy(
        update={"cases": load_manifest(MANIFEST_PATH).cases[:2]}
    )
    responses = [
        inference_response(
            index,
            OutreachOutput(
                subject="A subject",
                body="A body.",
                claims_used=(
                    [case.approved_claims[0].claim_id]
                    if index == 1
                    else ["claim-not-approved"]
                ),
                evidence_used=(
                    [benchmark_evidence_ids(case)[0]]
                    if index == 1
                    else ["evidence-not-present"]
                ),
                uncertainty_notes=[],
            ),
        )
        for index, case in enumerate(manifest.cases[:2], start=1)
    ]

    report = build_baseline_report(manifest, responses)

    assert report.total_cases == 2
    assert report.valid_output_count == 2
    assert report.passed_case_count == 1
    assert report.unsupported_claim_count == 1
    assert report.unresolved_evidence_count == 1
    assert report.failure_examples == ["case-reporting-operations"]
    assert report.model.model_revision == "a" * 40
    assert report.model_dump_json() == build_baseline_report(
        manifest, responses
    ).model_dump_json()
