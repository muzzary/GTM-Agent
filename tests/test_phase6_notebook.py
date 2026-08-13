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


def test_phase6_v2_notebooks_guard_against_stale_imports() -> None:
    pinned_versions = {
        "transformers": "5.14.1",
        "accelerate": "1.14.0",
        "bitsandbytes": "0.50.0",
        "peft": "0.20.0",
        "safetensors": "0.8.0",
    }

    for source in (
        v2_training_notebook_source(),
        v2_evaluation_notebook_source(),
    ):
        assert "PINNED_VERSIONS" in source
        for package, version in pinned_versions.items():
            assert f'"{package}": "{version}"' in source
        assert "importlib.metadata.version" in source
        assert "__version__" in source
        assert "raise RuntimeError" in source
        assert "Runtime > Restart session, then run all cells top to bottom." in source
        assert "Do not re-run the install cell in a live session." in source


def test_phase6_v2_notebooks_warn_before_install() -> None:
    warning = (
        "After any interrupted run, restart the runtime before re-running this "
        "notebook. Re-running %pip install in a live session produces exactly "
        "this stale-import failure."
    )

    for path in (V2_TRAINING_NOTEBOOK_PATH, V2_EVALUATION_NOTEBOOK_PATH):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        assert notebook["cells"][0]["cell_type"] == "markdown"
        assert warning in "".join(notebook["cells"][0]["source"])


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
    assert config.epochs == 8
    assert config.learning_rate == 0.0001
    assert config.lora_rank == 16
    assert config.lora_alpha == 32
    assert config.lora_dropout == 0.05
    assert config.target_modules == "all-linear"
    assert config.gradient_accumulation_steps == 4
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
        "emitted_status_counts",
        "outputs_with_support_map",
        "parsed_ok",
        "status_match",
        "model.gradient_checkpointing_disable()",
        "model.gradient_checkpointing_enable()",
        "model.config.use_cache = True",
        "model.config.use_cache = False",
        "add_generation_prompt=True",
        "labels = input_ids.clone()",
        "labels[:, :prompt_length] = -100",
        "validation_loss",
        '"dataset_id": dataset.dataset_id',
        '"dataset_version": dataset.dataset_version',
        '"adapter-metadata.json"',
        "run-",
        "exist_ok=False",
        "run-info.json",
        "checkpoints",
        "epochs_completed",
        '"adapter-metadata.json").write_text',
        "shutil.rmtree",
        "relative_to(destination)",
    ):
        assert required in source
    assert not re.search(r"(?<!\.)\btokenizer\(", source)
    assert "configs/phase6/pilot.json" not in source
    assert "configs/phase6/training.json" not in source
    assert "cloudflared" not in source.lower()
    assert "ngrok" not in source.lower()


def test_phase6_v2_training_notebook_marks_and_retains_checkpoints() -> None:
    source = v2_training_notebook_source()

    save_position = source.index("model.save_pretrained(destination")
    metadata_position = source.index('"adapter-metadata.json").write_text')
    cleanup_position = source.index("shutil.rmtree")
    assert save_position < metadata_position < cleanup_position
    assert "checkpoint_dirs[:-2]" in source
    assert 'CHECKPOINTS_DIR / f"epoch-{epoch + 1:02d}"' in source


def test_phase6_v2_evaluation_notebook_resolves_run_and_checkpoint_adapter() -> None:
    source = v2_evaluation_notebook_source()

    assert "RUN_DIR_NAME = None" in source
    assert "BASE_REPORT_PATH = None" in source
    assert 'checkpoints_dir.glob("epoch-*")' in source
    assert "adapter-metadata.json" in source
    assert "epochs_completed" in source
    assert "evaluation" in source


def test_phase6_v2_evaluation_notebook_reuses_base_report_fail_closed() -> None:
    source = v2_evaluation_notebook_source()

    for required in (
        "Phase6V2EvaluationReport.model_validate_json",
        "base_report.benchmark_id == v2_benchmark.benchmark_id",
        "base_report.benchmark_manifest_sha256 == v2_benchmark.content_sha256",
        "base_report.generation == GENERATION_SETTINGS",
        "base_report.model.model_id == BASE_IDENTITY.model_id",
        "base_report.model.model_revision == BASE_IDENTITY.model_revision",
        "base_report.model.adapter_id is None",
        "base_report.model.adapter_revision is None",
        "[case.case_id for case in base_report.cases] == [",
        "base_report.total_cases == len(v2_benchmark.cases)",
        "reused base report benchmark identity mismatch",
        "reused base report generation settings mismatch",
        "reused base report model identity mismatch",
        "reused base report case IDs mismatch",
        "reused base report total_cases mismatch",
        '"base_report_mode": "regenerated"',
        '"base_report_mode": "reused"',
        '"base_report_source": str(base_report_source)',
        "BASE_REPORT_DESTINATION.write_text",
    ):
        assert required in source

    for required in (
        "metadata.adapter_id == config.adapter_id",
        "metadata.dataset_id == v2_dataset.dataset_id",
        "metadata.dataset_version == v2_dataset.dataset_version",
        "metadata.base_model_id == config.base_model_id",
        "metadata.base_model_revision == config.base_model_revision",
        "if has_completed_adapter(adapter_dir)",
        "return checkpoint_dirs[0] if checkpoint_dirs else None",
    ):
        assert required in source


def test_phase6_v2_training_notebook_code_cells_compile() -> None:
    notebook = json.loads(V2_TRAINING_NOTEBOOK_PATH.read_text(encoding="utf-8"))

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(
            line for line in cell["source"] if not line.lstrip().startswith("%")
        )
        compile(source, f"{V2_TRAINING_NOTEBOOK_PATH}:cell-{index}", "exec")
