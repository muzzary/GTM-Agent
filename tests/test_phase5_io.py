from pathlib import Path

import pytest

from src.evaluation.phase1 import load_manifest
from src.evaluation.phase5 import run_baseline
from src.evaluation.phase5_io import (
    BaselineReportIOError,
    load_baseline_report,
    save_baseline_report,
)
from src.schemas.inference import (
    GenerationSettings,
    InferenceResponse,
    ModelIdentity,
    OutreachOutput,
    RuntimeMetadata,
)

MANIFEST_PATH = Path("configs/phase1/benchmark.json")
MODEL = ModelIdentity(model_id="model/test", model_revision="a" * 40)


def test_baseline_report_round_trips_as_canonical_json(tmp_path: Path) -> None:
    manifest = load_manifest(MANIFEST_PATH).model_copy(
        update={"cases": load_manifest(MANIFEST_PATH).cases[:1]}
    )

    def generate(request):
        return InferenceResponse(
            request_id=request.request_id,
            model=MODEL,
            generation=GenerationSettings(max_new_tokens=256, seed=42),
            output=OutreachOutput(
                subject="A subject",
                body="A body.",
                claims_used=[],
                evidence_used=[],
                uncertainty_notes=[],
            ),
            runtime=RuntimeMetadata(
                python_version="3.12",
                torch_version="test",
                transformers_version="test",
                gpu_name="test",
                gpu_memory_mb=1,
                latency_ms=1,
            ),
        )

    report = run_baseline(manifest, MODEL, generate)
    path = tmp_path / "baseline.json"
    save_baseline_report(report, path)

    assert load_baseline_report(path) == report
    assert path.read_bytes() == path.read_bytes()


def test_baseline_report_loader_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(BaselineReportIOError, match="valid JSON"):
        load_baseline_report(path)
