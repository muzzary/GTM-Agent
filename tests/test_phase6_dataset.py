from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.evaluation.phase1 import load_manifest
from src.schemas.dataset import (
    DatasetManifest,
    DatasetSplit,
    GenerationMethod,
    LicenseKind,
    ReviewStatus,
    TrainingExample,
)
from src.training.dataset import DatasetValidationError, validate_dataset

BENCHMARK_PATH = Path("configs/phase1/benchmark.json")
REVIEWED_AT = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def example(
    example_id: str,
    *,
    split: DatasetSplit,
    product_group: str,
    company_group: str,
    prospect_group: str,
    prompt: str = "Write a concise, evidence-aware outreach email.",
    benchmark_case_id: str | None = None,
    reviewer_status: ReviewStatus = ReviewStatus.REVIEWED,
    license_kind: LicenseKind = LicenseKind.SYNTHETIC,
    approved_claim_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
) -> TrainingExample:
    return TrainingExample(
        example_id=example_id,
        split=split,
        product_group=product_group,
        icp_group="regulated_operations",
        company_group=company_group,
        prospect_group=prospect_group,
        product_name="PilotProduct",
        prompt=prompt,
        target_subject="A question about reporting",
        target_body="Could a reviewed workflow reduce recurring manual reporting?",
        approved_claim_ids=approved_claim_ids or ["claim-pilot-supported"],
        personalization_evidence_ids=evidence_ids or ["evidence-pilot-signal"],
        source_kind="synthetic",
        source_reference="phase6-reviewed-pilot",
        license_kind=license_kind,
        license_basis="Reviewed synthetic example authored for this project",
        generation_method=GenerationMethod.HUMAN_AUTHORED,
        reviewer_status=reviewer_status,
        reviewer_reference="reviewer-phase6-01",
        reviewed_at=REVIEWED_AT,
        relevance=4,
        clarity=4,
        differentiation=3,
        credibility=4,
        cta_quality=4,
        brand_fit=4,
        benchmark_case_id=benchmark_case_id,
    )


def manifest(*examples: TrainingExample) -> DatasetManifest:
    return DatasetManifest(
        dataset_id="dataset-phase6-pilot",
        dataset_version="1.0",
        claim_catalog=["claim-pilot-supported"],
        evidence_catalog=["evidence-pilot-signal"],
        examples=list(examples),
    )


def test_reviewed_synthetic_pilot_passes_audit() -> None:
    dataset = manifest(
        example(
            "dataset-example-train01",
            split=DatasetSplit.TRAIN,
            product_group="product-reporting",
            company_group="company-alpha",
            prospect_group="prospect-alpha",
        ),
        example(
            "dataset-example-train02",
            split=DatasetSplit.TRAIN,
            product_group="product-reporting",
            company_group="company-beta",
            prospect_group="prospect-beta",
            prompt="Write outreach for distributed reporting teams.",
        ),
        example(
            "dataset-example-valid01",
            split=DatasetSplit.VALIDATION,
            product_group="product-security",
            company_group="company-gamma",
            prospect_group="prospect-gamma",
            prompt="Write outreach for cloud asset inventory teams.",
        ),
        example(
            "dataset-example-held01",
            split=DatasetSplit.HELD_OUT,
            product_group="product-devtools",
            company_group="company-delta",
            prospect_group="prospect-delta",
            prompt="Write outreach for engineering productivity teams.",
        ),
    )

    report = validate_dataset(dataset, load_manifest(BENCHMARK_PATH))

    assert report.passed is True
    assert report.split_counts == {"train": 2, "validation": 1, "held_out": 1}
    assert report.overlap_groups == []
    assert report.errors == []


def test_audit_rejects_duplicate_content_and_identity_overlap() -> None:
    dataset = manifest(
        example(
            "dataset-example-train01",
            split=DatasetSplit.TRAIN,
            product_group="product-reporting",
            company_group="company-alpha",
            prospect_group="prospect-alpha",
        ),
        example(
            "dataset-example-valid01",
            split=DatasetSplit.VALIDATION,
            product_group="product-reporting",
            company_group="company-beta",
            prospect_group="prospect-beta",
        ),
    )

    report = validate_dataset(dataset, load_manifest(BENCHMARK_PATH), strict=False)

    assert report.passed is False
    assert "duplicate content hash" in " ".join(report.errors)
    assert "product:product-reporting" in report.overlap_groups


def test_strict_validation_raises_for_pending_or_unsupported_examples() -> None:
    dataset = manifest(
        example(
            "dataset-example-pending1",
            split=DatasetSplit.TRAIN,
            product_group="product-reporting",
            company_group="company-alpha",
            prospect_group="prospect-alpha",
            reviewer_status=ReviewStatus.PENDING,
        ),
        example(
            "dataset-example-case01",
            split=DatasetSplit.TRAIN,
            product_group="product-security",
            company_group="company-beta",
            prospect_group="prospect-beta",
            benchmark_case_id="case-reporting-regulated",
                approved_claim_ids=["claim-not-approved"],
        ),
    )

    with pytest.raises(DatasetValidationError, match="reviewed|benchmark|claim"):
        validate_dataset(dataset, load_manifest(BENCHMARK_PATH))
