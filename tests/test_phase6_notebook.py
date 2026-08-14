import json
import re
from pathlib import Path

from src.schemas.dataset import DatasetManifest
from src.schemas.training import TrainingConfig, TrainingConfigV2

NOTEBOOK_PATH = Path("notebooks/phase6_outreach_adapter.ipynb")
V2_EVALUATION_NOTEBOOK_PATH = Path("notebooks/phase6_v2_evaluation.ipynb")
KAGGLE_V2_EVALUATION_NOTEBOOK_PATH = Path(
    "notebooks/phase6_v2_evaluation_kaggle.ipynb"
)
KAGGLE_V2_TRAINING_NOTEBOOK_PATH = Path(
    "notebooks/phase6_outreach_adapter_v2_kaggle.ipynb"
)
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


def kaggle_v2_evaluation_notebook_source() -> str:
    notebook = json.loads(
        KAGGLE_V2_EVALUATION_NOTEBOOK_PATH.read_text(encoding="utf-8")
    )
    assert notebook["nbformat"] == 4
    assert all(cell.get("outputs", []) == [] for cell in notebook["cells"])
    assert all(cell.get("execution_count") is None for cell in notebook["cells"])
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )


def kaggle_v2_training_notebook_source() -> str:
    notebook = json.loads(
        KAGGLE_V2_TRAINING_NOTEBOOK_PATH.read_text(encoding="utf-8")
    )
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


def test_phase6_v2_kaggle_evaluation_notebook_matches_kaggle_contract() -> None:
    source = kaggle_v2_evaluation_notebook_source()

    for required in (
        'ADAPTER_DIR_OVERRIDE = None',
        'BASE_REPORT_PATH_OVERRIDE = None',
        'Path("/kaggle/input")',
        'KAGGLE_WORKING_ROOT = Path("/kaggle/working")',
        'EVALUATION_DIR = KAGGLE_WORKING_ROOT / "evaluation"',
        "adapter-metadata.json",
        "phase6-v2-base-report.json",
        "Ambiguous adapter discovery",
        "No adapter metadata found",
        "Ambiguous base report discovery",
        "No base report found",
        "base_report.benchmark_id == v2_benchmark.benchmark_id",
        "base_report.benchmark_manifest_sha256 == v2_benchmark.content_sha256",
        "base_report.generation == GENERATION_SETTINGS",
        "base_report.model.model_id == BASE_IDENTITY.model_id",
        "base_report.model.model_revision == BASE_IDENTITY.model_revision",
        "base_report.model.adapter_id is None",
        "base_report.model.adapter_revision is None",
        "[case.case_id for case in base_report.cases] == [",
        "base_report.total_cases == len(v2_benchmark.cases)",
        "metadata.adapter_id == config.adapter_id",
        "metadata.dataset_id == v2_dataset.dataset_id",
        "metadata.dataset_version == v2_dataset.dataset_version",
        "metadata.base_model_id == config.base_model_id",
        "metadata.base_model_revision == config.base_model_revision",
        "importlib.metadata.version",
        "PeftModel.from_pretrained",
        "epochs_completed",
        "phase6-v2-adapter-report.json",
        "phase6-v2-comparison.json",
    ):
        assert required in source

    assert "google.colab" not in source
    assert "drive.mount" not in source
    assert "/content/drive" not in source


def test_phase6_v2_kaggle_notebook_starts_with_standard_library_preflight() -> None:
    notebook = json.loads(
        KAGGLE_V2_EVALUATION_NOTEBOOK_PATH.read_text(encoding="utf-8")
    )
    first_code_index = next(
        index for index, cell in enumerate(notebook["cells"])
        if cell["cell_type"] == "code"
    )
    first_code = notebook["cells"][first_code_index]
    preflight = "".join(first_code["source"])
    assert first_code_index > 0
    assert notebook["cells"][first_code_index - 1]["cell_type"] == "markdown"

    for required in (
        "/kaggle/input",
        "adapter-metadata.json",
        "phase6-v2-base-report.json",
        "socket.create_connection",
        "pypi.org",
        "/proc/driver/nvidia/version",
        "nvidia-smi",
        '"--query-gpu=name,compute_cap"',
        "compute_cap",
        "4-bit training requires 7.0+",
        "Tesla P100",
        "Tesla P40",
        "Tesla P4",
        "GTX 10",
        "GPU capability could not be determined",
        "GPU '{gpu_name}' has CUDA capability {gpu_compute_cap:.1f};",
        "Set Accelerator to 'GPU T4 x2' in the notebook sidebar",
        "(Kaggle also offers P100, which will not work).",
        "ADAPTER_DIR_OVERRIDE",
        "BASE_REPORT_PATH_OVERRIDE",
        "failures = []",
        "+ Add Input in the notebook sidebar",
        "enable Internet in the notebook sidebar",
        "phone verification at kaggle.com/settings",
        "set Accelerator to GPU T4 x2 in the sidebar",
        "will cost roughly double the GPU time",
        "Preflight passed:",
        "compute capability",
    ):
        assert required in preflight

    assert "import torch" not in preflight
    assert "import transformers" not in preflight
    assert "import peft" not in preflight
    assert "from src" not in preflight
    assert "raise RuntimeError" in preflight
    assert "failures.append" in preflight

    markdown_before_preflight = "".join(
        notebook["cells"][first_code_index - 1]["source"]
    )
    assert "Run All" in markdown_before_preflight
    assert "Save & Run All" in markdown_before_preflight


def test_phase6_v2_kaggle_evaluation_shares_fail_closed_discovery_helpers() -> None:
    notebook = json.loads(
        KAGGLE_V2_EVALUATION_NOTEBOOK_PATH.read_text(encoding="utf-8")
    )
    first_code_index = next(
        index for index, cell in enumerate(notebook["cells"])
        if cell["cell_type"] == "code"
    )
    preflight = "".join(notebook["cells"][first_code_index]["source"])
    source = kaggle_v2_evaluation_notebook_source()

    for required in (
        "def _input_files(filename):",
        "def resolve_adapter_dir():",
        "def resolve_base_report_path():",
        "completed_run_adapters",
        "epoch_candidates",
        "run_roots",
        "adapter-metadata.json",
        "epoch-(\\d+)",
        "epochs_completed",
        "Candidates found:",
        "Candidates found: none",
        "adapter={adapter_path}",
        "epochs_completed={adapter_epochs_completed}",
    ):
        assert required in preflight

    assert source.count("def resolve_adapter_dir():") == 1
    assert source.count("def resolve_base_report_path():") == 1
    assert "ADAPTER_DIR = resolve_adapter_dir()" in source
    assert "BASE_REPORT_PATH = resolve_base_report_path()" in source
    assert "len(candidates) != 1" not in preflight
    assert "len(adapter_candidates) != 1" not in preflight


def test_phase6_v2_kaggle_evaluation_discovery_contract_covers_preference_and_ambiguity() -> None:  # noqa: E501
    source = kaggle_v2_evaluation_notebook_source()

    assert 'path.name == "adapter"' in source
    assert 'path.parent / "checkpoints"' in source
    assert 'epoch_pattern = re.compile(r"^epoch-(\\d+)$")' in source
    assert "max(epoch_candidates" in source
    assert "distinct completed training runs" in source
    assert "Ambiguous adapter discovery" in source
    assert "No adapter metadata found" in source
    assert "Ambiguous base report discovery" in source
    assert "No base report found" in source
    assert "str(path) for path in candidates" in source
    assert "_candidate_lines" in source


def test_phase6_v2_kaggle_evaluation_notebook_code_cells_compile() -> None:
    notebook = json.loads(
        KAGGLE_V2_EVALUATION_NOTEBOOK_PATH.read_text(encoding="utf-8")
    )

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        cell_source = cell["source"]
        if isinstance(cell_source, str):
            cell_source = cell_source.splitlines(keepends=True)
        source = "".join(
            line for line in cell_source if not line.lstrip().startswith("%")
        )
        compile(
            source,
            f"{KAGGLE_V2_EVALUATION_NOTEBOOK_PATH}:cell-{index}",
            "exec",
        )


def test_phase6_v2_kaggle_training_notebook_matches_training_contract() -> None:
    source = kaggle_v2_training_notebook_source()

    for required in (
        'Path("/kaggle/working")',
        'RUN_DIR = KAGGLE_WORKING_ROOT / "run"',
        'CHECKPOINTS_DIR = RUN_DIR / "checkpoints"',
        'ADAPTER_DIR = RUN_DIR / "adapter"',
        "socket.create_connection",
        "pypi.org",
        "/proc/driver/nvidia/version",
        "nvidia-smi",
        '"--query-gpu=name,compute_cap"',
        "compute_cap",
        "4-bit training requires 7.0+",
        "Tesla P100",
        "Tesla P40",
        "Tesla P4",
        "GTX 10",
        "GPU capability could not be determined",
        "GPU '{gpu_name}' has CUDA capability {gpu_compute_cap:.1f};",
        "Set Accelerator to 'GPU T4 x2' in the notebook sidebar",
        "(Kaggle also offers P100, which will not work).",
        "failures = []",
        "enable Internet in the notebook sidebar",
        "phone verification at kaggle.com/settings",
        "set Accelerator to GPU T4 x2 in the sidebar",
        "Preflight passed:",
        "compute capability",
        "PINNED_VERSIONS",
        "importlib.metadata.version",
        "configs/phase6/training-v2.json",
        "configs/phase6/dataset-v2.json",
        "configs/phase6/benchmark-v2.json",
        "TrainingConfigV2",
        "DatasetManifestV2",
        "validate_dataset_v2",
        'assert audit.split_counts["train"] > 0',
        'assert audit.split_counts["validation"] > 0',
        'assert len(train_examples) == audit.split_counts["train"]',
        'assert len(validation_examples) == audit.split_counts["validation"]',
        '"split_counts": dict(audit.split_counts)',
        '"train_status_distribution"',
        '"validation_status_distribution"',
        "render_v2_prompt",
        "training_prompt_input",
        "training_target_json",
        "build_chat_messages",
        "apply_chat_template",
        "labels[:, :prompt_length] = -100",
        "assert torch.equal(prompt_ids[0], input_ids[0, :prompt_length])",
        "group_size = accumulation_group_size(",
        "loss / group_size",
        "was_use_cache = model.config.use_cache",
        "was_gradient_checkpointing = model.is_gradient_checkpointing",
        "model.config.use_cache = was_use_cache",
        "model.train(was_training)",
        "emitted_status_counts",
        "outputs_with_support_map",
        "parsed_ok",
        "status_match",
        'CHECKPOINTS_DIR / f"epoch-{epoch + 1:02d}"',
        '"adapter-metadata.json").write_text',
        "checkpoint_dirs[:-2]",
        '"epochs_completed": epochs_completed',
        "relative_to(destination)",
        "Save Version",
        "Save & Run All (Commit)",
        "Add Input → Notebook Output",
    ):
        assert required in source

    first_code_index = next(
        index
        for index, cell in enumerate(
            json.loads(
                KAGGLE_V2_TRAINING_NOTEBOOK_PATH.read_text(encoding="utf-8")
            )["cells"]
        )
        if cell["cell_type"] == "code"
    )
    notebook = json.loads(
        KAGGLE_V2_TRAINING_NOTEBOOK_PATH.read_text(encoding="utf-8")
    )
    preflight = "".join(notebook["cells"][first_code_index]["source"])
    assert first_code_index > 0
    assert "import torch" not in preflight
    assert "import transformers" not in preflight
    assert "import peft" not in preflight
    assert "from src" not in preflight
    assert 'Path("/kaggle/input")' not in source
    assert "google.colab" not in source
    assert "drive.mount" not in source
    assert "/content/drive" not in source
    assert "run_pattern" not in source
    assert not re.search(r"run-\\d", source)
    assert not re.search(r"(?<!\.)\btokenizer\(", source)

    validate_position = source.index("validate_dataset_v2")
    model_position = source.index("AutoModelForCausalLM.from_pretrained")
    assert validate_position < model_position


def test_phase6_v2_kaggle_training_notebook_code_cells_compile() -> None:
    notebook = json.loads(
        KAGGLE_V2_TRAINING_NOTEBOOK_PATH.read_text(encoding="utf-8")
    )

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(
            line for line in cell["source"] if not line.lstrip().startswith("%")
        )
        compile(
            source,
            f"{KAGGLE_V2_TRAINING_NOTEBOOK_PATH}:cell-{index}",
            "exec",
        )


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
    assert config.epochs == 5
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
        'assert audit.split_counts["train"] > 0',
        'assert audit.split_counts["validation"] > 0',
        'assert len(train_examples) == audit.split_counts["train"]',
        'assert len(validation_examples) == audit.split_counts["validation"]',
        '"split_counts": dict(audit.split_counts)',
        '"train_status_distribution"',
        '"validation_status_distribution"',
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
        "was_use_cache = model.config.use_cache",
        "model.config.use_cache = was_use_cache",
        "was_gradient_checkpointing = model.is_gradient_checkpointing",
        "model.train(was_training)",
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
