import json
from pathlib import Path

from src.evaluation.phase1 import load_manifest

NOTEBOOK_PATH = Path("notebooks/phase1_colab_feasibility.ipynb")


def test_notebook_is_clean_and_contains_required_feasibility_steps() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )

    assert notebook["nbformat"] == 4
    assert all(cell.get("outputs", []) == [] for cell in notebook["cells"])
    assert all(cell.get("execution_count") is None for cell in notebook["cells"])
    assert "capture_environment" in source
    assert "run_candidate_benchmark" in source
    assert "run_qlora_smoke" in source
    assert "create_bundle" in source
    assert "drive.mount" in source
    assert "cloudflared" not in source.lower()
    assert "ngrok" not in source.lower()


def test_notebook_pins_candidates_and_colab_libraries() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )
    manifest = load_manifest(Path("configs/phase1/benchmark.json"))

    for candidate in manifest.candidates:
        assert candidate.model_id in source
        assert candidate.revision in source

    for requirement in (
        "transformers==5.14.1",
        "accelerate==1.14.0",
        "bitsandbytes==0.50.0",
        "peft==0.20.0",
        "safetensors==0.8.0",
    ):
        assert requirement in source


def test_notebook_code_cells_are_valid_python_after_colab_magics() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(
            line for line in cell["source"] if not line.lstrip().startswith("%")
        )
        compile(source, f"{NOTEBOOK_PATH}:cell-{index}", "exec")
