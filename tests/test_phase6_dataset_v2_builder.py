# ruff: noqa: E501

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from src.evaluation.build_phase6_dataset_v2 import (
    COMPANIES,
    OUTPUT_PATH,
    _normalized_sentence,
    build_candidate_manifest,
)
from src.schemas.dataset import DatasetCandidateManifestV2

BENCHMARK_PATH = Path("configs/phase6/benchmark-v2.json")
EXPECTED = {
    "train": {
        "drafted": 40,
        "needs_more_evidence": 24,
        "disqualified": 18,
        "opted_out": 18,
    },
    "validation": {
        "drafted": 10,
        "needs_more_evidence": 6,
        "disqualified": 4,
        "opted_out": 4,
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
    if evidence[0].collected_at.year < 2026:
        return "stale"
    if any(marker in text for marker in ("while", "disagree", "different", "conflict")):
        return "conflicting"
    if any(
        marker in text
        for marker in ("assistance", "support for", "exposure", "light involvement")
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


def test_gate_and_content_quality_thresholds():
    rows = _manifest().examples
    assert all(row.gate_report.passed for row in rows)
    assert len({row.content_sha256 for row in rows}) == len(rows)
    outputs = [row.proposed_output for row in rows]
    drafted = [output for output in outputs if output.generation_status == "drafted"]
    abstentions = [
        output for output in outputs if output.generation_status != "drafted"
    ]
    assert len(drafted) == 50
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
