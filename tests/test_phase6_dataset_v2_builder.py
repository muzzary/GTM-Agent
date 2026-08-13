# ruff: noqa: E501

import json
import re
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

import pytest

from src.evaluation.build_phase6_dataset_v2 import (
    COMPANIES,
    OUTPUT_PATH,
    OUTPUT_REVIEWED_PATH,
    REFERENCE_DATE,
    _assert_conflicting_attribute,
    _normalized_sentence,
    apply_review,
    build_candidate_manifest,
)
from src.evaluation.phase6_benchmark import load_phase6_benchmark
from src.schemas.dataset import DatasetCandidateManifestV2, DatasetManifestV2
from src.training.dataset import validate_dataset_v2

BENCHMARK_PATH = Path("configs/phase6/benchmark-v2.json")
EXPECTED = {
    "train": {
        "drafted": 65,
        "needs_more_evidence": 15,
        "disqualified": 10,
        "opted_out": 10,
    },
    "validation": {
        "drafted": 15,
        "needs_more_evidence": 4,
        "disqualified": 3,
        "opted_out": 2,
    },
}
ROLE_TIERS = {
    "Insights Analyst": "individual_contributor",
    "Reporting Manager": "manager",
    "Director of Business Intelligence": "director",
    "VP of Analytics": "vp",
    "Chief Data Officer": "c_level",
    "Cloud Security Specialist": "individual_contributor",
    "Security Operations Manager": "manager",
    "Director of Security Architecture": "director",
    "VP of Cybersecurity": "vp",
    "Chief Security Officer": "c_level",
    "Developer Productivity Engineer": "individual_contributor",
    "Engineering Productivity Manager": "manager",
    "Director of Developer Infrastructure": "director",
    "VP of Platform Engineering": "vp",
    "Chief Engineering Officer": "c_level",
    "Knowledge Operations Specialist": "individual_contributor",
    "Support Enablement Manager": "manager",
    "Director of Customer Education": "director",
    "VP of Support Experience": "vp",
    "Chief Customer Experience Officer": "c_level",
    "Revenue Systems Analyst": "individual_contributor",
    "Revenue Systems Manager": "manager",
    "Director of Commercial Operations": "director",
    "VP of Revenue Systems": "vp",
    "Chief Commercial Officer": "c_level",
}


def _manifest():
    return DatasetCandidateManifestV2.model_validate_json(
        OUTPUT_PATH.read_text(encoding="utf-8")
    )


def _condition(row):
    evidence = row.input.prospect_evidence
    if not evidence:
        return "absent"
    text = evidence[0].text.casefold()
    if any(REFERENCE_DATE - item.collected_at >= timedelta(days=365) for item in evidence):
        return "stale"
    if any(marker in text for marker in ("while", "but a later", "disagree", "different", "conflict")):
        return "conflicting"
    if any(
        marker in text
        for marker in ("assistance", "assisting", "assist", "support for", "exposure", "light involvement")
    ):
        return "weak"
    return "strong"


def test_builder_is_deterministic_and_committed_artifact_matches():
    first = build_candidate_manifest()
    second = build_candidate_manifest()
    assert first.model_dump_json() == second.model_dump_json()
    assert first.model_dump_json() == _manifest().model_dump_json()


def test_exact_distribution_and_coverage():
    manifest = _manifest()
    distribution = {
        split: Counter(
            row.proposed_output.generation_status
            for row in manifest.examples
            if row.intended_split == split
        )
        for split in EXPECTED
    }
    assert {split: dict(counts) for split, counts in distribution.items()} == EXPECTED
    assert {row.product_name for row in manifest.examples} == {
        "MetricMosaic",
        "CloudLedger",
        "LoopSignal",
        "GuideCurrent",
        "RecordBeacon",
    }
    assert {_condition(row) for row in manifest.examples} == {
        "strong",
        "weak",
        "conflicting",
        "stale",
        "absent",
    }
    assert {ROLE_TIERS[row.input.target_role] for row in manifest.examples} == {
        "individual_contributor",
        "manager",
        "director",
        "vp",
        "c_level",
    }
    assert {row.scenario_kind for row in manifest.examples} == {
        "initial_outreach",
        "follow_up",
    }


def test_evidence_count_buckets_match_overall_status_shape():
    rows = _manifest().examples
    statuses = tuple(EXPECTED["train"])
    buckets = {
        count: Counter(
            row.proposed_output.generation_status
            for row in rows
            if len(row.input.prospect_evidence) == count
        )
        for count in range(4)
    }
    table = {count: dict(bucket) for count, bucket in buckets.items()}
    overall = Counter(row.proposed_output.generation_status for row in rows)
    overall_drafted_share = overall["drafted"] / len(rows)

    assert set(buckets[0]) == {"needs_more_evidence"}, table
    for count in (1, 2, 3):
        assert set(buckets[count]) == set(statuses), table
        drafted_share = buckets[count]["drafted"] / sum(buckets[count].values())
        assert abs(drafted_share - overall_drafted_share) <= 0.15, table
    assert buckets[1]["drafted"] / overall["drafted"] >= 0.60, table
    assert all(buckets[count][status] for count in (2, 3) for status in ("disqualified", "opted_out")), table


def test_gate_and_content_quality_thresholds():
    rows = _manifest().examples
    assert all(row.gate_report.passed for row in rows)
    assert len({row.content_sha256 for row in rows}) == len(rows)
    outputs = [row.proposed_output for row in rows]
    drafted = [output for output in outputs if output.generation_status == "drafted"]
    abstentions = [
        output for output in outputs if output.generation_status != "drafted"
    ]
    assert len(drafted) == 80
    assert all(
        not any(character.isdigit() for character in output.subject)
        for output in outputs
    )
    assert all(
        not any(
            character.isdigit()
            for note in output.uncertainty_notes
            for character in note
        )
        for output in outputs
    )
    forbidden = re.compile(
        r"(?i)\b(row|case|example|candidate)\s*\d|\bcandidate company\b"
    )
    assert not forbidden.search(
        json.dumps([output.model_dump(mode="json") for output in outputs])
    )
    for row in rows:
        evidence = {item.evidence_id: item.text for item in row.input.prospect_evidence}
        evidence_refs = [
            evidence_id
            for entry in row.proposed_output.support_map
            for evidence_id in entry.evidence_ids
        ]
        claim_refs = [
            claim_id
            for entry in row.proposed_output.support_map
            for claim_id in entry.claim_ids
        ]
        assert len(evidence_refs) == len(set(evidence_refs))
        assert all(claim_refs.count(claim_id) <= 2 for claim_id in set(claim_refs))
        assert all(re.search(r"[.!?]$", item.text) for item in row.input.prospect_evidence)
        for entry in row.proposed_output.support_map:
            cited = " ".join(
                evidence.get(evidence_id, "") for evidence_id in entry.evidence_ids
            )
            assert all(digit in cited for digit in re.findall(r"\d+", entry.sentence))
        if row.proposed_output.generation_status == "drafted":
            assert 1 <= len(row.input.prospect_evidence) <= 3
            assert 3 <= len(row.proposed_output.support_map) <= 6
    normalized_sentences = Counter(
        _normalized_sentence(entry.sentence)
        for output in drafted
        for entry in output.support_map
    )
    assert max(normalized_sentences.values()) <= 4
    ctas = Counter(
        entry.sentence
        for output in drafted
        for entry in output.support_map
        if entry.role == "cta"
    )
    assert len(ctas) >= 20
    assert max(ctas.values()) <= 4
    rationales = Counter(
        _normalized_sentence(note)
        for output in abstentions
        for note in output.uncertainty_notes
    )
    assert len(rationales) >= 30
    assert max(rationales.values()) <= 4
    shapes = Counter(
        tuple(entry.role for entry in output.support_map) for output in drafted
    )
    assert len(shapes) >= 6
    assert max(shapes.values()) <= len(drafted) * 0.4
    body_counts = [len(re.findall(r"\b[\w'-]+\b", output.body)) for output in drafted]
    assert all(40 <= count <= 95 for count in body_counts)
    frame_counts = Counter()
    for row in rows:
        claims_by_id = {claim.claim_id: claim.text for claim in row.input.approved_claims}
        for entry in row.proposed_output.support_map:
            if entry.role == "product_claim":
                frame_counts[entry.sentence.replace(claims_by_id[entry.claim_ids[0]].rstrip("."), "<claim>")] += 1
    assert max(frame_counts.values()) <= 3
    company_prefixed_notes = sum(
        any(note.startswith(f"{company}:") for company in COMPANIES)
        for output in abstentions
        for note in output.uncertainty_notes
    )
    assert company_prefixed_notes <= len(abstentions) * 0.3
    output_text = json.dumps([output.model_dump(mode="json") for output in outputs])
    assert not re.search(r"\b(Crm|Ci)\b", output_text)
    banned_support_phrases = (
        "public evidence",
        "public record",
        "the source",
        "according to",
        "the approved product profile",
        "operating guide",
        "careers page",
        "hiring page",
        "annual report",
        "job post",
        "public materials",
        "team page",
        "operations page",
        "process note",
        "role brief",
        "role details",
        "published workflow",
    )
    for output in outputs:
        for entry in output.support_map:
            lowered = entry.sentence.casefold()
            assert not any(phrase in lowered for phrase in banned_support_phrases)
            assert ":" not in entry.sentence
        for note in output.uncertainty_notes:
            assert not re.match(r"^\s*[A-Za-z][A-Za-z -]*:", note)
    found_companies = {
        name
        for row in rows
        for name in COMPANIES
        if name in json.dumps(row.model_dump(mode="json"))
    }
    assert len(found_companies) >= 40
    assert len({row.input.target_role for row in rows}) >= 20


def test_abstention_conditions_and_rationales_are_bound_to_input():
    rows = _manifest().examples
    for row in rows:
        condition = _condition(row)
        status = row.proposed_output.generation_status
        notes = " ".join(row.proposed_output.uncertainty_notes).casefold()
        if status == "needs_more_evidence":
            assert condition != "strong"
        if status == "drafted":
            continue
        if condition == "absent":
            assert row.input.prospect_evidence == []
            assert any(
                phrase in notes
                for phrase in (
                    "no usable prospect evidence",
                    "no usable evidence",
                    "no evidence",
                    "without usable evidence",
                    "lacks usable evidence",
                    "no prospect evidence",
                    "evidence is absent",
                )
            )
            assert not any(
                marker in notes
                for marker in (
                    "source",
                    "signal",
                    "role",
                    "month",
                    "year",
                    "old",
                    "ownership",
                    "disagree",
                )
            )
        elif condition == "stale":
            assert row.input.prospect_evidence
            assert all(
                REFERENCE_DATE - item.collected_at >= timedelta(days=365)
                for item in row.input.prospect_evidence
            )
            assert any(
                marker in notes
                for marker in ("old", "age", "earlier", "year", "recent", "date")
            )
        elif condition == "conflicting":
            _assert_conflicting_attribute(row.input.prospect_evidence)
            assert len(row.input.prospect_evidence) >= 2
            assert any(
                marker in notes
                for marker in (
                    "disagree",
                    "conflict",
                    "different",
                    "incompatible",
                    "responsib",
                    "agree",
                )
            )
        elif condition == "weak":
            assert row.input.prospect_evidence
            assert any(
                marker in notes
                for marker in ("thin", "indirect", "limited", "hint", "assist", "suggest", "weak")
            )
            assert not any(
                marker in notes for marker in ("old", "year", "disagree", "conflict")
            )
        if status in {"disqualified", "opted_out"}:
            evidence_words = set(
                re.findall(
                    r"[a-z]{5,}",
                    " ".join(item.text.casefold() for item in row.input.prospect_evidence),
                )
            )
            note_words = set(re.findall(r"[a-z]{5,}", notes))
            assert evidence_words & note_words
        duration = re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten|twelve|fourteen|\d+)\s+months?\b",
            notes,
        )
        if duration:
            month_words = {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
                "seven": 7,
                "eight": 8,
                "nine": 9,
                "ten": 10,
                "twelve": 12,
                "fourteen": 14,
            }
            months = month_words.get(duration.group(1), int(duration.group(1))) if duration.group(1).isdigit() else month_words[duration.group(1)]
            assert condition == "stale"
            assert all(
                REFERENCE_DATE - item.collected_at >= timedelta(days=months * 30)
                for item in row.input.prospect_evidence
            )


def test_identity_disjointness_and_split_boundary():
    manifest = _manifest()
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    benchmark_groups = {
        group
        for case in benchmark["cases"]
        for group in case["identity_groups"].values()
    }
    groups = defaultdict(set)
    for row in manifest.examples:
        for group in row.identity_groups.model_dump().values():
            assert group not in benchmark_groups
            groups[group].add(row.intended_split)
    assert all(len(splits) == 1 for splits in groups.values())


def test_fifteen_contrastive_pairs_share_identity_and_split():
    rows = _manifest().examples
    by_identity = defaultdict(list)
    for row in rows:
        by_identity[tuple(row.identity_groups.model_dump().values())].append(row)
    pairs = [group for group in by_identity.values() if len(group) == 2]
    assert len(pairs) == 15
    assert all(pair[0].intended_split == pair[1].intended_split for pair in pairs)
    assert all(
        pair[0].proposed_output.generation_status
        != pair[1].proposed_output.generation_status
        for pair in pairs
    )


def test_apply_review_is_deterministic_and_matches_committed_manifest():
    first = apply_review()
    second = apply_review()
    assert first.model_dump_json() == second.model_dump_json()
    assert first.model_dump_json() == DatasetManifestV2.model_validate_json(
        OUTPUT_REVIEWED_PATH.read_text(encoding="utf-8")
    ).model_dump_json()


def test_reviewed_manifest_validates_against_frozen_benchmark():
    report = validate_dataset_v2(
        apply_review(), load_phase6_benchmark(BENCHMARK_PATH)
    )
    assert report.passed
    assert report.errors == []


def test_reviewed_rows_have_exact_support_verdicts():
    manifest = apply_review()
    for row in manifest.examples:
        assert row.review.status.value == "reviewed"
        assert row.review.hard_gates_passed
        entries = {entry.sentence: entry for entry in row.approved_output.support_map}
        assert set(row.review.support_verdicts) == set(entries)
        for sentence, verdict in row.review.support_verdicts.items():
            entry = entries[sentence]
            assert verdict.role == entry.role
            assert verdict.claim_ids == entry.claim_ids
            assert verdict.evidence_ids == entry.evidence_ids
            assert verdict.cta_kind == entry.cta_kind
            assert verdict.mentions_offer == (entry.cta_kind == "approved_offer")
            assert verdict.approved


def test_apply_review_rejects_candidate_hash_mismatch(tmp_path):
    review = json.loads(Path("configs/phase6/dataset-v2.review.json").read_text())
    review["candidate_manifest_sha256"] = "0" * 64
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate manifest hash"):
        apply_review(review_path=review_path, output_path=tmp_path / "out.json")


@pytest.mark.parametrize("mutation", ["missing", "unapproved"])
def test_apply_review_rejects_missing_or_unapproved_row(tmp_path, mutation):
    review = json.loads(Path("configs/phase6/dataset-v2.review.json").read_text())
    if mutation == "missing":
        review["entries"].pop()
    else:
        review["entries"][0]["approved"] = False
    review_path = tmp_path / f"{mutation}.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError, match="review entry|approved"):
        apply_review(review_path=review_path, output_path=tmp_path / "out.json")
