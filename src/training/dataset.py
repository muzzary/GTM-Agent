from collections import defaultdict

from src.schemas.benchmark import BenchmarkManifest
from src.schemas.dataset import DatasetAuditReport, DatasetManifest, DatasetSplit


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
