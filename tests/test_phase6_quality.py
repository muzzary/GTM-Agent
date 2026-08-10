import pytest
from pydantic import ValidationError

from src.evaluation.phase6_quality import (
    evaluate_grounded_output,
    evaluate_grounded_structure,
)
from src.schemas.inference import (
    GroundedOutreachOutput,
    OutreachConstraints,
    SentenceSupportVerdict,
    SupportMapEntry,
)


def entry(
    sentence: str,
    role: str,
    *,
    claim_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    cta_kind: str | None = None,
) -> SupportMapEntry:
    return SupportMapEntry(
        sentence=sentence,
        role=role,
        claim_ids=claim_ids or [],
        evidence_ids=evidence_ids or [],
        cta_kind=cta_kind or ("interest_question" if role == "cta" else None),
    )


def grounded_draft() -> GroundedOutreachOutput:
    sentences = [
        entry(
            "Northstar publicly describes weekly compliance reporting.",
            "prospect_fact",
            evidence_ids=["evidence-001"],
        ),
        entry(
            "FlowReport supports scheduled report generation from approved sources.",
            "product_claim",
            claim_ids=["claim-001"],
        ),
        entry(
            "Would comparing your current reporting workflow be useful this "
            "quarter now?",
            "cta",
            claim_ids=["claim-001"],
        ),
    ]
    return GroundedOutreachOutput(
        generation_status="drafted",
        subject="Weekly reporting",
        body=" ".join(item.sentence for item in sentences),
        support_map=sentences,
        uncertainty_notes=[],
    )


def verdict_for(
    item: SupportMapEntry,
    *,
    approved: bool = True,
    mentions_offer: bool = False,
) -> SentenceSupportVerdict:
    return SentenceSupportVerdict(
        role=item.role,
        claim_ids=item.claim_ids,
        evidence_ids=item.evidence_ids,
        cta_kind=item.cta_kind,
        mentions_offer=mentions_offer,
        approved=approved,
    )


def verdicts_for(
    output: GroundedOutreachOutput,
) -> dict[str, SentenceSupportVerdict]:
    return {item.sentence: verdict_for(item) for item in output.support_map}


def test_grounded_draft_passes_all_hard_gates() -> None:
    output = grounded_draft()

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
        support_verdicts=verdicts_for(output),
    )

    assert report.passed is True
    assert report.violations == []
    assert report.subject_word_count == 2
    assert report.body_word_count >= 25


def test_structural_evaluation_does_not_fabricate_semantic_verdicts() -> None:
    output = grounded_draft()

    report = evaluate_grounded_structure(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
    )

    assert report.passed is True
    assert report.violations == []


def test_output_contract_requires_exact_body_support_map_coverage() -> None:
    with pytest.raises(ValidationError, match="support map"):
        GroundedOutreachOutput(
            generation_status="drafted",
            subject="Weekly reporting",
            body="A sentence that is not mapped.",
            support_map=[entry("Is this a different sentence?", "cta")],
            uncertainty_notes=[],
        )


def test_unknown_ids_and_missing_semantic_verdicts_fail_closed() -> None:
    output = grounded_draft()

    report = evaluate_grounded_output(
        output,
        approved_claim_ids=set(),
        approved_evidence_ids=set(),
        support_verdicts={},
    )

    assert report.passed is False
    assert {violation.code for violation in report.violations} == {
        "citation_precision_missing",
        "unknown_claim_id",
        "unknown_evidence_id",
    }


def test_mixed_claim_and_evidence_sentence_is_rejected() -> None:
    mixed = entry(
        "Northstar uses FlowReport for weekly reporting.",
        "product_claim",
        claim_ids=["claim-001"],
        evidence_ids=["evidence-001"],
    )
    output = GroundedOutreachOutput(
        generation_status="drafted",
        subject="Weekly reporting",
        body=(
            f"{mixed.sentence} Would reviewing the workflow be useful to your team "
            "during this quarter?"
        ),
        support_map=[
            mixed,
            entry(
                "Would reviewing the workflow be useful to your team during "
                "this quarter?",
                "cta",
            ),
        ],
        uncertainty_notes=[],
    )

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
        support_verdicts={mixed.sentence: verdict_for(mixed)},
    )

    assert "unsupported_fact_combination" in {
        violation.code for violation in report.violations
    }


def test_hypothesis_must_remain_uncertain_and_draft_has_one_cta() -> None:
    sentences = [
        entry("Your team manually consolidates every report.", "hypothesis"),
        entry(
            "FlowReport supports scheduled reports.",
            "product_claim",
            claim_ids=["claim-001"],
        ),
    ]
    output = GroundedOutreachOutput(
        generation_status="drafted",
        subject="Reporting workflow",
        body=" ".join(item.sentence for item in sentences)
        + " This additional wording keeps the body above the minimum required length.",
        support_map=[
            *sentences,
            entry(
                "This additional wording keeps the body above the minimum "
                "required length.",
                "hypothesis",
            ),
        ],
        uncertainty_notes=[],
    )

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids=set(),
        support_verdicts=verdicts_for(output),
    )

    codes = {violation.code for violation in report.violations}
    assert "hypothesis_as_fact" in codes
    assert "cta_count" in codes


def test_unapproved_offer_and_length_bounds_are_rejected() -> None:
    output = grounded_draft().model_copy(
        update={
            "subject": "An excessively long subject about weekly compliance reporting",
            "support_map": [
                *grounded_draft().support_map[:-1],
                entry(
                    "Can I send you a complimentary assessment?",
                    "cta",
                    cta_kind="approved_offer",
                ),
            ],
        }
    )
    output = output.model_copy(
        update={"body": " ".join(item.sentence for item in output.support_map)}
    )

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
        support_verdicts=verdicts_for(output),
    )

    codes = {violation.code for violation in report.violations}
    assert "subject_length" in codes
    assert "unapproved_offer" in codes


@pytest.mark.parametrize(
    "status",
    ["needs_more_evidence", "disqualified", "opted_out"],
)
def test_safe_abstention_contains_no_sendable_copy(status: str) -> None:
    output = GroundedOutreachOutput(
        generation_status=status,
        subject="",
        body="",
        support_map=[],
        uncertainty_notes=["No safe outreach draft should be produced."],
    )

    report = evaluate_grounded_output(
        output,
        approved_claim_ids=set(),
        approved_evidence_ids=set(),
        support_verdicts={},
    )

    assert report.passed is True


def test_abstention_contract_rejects_sendable_copy() -> None:
    with pytest.raises(ValidationError, match="must not contain outreach copy"):
        GroundedOutreachOutput(
            generation_status="opted_out",
            subject="One more thought",
            body="Should we talk?",
            support_map=[entry("Should we talk?", "cta")],
            uncertainty_notes=["The prospect opted out."],
        )


def test_support_map_entry_must_contain_exactly_one_sentence() -> None:
    with pytest.raises(ValidationError, match="exactly one sentence"):
        entry(
            "Northstar publishes reports. It also operates regional hubs.",
            "prospect_fact",
            evidence_ids=["evidence-001"],
        )


def test_every_sentence_requires_an_exact_positive_semantic_verdict() -> None:
    output = grounded_draft()
    verdicts = verdicts_for(output)
    verdicts[output.support_map[2].sentence] = verdict_for(
        output.support_map[2], approved=False
    )
    verdicts["A sentence that is not in the output."] = verdict_for(
        output.support_map[0]
    )

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
        support_verdicts=verdicts,
    )

    codes = {violation.code for violation in report.violations}
    assert "citation_precision_failed" in codes
    assert "unexpected_support_verdict" in codes


def test_configured_word_bounds_are_enforced() -> None:
    output = grounded_draft()

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
        support_verdicts=verdicts_for(output),
        constraints=OutreachConstraints(body_min_words=100),
    )

    assert "body_length" in {item.code for item in report.violations}


def test_abstention_note_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="uncertainty note"):
        GroundedOutreachOutput(
            generation_status="needs_more_evidence",
            subject="",
            body="",
            support_map=[],
            uncertainty_notes=[""],
        )


def test_verdict_snapshot_must_match_role_and_support_ids() -> None:
    output = grounded_draft()
    verdicts = verdicts_for(output)
    prospect_sentence = output.support_map[0].sentence
    verdicts[prospect_sentence] = verdicts[prospect_sentence].model_copy(
        update={"role": "hypothesis", "evidence_ids": []}
    )

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
        support_verdicts=verdicts,
    )

    assert "support_verdict_mismatch" in {
        violation.code for violation in report.violations
    }


def test_offer_semantics_require_an_approved_claim_even_when_mislabeled() -> None:
    output = grounded_draft()
    offer = entry(
        "Can I send you a complimentary assessment?",
        "cta",
        cta_kind="interest_question",
    )
    output = GroundedOutreachOutput(
        generation_status="drafted",
        subject=output.subject,
        body=" ".join(
            [*(item.sentence for item in output.support_map[:-1]), offer.sentence]
        ),
        support_map=[*output.support_map[:-1], offer],
        uncertainty_notes=[],
    )
    verdicts = verdicts_for(output)
    verdicts[offer.sentence] = verdict_for(offer, mentions_offer=True)

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
        support_verdicts=verdicts,
    )

    assert "unapproved_offer" in {item.code for item in report.violations}


def test_every_cta_requires_an_approved_claim() -> None:
    output = grounded_draft()
    unsupported_cta = output.support_map[-1].model_copy(update={"claim_ids": []})
    output = GroundedOutreachOutput(
        generation_status="drafted",
        subject=output.subject,
        body=" ".join(
            [
                *(item.sentence for item in output.support_map[:-1]),
                unsupported_cta.sentence,
            ]
        ),
        support_map=[*output.support_map[:-1], unsupported_cta],
        uncertainty_notes=[],
    )

    report = evaluate_grounded_output(
        output,
        approved_claim_ids={"claim-001"},
        approved_evidence_ids={"evidence-001"},
        support_verdicts=verdicts_for(output),
    )

    assert "cta_claim_required" in {item.code for item in report.violations}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subject_max_words", 7),
        ("body_min_words", 24),
        ("body_max_words", 151),
    ],
)
def test_configured_bounds_cannot_weaken_mandatory_limits(
    field: str, value: int
) -> None:
    with pytest.raises(ValidationError):
        OutreachConstraints(**{field: value})


@pytest.mark.parametrize(
    "claim_ids",
    [["claim-001", "claim-001"], ["claim-002", "claim-001"]],
)
def test_support_and_verdict_ids_must_be_unique_and_sorted(
    claim_ids: list[str],
) -> None:
    with pytest.raises(ValidationError, match="unique and sorted"):
        entry(
            "FlowReport supports scheduled reporting.",
            "product_claim",
            claim_ids=claim_ids,
        )

    with pytest.raises(ValidationError, match="unique and sorted"):
        SentenceSupportVerdict(
            role="product_claim",
            claim_ids=claim_ids,
            mentions_offer=False,
            approved=True,
        )
