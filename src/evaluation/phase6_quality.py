import re
from collections.abc import Mapping, Set

from pydantic import Field

from src.schemas.base import StrictModel
from src.schemas.inference import (
    GroundedOutreachOutput,
    OutreachConstraints,
    SentenceSupportVerdict,
    SupportMapEntry,
)

_UNCERTAINTY_MARKERS = ("may", "might", "could", "whether", "wonder")


class HardGateViolation(StrictModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    sentence: str | None = Field(default=None, max_length=500)


class GroundedQualityReport(StrictModel):
    passed: bool
    subject_word_count: int = Field(ge=0)
    body_word_count: int = Field(ge=0)
    violations: list[HardGateViolation] = Field(max_length=128)


def evaluate_grounded_output(
    output: GroundedOutreachOutput,
    *,
    approved_claim_ids: Set[str],
    approved_evidence_ids: Set[str],
    support_verdicts: Mapping[str, SentenceSupportVerdict],
    constraints: OutreachConstraints | None = None,
) -> GroundedQualityReport:
    structural = evaluate_grounded_structure(
        output,
        approved_claim_ids=approved_claim_ids,
        approved_evidence_ids=approved_evidence_ids,
        constraints=constraints,
    )
    violations = [
        *_support_verdict_violations(output, support_verdicts),
        *_semantic_offer_violations(output, support_verdicts),
        *structural.violations,
    ]
    return GroundedQualityReport(
        passed=not violations,
        subject_word_count=structural.subject_word_count,
        body_word_count=structural.body_word_count,
        violations=violations,
    )


def evaluate_grounded_structure(
    output: GroundedOutreachOutput,
    *,
    approved_claim_ids: Set[str],
    approved_evidence_ids: Set[str],
    constraints: OutreachConstraints | None = None,
) -> GroundedQualityReport:
    """Evaluate deterministic gates without asserting semantic support."""
    constraints = constraints or OutreachConstraints()
    subject_word_count = _word_count(output.subject)
    body_word_count = _word_count(output.body)
    violations: list[HardGateViolation] = []

    if output.generation_status != "drafted":
        return GroundedQualityReport(
            passed=not violations,
            subject_word_count=subject_word_count,
            body_word_count=body_word_count,
            violations=violations,
        )

    if not (
        constraints.subject_min_words
        <= subject_word_count
        <= constraints.subject_max_words
    ):
        violations.append(
            HardGateViolation(
                code="subject_length",
                message=(
                    "draft subject must contain between "
                    f"{constraints.subject_min_words} and "
                    f"{constraints.subject_max_words} words"
                ),
            )
        )
    if not constraints.body_min_words <= body_word_count <= constraints.body_max_words:
        violations.append(
            HardGateViolation(
                code="body_length",
                message=(
                    "draft body must contain between "
                    f"{constraints.body_min_words} and "
                    f"{constraints.body_max_words} words"
                ),
            )
        )

    cta_entries = [entry for entry in output.support_map if entry.role == "cta"]
    if len(cta_entries) != constraints.cta_count:
        violations.append(
            HardGateViolation(
                code="cta_count",
                message="draft must contain exactly one CTA sentence",
            )
        )

    for entry in output.support_map:
        violations.extend(
            _entry_violations(
                entry,
                approved_claim_ids=approved_claim_ids,
                approved_evidence_ids=approved_evidence_ids,
                verdict=None,
            )
        )

    return GroundedQualityReport(
        passed=not violations,
        subject_word_count=subject_word_count,
        body_word_count=body_word_count,
        violations=violations,
    )


def _entry_violations(
    entry: SupportMapEntry,
    *,
    approved_claim_ids: Set[str],
    approved_evidence_ids: Set[str],
    verdict: SentenceSupportVerdict | None,
) -> list[HardGateViolation]:
    violations: list[HardGateViolation] = []
    unknown_claim_ids = sorted(set(entry.claim_ids) - approved_claim_ids)
    unknown_evidence_ids = sorted(set(entry.evidence_ids) - approved_evidence_ids)
    if unknown_claim_ids:
        violations.append(
            _sentence_violation(
                "unknown_claim_id",
                f"sentence uses unknown claim IDs: {', '.join(unknown_claim_ids)}",
                entry,
            )
        )
    if unknown_evidence_ids:
        violations.append(
            _sentence_violation(
                "unknown_evidence_id",
                "sentence uses unknown evidence IDs: "
                f"{', '.join(unknown_evidence_ids)}",
                entry,
            )
        )
    if entry.claim_ids and entry.evidence_ids:
        violations.append(
            _sentence_violation(
                "unsupported_fact_combination",
                "sentence combines product claims and prospect evidence",
                entry,
            )
        )
    if entry.role == "prospect_fact" and not entry.evidence_ids:
        violations.append(
            _sentence_violation(
                "citation_recall",
                "prospect fact requires evidence support",
                entry,
            )
        )
    if entry.role == "product_claim" and not entry.claim_ids:
        violations.append(
            _sentence_violation(
                "citation_recall",
                "product statement requires approved claim support",
                entry,
            )
        )
    if entry.role == "cta" and not entry.claim_ids:
        violations.append(
            _sentence_violation(
                "cta_claim_required",
                "CTA must reference an approved product claim",
                entry,
            )
        )
    if entry.role == "hypothesis" and not _is_uncertain(entry.sentence):
        violations.append(
            _sentence_violation(
                "hypothesis_as_fact",
                "hypothesis must use uncertainty language or a question",
                entry,
            )
        )
    if (
        entry.role == "cta"
        and (entry.cta_kind == "approved_offer" or (verdict and verdict.mentions_offer))
        and not entry.claim_ids
    ):
        violations.append(
            _sentence_violation(
                "unapproved_offer",
                "CTA offer requires an approved claim",
                entry,
            )
        )
    return violations


def _support_verdict_violations(
    output: GroundedOutreachOutput,
    support_verdicts: Mapping[str, SentenceSupportVerdict],
) -> list[HardGateViolation]:
    sentences = {entry.sentence for entry in output.support_map}
    verdict_sentences = set(support_verdicts)
    violations = [
        HardGateViolation(
            code="citation_precision_missing",
            message="every output sentence requires a semantic support verdict",
            sentence=sentence,
        )
        for sentence in sorted(sentences - verdict_sentences)
    ]
    violations.extend(
        HardGateViolation(
            code="unexpected_support_verdict",
            message="semantic verdict does not match an output sentence",
            sentence=sentence,
        )
        for sentence in sorted(verdict_sentences - sentences)
    )
    violations.extend(
        HardGateViolation(
            code="citation_precision_failed",
            message="reviewer found the sentence role or support invalid",
            sentence=sentence,
        )
        for sentence in sorted(sentences & verdict_sentences)
        if not support_verdicts[sentence].approved
    )
    entries = {entry.sentence: entry for entry in output.support_map}
    violations.extend(
        HardGateViolation(
            code="support_verdict_mismatch",
            message="semantic verdict does not match the reviewed role or support IDs",
            sentence=sentence,
        )
        for sentence in sorted(sentences & verdict_sentences)
        if not _verdict_matches(entries[sentence], support_verdicts[sentence])
    )
    return violations


def _semantic_offer_violations(
    output: GroundedOutreachOutput,
    support_verdicts: Mapping[str, SentenceSupportVerdict],
) -> list[HardGateViolation]:
    return [
        _sentence_violation(
            "unapproved_offer",
            "CTA offer requires an approved claim",
            entry,
        )
        for entry in output.support_map
        if entry.role == "cta"
        and not entry.claim_ids
        and (verdict := support_verdicts.get(entry.sentence)) is not None
        and verdict.mentions_offer
    ]


def _verdict_matches(
    entry: SupportMapEntry, verdict: SentenceSupportVerdict
) -> bool:
    return (
        verdict.role == entry.role
        and verdict.claim_ids == entry.claim_ids
        and verdict.evidence_ids == entry.evidence_ids
        and verdict.cta_kind == entry.cta_kind
    )


def _sentence_violation(
    code: str, message: str, entry: SupportMapEntry
) -> HardGateViolation:
    return HardGateViolation(code=code, message=message, sentence=entry.sentence)


def _is_uncertain(sentence: str) -> bool:
    words = {word.casefold() for word in re.findall(r"[A-Za-z]+", sentence)}
    return sentence.rstrip().endswith("?") or bool(
        words.intersection(_UNCERTAINTY_MARKERS)
    )


def _word_count(value: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", value, flags=re.UNICODE))
