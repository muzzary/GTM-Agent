from pathlib import Path

from src.evaluation.review_sheet_phase6_dataset_v2 import (
    OUTPUT_PATH,
    build_review_sheet,
    write_review_sheet,
)
from src.schemas.dataset import DatasetCandidateManifestV2


def test_review_sheet_contains_all_rows_and_fifteen_pairs(tmp_path: Path):
    output_path = tmp_path / OUTPUT_PATH.name
    write_review_sheet(output_path=output_path)
    sheet = output_path.read_text(encoding="utf-8")
    manifest = DatasetCandidateManifestV2.model_validate_json(
        Path("configs/phase6/dataset-v2.candidate.json").read_text(encoding="utf-8")
    )

    assert all(
        f"### {example.example_id} | " in sheet for example in manifest.examples
    )
    summary = sheet.split("## train", maxsplit=1)[0]
    assert summary.count(" <-> ") == 15
    assert len(sheet.split()) < 20_000
    assert build_review_sheet().splitlines() == sheet.splitlines()
