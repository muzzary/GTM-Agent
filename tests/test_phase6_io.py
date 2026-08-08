import json
from pathlib import Path

import pytest

from src.evaluation.phase6 import compare_baseline_reports
from src.evaluation.phase6_io import (
    Phase6ReportIOError,
    load_adapter_metadata,
    load_comparison_report,
    save_comparison_report,
)
from src.schemas.training import AdapterArtifactMetadata
from tests.test_phase6_comparison import reports


def test_comparison_report_round_trips_and_excludes_computed_acceptance(
    tmp_path: Path,
) -> None:
    base, adapter = reports()
    report = compare_baseline_reports(base, adapter, "c" * 64)
    path = tmp_path / "comparison.json"

    save_comparison_report(report, path)

    assert load_comparison_report(path) == report
    assert "accepted" not in json.loads(path.read_text(encoding="utf-8"))


def test_invalid_adapter_metadata_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps({"adapter_id": "unexpected"}), encoding="utf-8")

    with pytest.raises(Phase6ReportIOError, match="metadata"):
        load_adapter_metadata(path)


def test_valid_adapter_metadata_is_strict() -> None:
    metadata = AdapterArtifactMetadata.model_validate(
        {
            "artifact_version": "1.0",
            "adapter_id": "gtm-agent-outreach-pilot",
            "adapter_revision": "b" * 64,
            "base_model_id": "Qwen/Qwen3-4B-Instruct-2507",
            "base_model_revision": "a" * 40,
            "dataset_id": "dataset-phase6-pilot",
            "dataset_version": "1.0",
            "train_examples": 3,
            "trained_steps": 3,
            "created_at": "2026-08-08T18:06:11.671471+00:00",
        }
    )

    assert metadata.trained_steps == 3
