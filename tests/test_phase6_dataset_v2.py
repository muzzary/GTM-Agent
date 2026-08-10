import json
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from pydantic import ValidationError

from src.schemas.dataset import (
    ApprovedClaimRecord,
    EvidenceRecordV2,
    HumanRubricScores,
    IdentityGroups,
    TrainingExampleV2,
    TrainingInputV2,
    TrainingProvenanceV2,
    TrainingReviewV2,
    _content_digest,
)
from src.schemas.inference import (
    GroundedOutreachOutput,
    OutreachConstraints,
    SentenceSupportVerdict,
    SupportMapEntry,
)


def grounded_output() -> GroundedOutreachOutput:
    support_map = [
        SupportMapEntry(
            sentence="Northstar publicly describes weekly compliance reporting.",
            role="prospect_fact",
            evidence_ids=["evidence-001"],
        ),
        SupportMapEntry(
            sentence="FlowReport supports scheduled report generation.",
            role="product_claim",
            claim_ids=["claim-001"],
        ),
        SupportMapEntry(
            sentence=(
                "Would comparing your current reporting workflow be useful to your "
                "operations team this quarter?"
                ),
                role="cta",
                cta_kind="interest_question",
                claim_ids=["claim-001"],
            ),
    ]
    return GroundedOutreachOutput(
        generation_status="drafted",
        subject="Weekly reporting",
        body=" ".join(item.sentence for item in support_map),
        support_map=support_map,
        uncertainty_notes=[],
    )


def review_verdicts(
    output: GroundedOutreachOutput,
) -> dict[str, SentenceSupportVerdict]:
    return {
        item.sentence: SentenceSupportVerdict(
            role=item.role,
            claim_ids=item.claim_ids,
            evidence_ids=item.evidence_ids,
            cta_kind=item.cta_kind,
            mentions_offer=False,
            approved=True,
        )
        for item in output.support_map
    }


def reviewed_example(**updates: object) -> TrainingExampleV2:
    output = grounded_output()
    values: dict[str, object] = {
        "example_id": "dataset-example-v2-train01",
        "schema_version": "2.0",
        "split": "train",
        "task_type": "outreach_generation",
        "identity_groups": IdentityGroups(
            product_group="product-reporting",
            icp_group="regulated_operations",
            company_group="company-northstar",
            prospect_group="prospect-operations-director",
        ),
        "prompt_template_version": "outreach-grounded-v2",
        "input": TrainingInputV2(
            target_role="Director of Operations",
            approved_claims=[
                ApprovedClaimRecord(
                    claim_id="claim-001",
                    text="FlowReport supports scheduled report generation.",
                    source_kind="approved_product_profile",
                    source_reference="product-profile-flowreport-v1",
                    license_kind="synthetic",
                    license_basis="Project-owned product claim",
                )
            ],
            prospect_evidence=[
                EvidenceRecordV2(
                    evidence_id="evidence-001",
                    text="Northstar publicly describes weekly compliance reporting.",
                    source_url="https://example.com/northstar/reporting",
                    collected_at=datetime(2026, 8, 10, tzinfo=UTC),
                    content_sha256="a" * 64,
                    source_kind="public_company_page",
                    source_reference="northstar-reporting-page",
                    license_kind="synthetic",
                    license_basis="Reviewed factual excerpt for this example",
                )
            ],
            pain_hypotheses=[
                "Recurring reporting may require manual consolidation."
            ],
            constraints=OutreachConstraints(),
        ),
        "approved_output": output,
        "provenance": TrainingProvenanceV2(
            source_kind="first_party_synthetic",
            source_reference="phase6-reviewed-v2",
            license_kind="synthetic",
            license_basis="Project-owned reviewed example",
            generation_method="human_authored",
            reviewer_reference="reviewer-phase6-01",
            reviewed_at=datetime(2026, 8, 10, tzinfo=UTC),
        ),
        "review": TrainingReviewV2(
            status="reviewed",
            hard_gates_passed=True,
            support_verdicts=review_verdicts(output),
            scores=HumanRubricScores(
                personalization=5,
                grounding=5,
                clarity=4,
                differentiation=4,
                cta_quality=5,
                brand_fit=5,
            ),
            review_notes=[],
        ),
    }
    values.update(updates)
    return TrainingExampleV2(**values)


def test_reviewed_v2_training_example_populates_stable_content_hash() -> None:
    training_example = reviewed_example()

    assert len(training_example.content_sha256) == 64
    assert training_example.review.scores is not None
    assert training_example.review.scores.average == pytest.approx(4.6667, abs=0.001)


def test_v2_training_example_rejects_tampered_content_hash() -> None:
    with pytest.raises(ValidationError, match="content_sha256"):
        reviewed_example(content_sha256="f" * 64)


def test_train_split_requires_reviewed_hard_gate_pass() -> None:
    with pytest.raises(ValidationError, match="training split"):
        reviewed_example(
            review=TrainingReviewV2(
                status="pending",
                hard_gates_passed=False,
                support_verdicts={},
                scores=None,
                review_notes=["Awaiting review."],
            )
        )


def test_reviewed_record_requires_scores_and_positive_support_verdicts() -> None:
    with pytest.raises(ValidationError, match="reviewed record"):
        reviewed_example(
            review=TrainingReviewV2(
                status="reviewed",
                hard_gates_passed=True,
                support_verdicts={
                    "Unsupported sentence.": SentenceSupportVerdict(
                        role="hypothesis",
                        mentions_offer=False,
                        approved=False,
                    )
                },
                scores=None,
                review_notes=[],
            )
        )


def test_public_dataset_provenance_requires_license_url() -> None:
    with pytest.raises(ValidationError, match="license URL"):
        TrainingProvenanceV2(
            source_kind="public_dataset",
            source_reference="external-row-1",
            license_kind="public_dataset",
            license_basis="Apache-2.0",
            generation_method="human_authored",
            reviewer_reference="reviewer-phase6-01",
            reviewed_at=datetime(2026, 8, 10, tzinfo=UTC),
        )


def test_public_claim_and_evidence_sources_require_license_urls() -> None:
    with pytest.raises(ValidationError, match="public claim source"):
        ApprovedClaimRecord(
            claim_id="claim-001",
            text="A public dataset claim.",
            source_kind="public_dataset",
            source_reference="external-claim-1",
            license_kind="public_dataset",
            license_basis="Apache-2.0",
        )

    with pytest.raises(ValidationError, match="public evidence source"):
        EvidenceRecordV2(
            evidence_id="evidence-001",
            text="A public dataset evidence excerpt.",
            source_url="https://example.com/source",
            collected_at=datetime(2026, 8, 10, tzinfo=UTC),
            content_sha256="a" * 64,
            source_kind="public_dataset",
            source_reference="external-evidence-1",
            license_kind="public_dataset",
            license_basis="Apache-2.0",
        )


def test_v2_training_example_round_trips_through_json() -> None:
    training_example = reviewed_example()

    restored = TrainingExampleV2.model_validate_json(
        training_example.model_dump_json()
    )

    assert restored == training_example
    assert restored.content_sha256 == training_example.content_sha256


def test_automatic_hash_uses_normalized_defaults() -> None:
    payload = json.loads(reviewed_example().model_dump_json())
    payload.pop("content_sha256")
    payload["input"].pop("pain_hypotheses")
    payload["review"].pop("review_notes")

    restored = TrainingExampleV2.model_validate(payload)

    assert restored.content_sha256 == restored.content_sha256_for_audit()


def test_train_row_cannot_claim_success_when_actual_hard_gates_fail() -> None:
    base = reviewed_example()
    invalid_output = base.approved_output.model_copy(
        update={
            "support_map": base.approved_output.support_map[:-1],
            "body": " ".join(
                item.sentence for item in base.approved_output.support_map[:-1]
            ),
        }
    )
    invalid_review = base.review.model_copy(
        update={
            "support_verdicts": review_verdicts(invalid_output)
        }
    )

    with pytest.raises(ValidationError, match="hard gates"):
        reviewed_example(
            approved_output=invalid_output,
            review=invalid_review,
        )


def test_train_row_uses_its_configured_bounds() -> None:
    base = reviewed_example()
    strict_input = base.input.model_copy(
        update={
            "constraints": base.input.constraints.model_copy(
                update={"body_min_words": 100}
            )
        }
    )

    with pytest.raises(ValidationError, match="hard gates"):
        reviewed_example(input=strict_input)


def test_content_hash_normalizes_equivalent_unicode() -> None:
    base = reviewed_example()
    composed_claim = base.input.approved_claims[0].model_copy(
        update={"text": "Café reporting"}
    )
    decomposed_claim = base.input.approved_claims[0].model_copy(
        update={"text": "Cafe\u0301 reporting"}
    )
    composed = reviewed_example(
        input=base.input.model_copy(update={"approved_claims": [composed_claim]})
    )
    decomposed = reviewed_example(
        input=base.input.model_copy(update={"approved_claims": [decomposed_claim]})
    )

    assert composed.content_sha256 == decomposed.content_sha256


def test_v1_content_digest_remains_byte_compatible() -> None:
    content = {"text": "Cafe\u0301"}
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    assert _content_digest(content) == sha256(canonical.encode("utf-8")).hexdigest()
