import hashlib
import json
from pathlib import Path

import pytest

from src.evaluation.phase6_benchmark import load_phase6_benchmark
from src.evaluation.phase6_v2 import (
    build_chat_messages,
    build_phase6_v2_prompt,
    render_v2_prompt,
    training_prompt_input,
    training_target_json,
)
from src.schemas.dataset import DatasetManifestV2, DatasetSplit
from src.schemas.inference import GroundedOutreachOutput
from src.training.dataset import DatasetValidationError, validate_dataset_v2
from tests.test_phase6_dataset_v2 import reviewed_example

BENCHMARK_PATH = Path("configs/phase6/benchmark-v2.json")
PROMPT_SHA256 = "5848334fc2742fe53d55d8da0a748ce82b1ad7a734f0caa2d8168f475ba7ca19"


def benchmark():
    return load_phase6_benchmark(BENCHMARK_PATH)


def dataset(*examples):
    return DatasetManifestV2.model_construct(
        dataset_id="dataset-phase6-v2-test",
        dataset_version="2.0",
        examples=list(examples),
        content_sha256="0" * 64,
    )


def malformed(example, **updates):
    return example.model_copy(update=updates)


def test_training_and_benchmark_prompt_renderers_are_identical():
    case = benchmark().cases[0]
    example = malformed(
        reviewed_example(),
        input=case.input,
        product_name=case.product_name,
        scenario_kind=case.scenario_kind,
    )

    assert render_v2_prompt(training_prompt_input(example)) == (
        build_phase6_v2_prompt(case)
    )


def test_benchmark_prompt_hash_is_pinned():
    prompt = build_phase6_v2_prompt(benchmark().cases[0])

    assert hashlib.sha256(prompt.encode("utf-8")).hexdigest() == PROMPT_SHA256


def test_chat_messages_match_evaluation_contract():
    prompt = "prompt"

    assert build_chat_messages(prompt) == [
        {"role": "system", "content": "Return strict JSON only."},
        {"role": "user", "content": prompt},
    ]
    assert build_chat_messages(prompt, "{}") == [
        {"role": "system", "content": "Return strict JSON only."},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "{}"},
    ]


def test_training_target_json_round_trips():
    example = reviewed_example()

    restored = GroundedOutreachOutput.model_validate(
        json.loads(training_target_json(example))
    )

    assert restored == example.approved_output


def test_v2_audit_reports_status_counts():
    report = validate_dataset_v2(dataset(reviewed_example()), benchmark())

    assert report.passed is True
    assert report.status_counts[DatasetSplit.TRAIN.value] == {
        "drafted": 1,
        "needs_more_evidence": 0,
        "disqualified": 0,
        "opted_out": 0,
    }


def test_v2_audit_rejects_duplicate_example_ids():
    base = reviewed_example()

    with pytest.raises(DatasetValidationError, match="duplicate example IDs"):
        validate_dataset_v2(dataset(base, base), benchmark())


def test_v2_audit_rejects_duplicate_content_hashes():
    base = reviewed_example()
    other = base.model_copy(update={"example_id": "dataset-example-v2-other"})

    with pytest.raises(DatasetValidationError, match="duplicate content hash"):
        validate_dataset_v2(dataset(base, other), benchmark())


def test_v2_audit_rejects_identity_groups_crossing_splits():
    base = reviewed_example()
    other = malformed(
        base,
        example_id="dataset-example-v2-valid",
        split=DatasetSplit.VALIDATION,
        product_name="Another FlowReport",
    )

    with pytest.raises(DatasetValidationError, match="crosses dataset splits"):
        validate_dataset_v2(dataset(base, other), benchmark())


def test_v2_audit_rejects_benchmark_identity_leakage():
    case = benchmark().cases[0]
    leaked = reviewed_example(
        identity_groups=case.identity_groups,
    )

    with pytest.raises(DatasetValidationError, match="frozen benchmark"):
        validate_dataset_v2(dataset(leaked), benchmark())


def test_v2_audit_rejects_unsupported_support_map_ids():
    base = reviewed_example()
    output = base.approved_output.model_copy(
        update={
            "support_map": [
                base.approved_output.support_map[0].model_copy(
                    update={"evidence_ids": ["evidence-not-in-input"]}
                ),
                *base.approved_output.support_map[1:],
            ]
        }
    )
    malformed_row = malformed(base, approved_output=output)

    with pytest.raises(DatasetValidationError, match="unsupported evidence"):
        validate_dataset_v2(dataset(malformed_row), benchmark())


def test_v2_audit_rejects_unreviewed_training_row():
    base = reviewed_example()
    malformed_row = malformed(
        base, review=base.review.model_copy(update={"status": "pending"})
    )

    with pytest.raises(DatasetValidationError, match="unreviewed training"):
        validate_dataset_v2(dataset(malformed_row), benchmark())


def test_v2_audit_rejects_benchmark_content_hash_overlap():
    base = reviewed_example()
    malformed_row = malformed(
        base, content_sha256=benchmark().cases[0].content_sha256
    )

    with pytest.raises(DatasetValidationError, match="prompt content"):
        validate_dataset_v2(dataset(malformed_row), benchmark())
