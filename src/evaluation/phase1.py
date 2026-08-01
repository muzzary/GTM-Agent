import json
from pathlib import Path

from pydantic import ValidationError

from src.schemas.benchmark import (
    BenchmarkCase,
    BenchmarkManifest,
    CandidateResult,
    CaseEvaluation,
    HardGates,
)
from src.schemas.inference import OutreachOutput


def load_manifest(path: Path) -> BenchmarkManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load benchmark manifest: {exc}") from exc
    return BenchmarkManifest.model_validate(raw)


def parse_model_output(raw_text: str) -> OutreachOutput:
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("model output is not valid JSON") from exc
    try:
        return OutreachOutput.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(
            "model output does not match the valid output contract"
        ) from exc


def evaluate_output(case: BenchmarkCase, output: OutreachOutput) -> CaseEvaluation:
    unsupported = sorted(set(output.claims_used) - case.approved_claim_ids)
    return CaseEvaluation(
        unsupported_claims=unsupported,
        passes_claim_gate=not unsupported,
    )


def passes_hard_gates(result: CandidateResult, gates: HardGates) -> bool:
    return (
        result.valid_output_rate >= gates.minimum_valid_output_rate
        and result.unsupported_claim_count <= gates.maximum_unsupported_claim_count
        and (result.qlora_smoke_passed or not gates.require_qlora_smoke)
    )


def choose_winner(
    results: list[CandidateResult],
    gates: HardGates | None = None,
) -> CandidateResult:
    active_gates = gates or HardGates(minimum_valid_output_rate=0.9)
    passing = [result for result in results if passes_hard_gates(result, active_gates)]
    if not passing:
        raise ValueError("No candidate passed all Phase 1 hard gates")
    return min(
        passing,
        key=lambda result: (
            -result.human_rubric_average,
            result.peak_gpu_memory_mb,
            result.median_latency_ms,
            result.model_id,
        ),
    )
