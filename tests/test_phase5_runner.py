from pathlib import Path

from src.evaluation.phase1 import load_manifest
from src.evaluation.phase5 import benchmark_evidence_ids, run_baseline
from src.schemas.inference import (
    GenerationSettings,
    InferenceResponse,
    ModelIdentity,
    OutreachOutput,
    RuntimeMetadata,
)

MANIFEST_PATH = Path("configs/phase1/benchmark.json")
MODEL = ModelIdentity(
    model_id="Qwen/Qwen3-4B-Instruct-2507",
    model_revision="a" * 40,
)


def response_for(request_id: str, output: OutreachOutput) -> InferenceResponse:
    return InferenceResponse(
        request_id=request_id,
        model=MODEL,
        generation=GenerationSettings(max_new_tokens=256, seed=42),
        output=output,
        runtime=RuntimeMetadata(
            python_version="3.12",
            torch_version="test",
            transformers_version="test",
            gpu_name="test-double",
            gpu_memory_mb=1,
            latency_ms=12.5,
        ),
    )


def test_runner_records_retry_and_complete_trace() -> None:
    case = load_manifest(MANIFEST_PATH).cases[0]
    calls = 0

    def generate(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary model timeout")
        return response_for(
            request.request_id,
            OutreachOutput(
                subject="A question",
                body="Could scheduled reporting reduce manual work?",
                claims_used=[case.approved_claims[0].claim_id],
                evidence_used=[benchmark_evidence_ids(case)[0]],
                uncertainty_notes=[],
            ),
        )

    report = run_baseline(
        load_manifest(MANIFEST_PATH).model_copy(update={"cases": [case]}),
        MODEL,
        generate,
    )

    assert calls == 2
    assert report.valid_output_count == 1
    assert report.passed_case_count == 1
    assert report.cases[0].retry_count == 1
    assert [entry.status for entry in report.trace] == ["failed", "succeeded"]
    assert report.trace[0].error == "temporary model timeout"
    assert report.trace[1].latency_ms == 12.5


def test_runner_stops_after_one_retry_and_reports_failure() -> None:
    manifest = load_manifest(MANIFEST_PATH).model_copy(
        update={"cases": load_manifest(MANIFEST_PATH).cases[:2]}
    )
    calls = 0

    def generate(_request):
        nonlocal calls
        calls += 1
        raise ConnectionError("colab endpoint unavailable")

    report = run_baseline(manifest, MODEL, generate)

    assert calls == 4
    assert report.valid_output_count == 0
    assert report.passed_case_count == 0
    assert report.failure_examples == [
        "case-reporting-regulated",
        "case-reporting-operations",
    ]
    assert all(case.failure == "colab endpoint unavailable" for case in report.cases)
    assert len(report.trace) == 4
