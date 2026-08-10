import json
from pathlib import Path

from src.schemas.dataset import DatasetManifest
from src.schemas.training import TrainingConfig

NOTEBOOK_PATH = Path("notebooks/phase6_outreach_adapter.ipynb")
V2_EVALUATION_NOTEBOOK_PATH = Path("notebooks/phase6_v2_evaluation.ipynb")
PILOT_PATH = Path("configs/phase6/pilot.json")


def notebook_source() -> str:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert all(cell.get("outputs", []) == [] for cell in notebook["cells"])
    assert all(cell.get("execution_count") is None for cell in notebook["cells"])
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )


def v2_evaluation_notebook_source() -> str:
    notebook = json.loads(V2_EVALUATION_NOTEBOOK_PATH.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert all(cell.get("outputs", []) == [] for cell in notebook["cells"])
    assert all(cell.get("execution_count") is None for cell in notebook["cells"])
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )


def test_phase6_notebook_is_clean_and_validates_before_training() -> None:
    source = notebook_source()

    assert "validate_dataset" in source
    assert "TrainingConfig" in source
    assert "split_counts[\"train\"]" in source
    assert "held_out" in source
    assert "get_peft_model" in source
    assert "PeftModel.from_pretrained" in source
    assert "run_baseline" in source
    assert "compare_baseline_reports" in source
    assert "base-report.json" in source
    assert "adapter-report.json" in source
    assert "comparison.json" in source
    assert "save_pretrained" in source
    assert "adapter-metadata.json" in source
    assert "cloudflared" not in source.lower()
    assert "ngrok" not in source.lower()


def test_phase6_notebook_code_cells_compile_after_colab_magics() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(
            line for line in cell["source"] if not line.lstrip().startswith("%")
        )
        compile(source, f"{NOTEBOOK_PATH}:cell-{index}", "exec")


def test_phase6_v2_evaluation_notebook_is_clean_and_scoped() -> None:
    source = v2_evaluation_notebook_source()

    assert "benchmark-v2.json" in source
    assert "audit_phase6_benchmark" in source
    assert "run_phase6_v2_evaluation" in source
    assert "phase6-v2-base-report.json" in source
    assert "phase6-v2-adapter-report.json" in source
    assert "phase6-v2-comparison.json" in source
    assert "get_peft_model" not in source
    assert "optimizer" not in source
    assert "backward" not in source
    assert "cloudflared" not in source.lower()
    assert "ngrok" not in source.lower()


def test_phase6_v2_evaluation_notebook_code_cells_compile() -> None:
    notebook = json.loads(
        V2_EVALUATION_NOTEBOOK_PATH.read_text(encoding="utf-8")
    )

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(
            line for line in cell["source"] if not line.lstrip().startswith("%")
        )
        compile(source, f"{V2_EVALUATION_NOTEBOOK_PATH}:cell-{index}", "exec")


def test_phase6_pilot_json_matches_the_dataset_contract() -> None:
    dataset = DatasetManifest.model_validate(
        json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    )

    assert dataset.dataset_id == "dataset-phase6-pilot"
    assert len(dataset.examples) == 6


def test_phase6_training_json_matches_the_training_contract() -> None:
    config = TrainingConfig.model_validate(
        json.loads(Path("configs/phase6/training.json").read_text(encoding="utf-8"))
    )

    assert config.adapter_id == "gtm-agent-outreach-pilot"
