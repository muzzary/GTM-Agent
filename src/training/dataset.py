import json
from collections import Counter, defaultdict

from src.evaluation.phase6_v2 import training_prompt_input
from src.schemas.benchmark import BenchmarkManifest
from src.schemas.dataset import (
    DatasetAuditReport,
    DatasetAuditReportV2,
    DatasetManifest,
    DatasetManifestV2,
    DatasetSplit,
    ReviewStatus,
)
from src.schemas.quality_benchmark import GenerationStatus, Phase6BenchmarkManifest


class DatasetValidationError(ValueError):
    """Raised when a dataset fails a strict Phase 6 audit."""

    def __init__(self, report: DatasetAuditReport) -> None:
        self.report = report
        super().__init__("dataset validation failed: " + "; ".join(report.errors))


def validate_dataset(
    dataset: DatasetManifest,
    benchmark: BenchmarkManifest,
    *,
    strict: bool = True,
) -> DatasetAuditReport:
    errors: list[str] = []
    ids = [example.example_id for example in dataset.examples]
    duplicate_example_ids = sorted(
        identifier for identifier in set(ids) if ids.count(identifier) > 1
    )
    if duplicate_example_ids:
        errors.append("duplicate example IDs")

    hashes = [example.content_sha256 for example in dataset.examples]
    duplicate_content_hashes = sorted(
        digest for digest in set(hashes) if hashes.count(digest) > 1
    )
    if duplicate_content_hashes:
        errors.append("duplicate content hash")

    split_counts = {split.value: 0 for split in DatasetSplit}
    groups: dict[str, set[str]] = defaultdict(set)
    for example in dataset.examples:
        split_counts[example.split.value] += 1
        groups[f"product:{example.product_group}"].add(example.split.value)
        groups[f"company:{example.company_group}"].add(example.split.value)
        groups[f"prospect:{example.prospect_group}"].add(example.split.value)
        if not set(example.approved_claim_ids) <= set(dataset.claim_catalog):
            errors.append(f"unsupported claim in {example.example_id}")
        if not set(example.personalization_evidence_ids) <= set(
            dataset.evidence_catalog
        ):
            errors.append(f"unsupported evidence in {example.example_id}")
        if (
            example.split is DatasetSplit.TRAIN
            and example.reviewer_status.value != "reviewed"
        ):
            errors.append(f"unreviewed training example {example.example_id}")

    overlap_groups = sorted(
        group for group, splits in groups.items() if len(splits) > 1
    )
    if overlap_groups:
        errors.append("identity group crosses dataset splits")

    benchmark_ids = {case.case_id for case in benchmark.cases}
    benchmark_overlap = sorted(
        example.example_id
        for example in dataset.examples
        if example.benchmark_case_id in benchmark_ids
        and example.split is not DatasetSplit.HELD_OUT
    )
    if benchmark_overlap:
        errors.append("benchmark case overlaps training or validation data")

    report = DatasetAuditReport(
        dataset_id=dataset.dataset_id,
        passed=not errors,
        split_counts=split_counts,
        overlap_groups=overlap_groups,
        duplicate_example_ids=duplicate_example_ids,
        duplicate_content_hashes=duplicate_content_hashes,
        unsupported_claim_ids=sorted(
            {
                claim_id
                for example in dataset.examples
                for claim_id in example.approved_claim_ids
                if claim_id not in dataset.claim_catalog
            }
        ),
        unsupported_evidence_ids=sorted(
            {
                evidence_id
                for example in dataset.examples
                for evidence_id in example.personalization_evidence_ids
                if evidence_id not in dataset.evidence_catalog
            }
        ),
        benchmark_overlap=benchmark_overlap,
        errors=errors,
    )
    if strict and not report.passed:
        raise DatasetValidationError(report)
    return report


def validate_dataset_v2(
    dataset: DatasetManifestV2,
    benchmark: Phase6BenchmarkManifest,
    *,
    strict: bool = True,
) -> DatasetAuditReportV2:
    errors: list[str] = []
    examples = dataset.examples
    example_ids = [example.example_id for example in examples]
    duplicate_example_ids = _duplicates(example_ids)
    if duplicate_example_ids:
        errors.append("duplicate example IDs")

    content_hashes = [example.content_sha256 or "" for example in examples]
    duplicate_content_hashes = _duplicates(content_hashes)
    if duplicate_content_hashes:
        errors.append("duplicate content hash")

    split_counts = {split.value: 0 for split in DatasetSplit}
    status_counts = {
        split.value: {status: 0 for status in _generation_status_values()}
        for split in DatasetSplit
    }
    groups: dict[str, set[str]] = defaultdict(set)
    unsupported_claim_ids: set[str] = set()
    unsupported_evidence_ids: set[str] = set()
    for example in examples:
        split_counts[example.split.value] += 1
        status_counts[example.split.value][
            example.approved_output.generation_status
        ] += 1
        groups[f"product:{example.identity_groups.product_group}"].add(
            example.split.value
        )
        groups[f"company:{example.identity_groups.company_group}"].add(
            example.split.value
        )
        groups[f"prospect:{example.identity_groups.prospect_group}"].add(
            example.split.value
        )
        input_claim_ids = {
            claim.claim_id for claim in example.input.approved_claims
        }
        input_evidence_ids = {
            evidence.evidence_id for evidence in example.input.prospect_evidence
        }
        used_claim_ids = {
            claim_id
            for item in example.approved_output.support_map
            for claim_id in item.claim_ids
        }
        used_evidence_ids = {
            evidence_id
            for item in example.approved_output.support_map
            for evidence_id in item.evidence_ids
        }
        unsupported_claim_ids.update(used_claim_ids - input_claim_ids)
        unsupported_evidence_ids.update(used_evidence_ids - input_evidence_ids)
        if used_claim_ids - input_claim_ids:
            errors.append(f"unsupported claim in {example.example_id}")
        if used_evidence_ids - input_evidence_ids:
            errors.append(f"unsupported evidence in {example.example_id}")
        if example.split is DatasetSplit.TRAIN and (
            example.review.status is not ReviewStatus.REVIEWED
        ):
            errors.append(f"unreviewed training example {example.example_id}")

    overlap_groups = sorted(
        group for group, splits in groups.items() if len(splits) > 1
    )
    if overlap_groups:
        errors.append("identity group crosses dataset splits")

    benchmark_groups = {
        f"{kind}:{getattr(case.identity_groups, f'{kind}_group')}"
        for case in benchmark.cases
        for kind in ("product", "company", "prospect")
    }
    dataset_groups = set(groups)
    benchmark_identity_overlap = sorted(dataset_groups & benchmark_groups)
    if benchmark_identity_overlap:
        errors.append("dataset identity overlaps frozen benchmark")

    benchmark_hashes = {
        case.content_sha256 for case in benchmark.cases if case.content_sha256
    }
    benchmark_prompt_contents = {
        _canonical_json(case.prompt_input().model_dump(mode="json"))
        for case in benchmark.cases
    }
    benchmark_content_overlap = sorted(
        example.example_id
        for example in examples
        if example.content_sha256 in benchmark_hashes
        or _canonical_json(training_prompt_input(example).model_dump(mode="json"))
        in benchmark_prompt_contents
    )
    if benchmark_content_overlap:
        errors.append("training prompt content overlaps benchmark case")

    report = DatasetAuditReportV2(
        dataset_id=dataset.dataset_id,
        passed=not errors,
        split_counts=split_counts,
        status_counts=status_counts,
        overlap_groups=overlap_groups,
        duplicate_example_ids=duplicate_example_ids,
        duplicate_content_hashes=duplicate_content_hashes,
        unsupported_claim_ids=sorted(unsupported_claim_ids),
        unsupported_evidence_ids=sorted(unsupported_evidence_ids),
        benchmark_identity_overlap=benchmark_identity_overlap,
        benchmark_content_overlap=benchmark_content_overlap,
        errors=errors,
    )
    if strict and not report.passed:
        raise DatasetValidationError(report)
    return report


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _generation_status_values() -> tuple[str, ...]:
    return tuple(GenerationStatus.__args__)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
