from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.schemas.campaign import (
    ApprovalDecision,
    ApprovalRecord,
    CampaignInput,
    ClaimDecision,
    ClaimWordingSource,
    EvaluationCheck,
    EvaluationResult,
    TraceEvent,
    TraceEventType,
)


def valid_campaign_input() -> dict[str, object]:
    return {
        "product_name": "RouteSignal",
        "product_url": "https://example.com/routesignal",
        "short_description": "Highlights recurring delivery exceptions.",
        "known_capabilities": ["exception reporting"],
        "known_limitations": ["requires dispatch data"],
        "icp": {
            "industries": ["logistics"],
            "company_size": "mid-market",
            "roles": ["Head of Operations"],
            "pain_hypotheses": ["manual exception review"],
        },
    }


def test_campaign_input_is_strict_and_requires_workflow_context() -> None:
    payload = valid_campaign_input()
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        CampaignInput.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("known_capabilities",), ["   "]),
        (("known_capabilities",), ["a" * 201]),
        (("known_capabilities",), ["same", " same "]),
        (("icp", "industries"), ["logistics\u0000"]),
        (("icp", "roles"), ["a" * 121]),
        (("icp", "pain_hypotheses"), ["a" * 501]),
    ],
)
def test_campaign_input_rejects_malformed_list_items(
    path: tuple[str, ...], value: object
) -> None:
    payload = valid_campaign_input()
    target = payload
    for part in path[:-1]:
        target = target[part]  # type: ignore[index,assignment]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(ValidationError):
        CampaignInput.model_validate(payload)


def test_campaign_input_trims_values_without_reordering_them() -> None:
    payload = valid_campaign_input()
    payload["product_name"] = "  RouteSignal  "
    payload["known_capabilities"] = [" reporting ", " alerts "]

    parsed = CampaignInput.model_validate(payload)

    assert parsed.product_name == "RouteSignal"
    assert parsed.known_capabilities == ["reporting", "alerts"]


def test_campaign_input_normalizes_optional_regions() -> None:
    payload = valid_campaign_input()

    global_campaign = CampaignInput.model_validate(payload)
    payload["icp"]["regions"] = [" United States ", "Canada"]  # type: ignore[index]
    regional_campaign = CampaignInput.model_validate(payload)

    assert global_campaign.icp.regions == []
    assert regional_campaign.icp.regions == ["United States", "Canada"]

    payload["icp"]["regions"] = ["Canada", " Canada "]  # type: ignore[index]
    with pytest.raises(ValidationError):
        CampaignInput.model_validate(payload)


def test_claim_decision_enforces_edit_authorization_shape() -> None:
    with pytest.raises(ValidationError, match="rejected claim cannot include"):
        ClaimDecision(
            claim_id="claim-0001",
            decision=ApprovalDecision.REJECTED,
            edited_text="Different wording",
        )
    with pytest.raises(ValidationError, match="requires evidence attestation"):
        ClaimDecision(
            claim_id="claim-0001",
            decision=ApprovalDecision.APPROVED,
            edited_text="Different wording",
        )
    with pytest.raises(ValidationError):
        ClaimDecision(
            claim_id="claim-0001",
            decision=ApprovalDecision.APPROVED,
            edited_text="   ",
            evidence_attested=True,
        )

    payload = valid_campaign_input()
    payload["known_capabilities"] = []

    with pytest.raises(ValidationError):
        CampaignInput.model_validate(payload)


def test_approval_and_evaluation_are_first_class_serializable_records() -> None:
    decided_at = datetime(2026, 8, 2, 10, 30, tzinfo=UTC)
    approval = ApprovalRecord(
        approval_id="approval-0001",
        campaign_id="campaign-0001",
        claim_id="claim-0001",
        decision=ApprovalDecision.APPROVED,
        original_text="RouteSignal supports exception reporting.",
        reviewed_text="RouteSignal supports exception reporting.",
        evidence_ids=("evidence-0001",),
        wording_source=ClaimWordingSource.PROPOSED,
        evidence_attested=False,
        decided_at=decided_at,
    )
    evaluation = EvaluationResult(
        evaluation_id="evaluation-0001",
        campaign_id="campaign-0001",
        draft_id="draft-0001",
        passed=True,
        checks=[
            EvaluationCheck(
                name="approved_claims_only",
                passed=True,
                reason="Every referenced claim is approved.",
            )
        ],
        evaluated_at=decided_at,
    )

    assert ApprovalRecord.model_validate_json(approval.model_dump_json()) == approval
    restored_evaluation = EvaluationResult.model_validate_json(
        evaluation.model_dump_json()
    )
    assert restored_evaluation == evaluation


def test_approval_record_rejects_inconsistent_review_provenance() -> None:
    with pytest.raises(ValidationError, match="edited approval"):
        ApprovalRecord(
            approval_id="approval-0001",
            campaign_id="campaign-0001",
            claim_id="claim-0001",
            decision=ApprovalDecision.APPROVED,
            original_text="Original",
            reviewed_text="Edited",
            evidence_ids=("evidence-0001",),
            wording_source=ClaimWordingSource.USER_EDITED,
            evidence_attested=False,
            decided_at=datetime(2026, 8, 2, 10, 30, tzinfo=UTC),
        )


def test_trace_event_has_stable_json_and_is_immutable() -> None:
    event = TraceEvent(
        event_id="trace-0001",
        campaign_id="campaign-0001",
        sequence=1,
        event_type=TraceEventType.CAMPAIGN_CREATED,
        occurred_at=datetime(2026, 8, 2, 10, 30, tzinfo=UTC),
        input_ids=("product-0001", "icp-0001"),
        output_ids=("campaign-0001",),
        summary="Campaign accepted for fixture processing.",
    )

    serialized = event.model_dump_json()

    assert TraceEvent.model_validate_json(serialized) == event
    assert '"occurred_at":"2026-08-02T10:30:00Z"' in serialized
    with pytest.raises(ValidationError):
        event.sequence = 2
