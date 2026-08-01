from copy import deepcopy

import pytest
from pydantic import ValidationError

from src.outreach.bundles import (
    BundleIntegrityError,
    BundleMismatchError,
    DuplicateBundleError,
    create_bundle,
    validate_bundle,
)
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
        "generation": {
            "do_sample": False,
            "max_new_tokens": 256,
            "seed": 42,
        },
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


def test_valid_bundle_round_trip() -> None:
    response = InferenceResponse.model_validate(valid_response_data())
    bundle = create_bundle(response)

    validated = validate_bundle(
        bundle.model_dump(mode="json"),
        expected_request_id=response.request_id,
        expected_model_revision=response.model.model_revision,
    )

    assert validated.payload == response


def test_modified_payload_fails_integrity_check() -> None:
    response = InferenceResponse.model_validate(valid_response_data())
    raw_bundle = create_bundle(response).model_dump(mode="json")
    raw_bundle["payload"]["output"]["subject"] = "Tampered subject"  # type: ignore[index]

    with pytest.raises(BundleIntegrityError, match="integrity"):
        validate_bundle(
            raw_bundle,
            expected_request_id=response.request_id,
            expected_model_revision=response.model.model_revision,
        )


def test_request_or_model_revision_mismatch_is_rejected() -> None:
    response = InferenceResponse.model_validate(valid_response_data())
    bundle = create_bundle(response).model_dump(mode="json")

    with pytest.raises(BundleMismatchError, match="request"):
        validate_bundle(
            bundle,
            expected_request_id="req_abcdef012345",
            expected_model_revision=response.model.model_revision,
        )

    with pytest.raises(BundleMismatchError, match="model revision"):
        validate_bundle(
            bundle,
            expected_request_id=response.request_id,
            expected_model_revision="0" * 40,
        )


def test_duplicate_bundle_is_rejected() -> None:
    response = InferenceResponse.model_validate(valid_response_data())
    bundle = create_bundle(response).model_dump(mode="json")

    with pytest.raises(DuplicateBundleError, match="already imported"):
        validate_bundle(
            bundle,
            expected_request_id=response.request_id,
            expected_model_revision=response.model.model_revision,
            imported_hashes={bundle["payload_sha256"]},
        )


def test_contract_rejects_extra_fields_and_non_finite_latency() -> None:
    extra = deepcopy(valid_response_data())
    extra["unexpected"] = True
    with pytest.raises(ValidationError):
        InferenceResponse.model_validate(extra)

    non_finite = deepcopy(valid_response_data())
    non_finite["runtime"]["latency_ms"] = float("nan")  # type: ignore[index]
    with pytest.raises(ValidationError):
        InferenceResponse.model_validate(non_finite)
