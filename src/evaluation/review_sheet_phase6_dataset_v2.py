"""Render the Phase 6 candidate dataset as a human-readable review sheet."""

# The sheet format intentionally keeps compact human-readable lines.
# ruff: noqa: E501

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from src.schemas.dataset import DatasetCandidateManifestV2, TrainingExampleCandidateV2

DATASET_PATH = Path("configs/phase6/dataset-v2.candidate.json")
OUTPUT_PATH = Path("results/phase6-dataset-v2-review-sheet.md")
# Ceiling on the reviewer-facing sheet so it stays readable in a couple of passes.
# It is a working-artifact budget, not a data contract: raise it when the dataset
# legitimately grows (the 40->65 drafted rebalance took the sheet past 20k words).
WORD_LIMIT = 30_000

PRODUCT_CATEGORIES = {
    "MetricMosaic": "reporting_automation",
    "CloudLedger": "security_asset_inventory",
    "LoopSignal": "developer_productivity",
    "GuideCurrent": "support_knowledge_workflow",
    "RecordBeacon": "crm_data_hygiene",
}


def _load_dataset(path: Path = DATASET_PATH) -> DatasetCandidateManifestV2:
    return DatasetCandidateManifestV2.model_validate_json(path.read_text(encoding="utf-8"))


def _evidence_condition(row: TrainingExampleCandidateV2) -> str:
    evidence = row.input.prospect_evidence
    if not evidence:
        return "absent"
    if any(item.collected_at.year < 2026 for item in evidence):
        return "stale"
    combined = " ".join(item.text.casefold() for item in evidence)
    if any(marker in combined for marker in ("conflict", "disagree", "different", "both claiming")):
        return "conflicting"
    if any(marker in combined for marker in ("assistance", "support for", "exposure", "light involvement")):
        return "weak"
    return "strong"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _pair_map(rows: list[TrainingExampleCandidateV2]) -> dict[str, str]:
    grouped: dict[tuple[str, ...], list[TrainingExampleCandidateV2]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.identity_groups.model_dump().values())].append(row)
    pairs = [group for group in grouped.values() if len(group) == 2]
    if len(pairs) != 15:
        raise AssertionError(f"expected 15 contrastive pairs, found {len(pairs)}")
    result: dict[str, str] = {}
    for pair in pairs:
        left, right = pair
        result[left.example_id] = right.example_id
        result[right.example_id] = left.example_id
    return result


def _pair_lines(rows: list[TrainingExampleCandidateV2], pair_map: dict[str, str]) -> list[str]:
    by_id = {row.example_id: row for row in rows}
    seen: set[frozenset[str]] = set()
    lines: list[str] = []
    for row in rows:
        other_id = pair_map.get(row.example_id)
        if other_id is None:
            continue
        key = frozenset((row.example_id, other_id))
        if key in seen:
            continue
        seen.add(key)
        other = by_id[other_id]
        lines.append(
            f"{row.example_id} <-> {other.example_id} "
            f"({row.proposed_output.generation_status} vs "
            f"{other.proposed_output.generation_status}, "
            f"flipped signal: {_evidence_condition(row)} -> "
            f"{_evidence_condition(other)})"
        )
    if len(lines) != 15:
        raise AssertionError(f"expected 15 pair lines, found {len(lines)}")
    return lines


def _summary(rows: list[TrainingExampleCandidateV2], pair_map: dict[str, str]) -> list[str]:
    distribution = Counter(
        (row.intended_split, row.proposed_output.generation_status) for row in rows
    )
    drafted_body_counts = [
        _word_count(row.proposed_output.body)
        for row in rows
        if row.proposed_output.generation_status == "drafted"
    ]
    return [
        "# Phase 6 v2 Candidate Dataset Review Sheet",
        "",
        "## Summary",
        "",
        f"- Total rows: {len(rows)}",
        "- Split/status distribution:",
        *(f"  - {split} / {status}: {distribution[(split, status)]}" for split in ("train", "validation") for status in ("drafted", "needs_more_evidence", "disqualified", "opted_out")),
        f"- Body words (drafted rows, min/median/max): {min(drafted_body_counts)} / {median(drafted_body_counts):g} / {max(drafted_body_counts)}",
        "- Contrastive pairs (flipped signal):",
        *[f"  - {line}" for line in _pair_lines(rows, pair_map)],
        "",
    ]


def _row_block(row: TrainingExampleCandidateV2, pair_map: dict[str, str]) -> list[str]:
    output = row.proposed_output
    category = PRODUCT_CATEGORIES.get(row.product_name, "unknown")
    lines = [
        f"### {row.example_id} | {row.intended_split} | {output.generation_status}",
        f"product: {row.product_name} ({category}) | role: {row.input.target_role} | scenario: {row.scenario_kind}",
        f"company: {row.identity_groups.company_group} | evidence condition: {_evidence_condition(row)} | pair: {pair_map.get(row.example_id, '-')}",
        "claims offered:",
    ]
    lines.extend(
        f"- {claim.claim_id}: {_truncate(claim.text, 40)}"
        for claim in row.input.approved_claims
    )
    lines.append("evidence offered:")
    for evidence in row.input.prospect_evidence:
        collected_at = evidence.collected_at.isoformat()
        lines.append(
            f"- {evidence.evidence_id}: {_truncate(evidence.text, 50)} "
            f"[{collected_at}]"
        )
    if not row.input.prospect_evidence:
        lines.append("- (none)")
    lines.extend(
        [
            "--- proposed output ---",
            f"subject: {output.subject or '(none)'}",
            f"body: {output.body or '(none)'}",
            "support:",
        ]
    )
    if output.support_map:
        lines.extend(
            "- "
            + " | ".join(
                (
                    entry.role,
                    entry.cta_kind or "-",
                    ",".join(entry.claim_ids) or "-",
                    ",".join(entry.evidence_ids) or "-",
                    _truncate(entry.sentence, 40),
                )
            )
            for entry in output.support_map
        )
    else:
        lines.append("- (none)")
    notes = "; ".join(output.uncertainty_notes) if output.uncertainty_notes else "(none)"
    lines.extend([f"notes: {notes}", ""])
    return lines


def build_review_sheet(path: Path = DATASET_PATH) -> str:
    manifest = _load_dataset(path)
    rows = manifest.examples
    pair_map = _pair_map(rows)
    lines = _summary(rows, pair_map)
    for split in ("train", "validation"):
        lines.extend([f"## {split}", ""])
        for status in ("drafted", "needs_more_evidence", "disqualified", "opted_out"):
            lines.extend([f"### Status: {status}", ""])
            matching = [
                row
                for row in rows
                if row.intended_split == split
                and row.proposed_output.generation_status == status
            ]
            for row in matching:
                lines.extend(_row_block(row, pair_map))
    sheet = "\n".join(lines).rstrip() + "\n"
    word_count = len(sheet.split())
    if word_count > WORD_LIMIT:
        raise AssertionError(f"review sheet exceeds {WORD_LIMIT} words: {word_count}")
    return sheet


def write_review_sheet(
    dataset_path: Path = DATASET_PATH, output_path: Path = OUTPUT_PATH
) -> None:
    sheet = build_review_sheet(dataset_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sheet, encoding="utf-8")


if __name__ == "__main__":
    write_review_sheet()
