import json
from pathlib import Path

import pytest

from src.outreach.bundle_io import BundleReadError, load_and_validate_bundle
from src.outreach.bundles import create_bundle
from src.schemas.inference import InferenceResponse


def valid_response_data() -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "request_id": "req_0123456789ab",
        "model": {
            "model_id": "Qwen/Qwen3-4B-Instruct-2507",
            "model_revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
            "adapter_id": None,
            "adapter_revision": None,
        },
        "generation": {"do_sample": False, "max_new_tokens": 256, "seed": 42},
        "output": {
            "subject": "A simpler reporting workflow",
            "body": "Could reducing manual reporting help your operations team?",
            "claims_used": ["claim-001"],
            "uncertainty_notes": [],
        },
        "runtime": {
            "python_version": "3.12.12",
            "torch_version": "2.8.0",
            "transformers_version": "5.14.1",
            "cuda_version": "12.6",
            "gpu_name": "Tesla T4",
            "gpu_memory_mb": 15360,
            "latency_ms": 1250.5,
        },
    }


def test_bundle_file_is_loaded_and_validated(tmp_path: Path) -> None:
    response = InferenceResponse.model_validate(valid_response_data())
    bundle = create_bundle(response)
    path = tmp_path / "result.json"
    path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")

    loaded = load_and_validate_bundle(
        path,
        expected_request_id=response.request_id,
        expected_model_revision=response.model.model_revision,
    )

    assert loaded.payload == response


def test_bundle_file_rejects_invalid_json_and_large_input(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json", encoding="utf-8")
    with pytest.raises(BundleReadError, match="valid JSON"):
        load_and_validate_bundle(
            invalid,
            expected_request_id="req_0123456789ab",
            expected_model_revision="a" * 40,
        )

    large = tmp_path / "large.json"
    large.write_text(json.dumps({"padding": "x" * 1_000_001}), encoding="utf-8")
    with pytest.raises(BundleReadError, match="size limit"):
        load_and_validate_bundle(
            large,
            expected_request_id="req_0123456789ab",
            expected_model_revision="a" * 40,
        )
