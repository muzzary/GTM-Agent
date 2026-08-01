from src.outreach.bundles import validate_bundle
from src.outreach.test_double import DeterministicInferenceDouble
from src.schemas.inference import InferenceRequest, ModelIdentity


def test_double_produces_contract_compatible_bundle() -> None:
    model = ModelIdentity(
        model_id="test/deterministic-model",
        model_revision="d" * 40,
        adapter_id=None,
        adapter_revision=None,
    )
    request = InferenceRequest(
        request_id="req_0123456789ab",
        prompt="Write an evidence-aware B2B email.",
        approved_claim_ids=["claim-001"],
    )

    bundle = DeterministicInferenceDouble(model).generate(request)

    validated = validate_bundle(
        bundle.model_dump(mode="json"),
        expected_request_id=request.request_id,
        expected_model_revision=model.model_revision,
    )
    assert validated.payload.output.claims_used == ["claim-001"]
    assert validated.payload.generation.seed == request.seed
