import json
import re
from pathlib import Path

from src.schemas.dataset import DatasetManifest
from src.schemas.training import TrainingConfig, TrainingConfigV2

NOTEBOOK_PATH = Path("notebooks/phase6_outreach_adapter.ipynb")
V2_EVALUATION_NOTEBOOK_PATH = Path("notebooks/phase6_v2_evaluation.ipynb")
V2_TRAINING_NOTEBOOK_PATH = Path("notebooks/phase6_outreach_adapter_v2.ipynb")
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


def v2_training_notebook_source() -> str:
    notebook = json.loads(V2_TRAINING_NOTEBOOK_PATH.read_text(encoding="utf-8"))
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

    assert "configs/phase6/training-v2.json" in source
    assert "configs/phase6/training.json" not in source
    assert "configs/phase6/benchmark-v2.json" in source
    assert "TrainingConfigV2" in source
    assert "metadata.adapter_id == config.adapter_id" in source
    assert "metadata.dataset_id == v2_dataset.dataset_id" in source
    assert "metadata.dataset_version == v2_dataset.dataset_version" in source
    assert "Qwen/Qwen3-4B-Instruct-2507" in source
    assert "cdbee75f17c01a7cc42f958dc650907174af0554" in source
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


def test_phase6_v2_training_json_matches_the_training_contract() -> None:
    config = TrainingConfigV2.model_validate_json(
        Path("configs/phase6/training-v2.json").read_text(encoding="utf-8")
    )

    assert config.config_version == "2.0"
    assert config.adapter_id == "gtm-agent-outreach-v2"
    assert config.max_length == 1536
    assert config.epochs == 3
    assert config.learning_rate == 0.0001
    assert config.lora_rank == 16
    assert config.lora_alpha == 32
    assert config.lora_dropout == 0.05
    assert config.target_modules == "all-linear"
    assert config.gradient_accumulation_steps == 8
    assert config.max_steps == 0


def test_phase6_v2_training_notebook_is_scoped_and_masks_assistant_loss() -> None:
    source = v2_training_notebook_source()

    for required in (
        "configs/phase6/dataset-v2.json",
        "configs/phase6/training-v2.json",
        "validate_dataset_v2",
        "render_v2_prompt",
        "training_prompt_input",
        "training_target_json",
        "build_chat_messages",
        "apply_chat_template",
        "labels = input_ids.clone()",
        "labels[:, :prompt_length] = -100",
        "validation_loss",
        '"dataset_id": dataset.dataset_id',
        '"dataset_version": dataset.dataset_version',
        '"adapter-metadata.json"',
    ):
        assert required in source
    assert not re.search(r"(?<!\.)\btokenizer\(", source)
    assert "configs/phase6/pilot.json" not in source
    assert "configs/phase6/training.json" not in source
    assert "cloudflared" not in source.lower()
    assert "ngrok" not in source.lower()


def test_phase6_v2_training_notebook_code_cells_compile() -> None:
    notebook = json.loads(V2_TRAINING_NOTEBOOK_PATH.read_text(encoding="utf-8"))

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(
            line for line in cell["source"] if not line.lstrip().startswith("%")
        )
        compile(source, f"{V2_TRAINING_NOTEBOOK_PATH}:cell-{index}", "exec")
