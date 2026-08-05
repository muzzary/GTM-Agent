import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.evaluation.phase1 import load_manifest
from src.evaluation.phase5 import (
    benchmark_evidence_ids,
    evaluate_baseline_output,
)
from src.schemas.inference import OutreachOutput

MANIFEST_PATH = Path("configs/phase1/benchmark.json")


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
