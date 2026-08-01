import json
from pathlib import Path

import pytest

from src.evaluation.phase1 import (
    choose_winner,
    evaluate_output,
    load_manifest,
    parse_model_output,
)
from src.schemas.benchmark import CandidateResult

MANIFEST_PATH = Path("configs/phase1/benchmark.json")


def test_manifest_covers_three_product_and_icp_patterns() -> None:
    manifest = load_manifest(MANIFEST_PATH)

    assert len(manifest.cases) == 9
    assert len({case.product_category for case in manifest.cases}) == 3
    assert len({case.icp_pattern for case in manifest.cases}) == 3
    assert len({case.case_id for case in manifest.cases}) == 9
    assert all(len(candidate.revision) == 40 for candidate in manifest.candidates)


def test_model_output_must_be_strict_json() -> None:
    valid = json.dumps(
        {
            "subject": "Reduce reporting delays",
            "body": "Would a scheduled reporting workflow help your team?",
            "claims_used": ["claim-001"],
            "uncertainty_notes": [],
        }
    )

    assert parse_model_output(valid).claims_used == ["claim-001"]

    with pytest.raises(ValueError, match="valid JSON"):
        parse_model_output("Here is the JSON: " + valid)

    with pytest.raises(ValueError, match="valid output contract"):
        parse_model_output(valid[:-1] + ', "extra": true}')


def test_unsupported_claims_fail_automatic_evaluation() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    case = manifest.cases[0]
    output = parse_model_output(
        json.dumps(
            {
                "subject": "Relevant subject",
                "body": "A concise evidence-aware message.",
                "claims_used": ["invented-claim"],
                "uncertainty_notes": [],
            }
        )
    )

    result = evaluate_output(case, output)

    assert result.unsupported_claims == ["invented-claim"]
    assert result.passes_claim_gate is False


def test_winner_requires_hard_gates_then_uses_stable_tie_break() -> None:
    failing = CandidateResult(
        model_id="model/failing",
        model_revision="a" * 40,
        total_outputs=10,
        valid_outputs=10,
        unsupported_claim_count=1,
        qlora_smoke_passed=True,
        human_rubric_average=5.0,
        peak_gpu_memory_mb=6000,
        median_latency_ms=800,
    )
    slower = CandidateResult(
        model_id="model/slower",
        model_revision="b" * 40,
        total_outputs=10,
        valid_outputs=10,
        unsupported_claim_count=0,
        qlora_smoke_passed=True,
        human_rubric_average=4.0,
        peak_gpu_memory_mb=7000,
        median_latency_ms=900,
    )
    faster = CandidateResult(
        model_id="model/faster",
        model_revision="c" * 40,
        total_outputs=10,
        valid_outputs=10,
        unsupported_claim_count=0,
        qlora_smoke_passed=True,
        human_rubric_average=4.0,
        peak_gpu_memory_mb=7000,
        median_latency_ms=700,
    )

    assert choose_winner([failing, slower, faster]).model_id == "model/faster"


def test_no_candidate_passing_hard_gates_is_explicit() -> None:
    result = CandidateResult(
        model_id="model/failing",
        model_revision="a" * 40,
        total_outputs=10,
        valid_outputs=8,
        unsupported_claim_count=0,
        qlora_smoke_passed=True,
        human_rubric_average=5.0,
        peak_gpu_memory_mb=6000,
        median_latency_ms=800,
    )

    with pytest.raises(ValueError, match="No candidate passed"):
        choose_winner([result])
