import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schemas.training import TrainingConfig

CONFIG_PATH = Path("configs/phase6/training.json")
V2_CONFIG_PATH = Path("configs/phase6/training-v2.json")


def test_phase6_training_config_is_pinned_and_bounded() -> None:
    config = TrainingConfig.model_validate(
        json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    )

    assert config.base_model_revision == "cdbee75f17c01a7cc42f958dc650907174af0554"
    assert config.max_steps <= 1000
    assert config.max_length <= 4096


def test_phase6_training_config_rejects_unpinned_or_unbounded_values() -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["base_model_revision"] = "latest"
    raw["max_steps"] = 1001

    with pytest.raises(ValidationError):
        TrainingConfig.model_validate(raw)


def test_phase6_v2_training_config_uses_five_epochs_and_four_step_accumulation(
    ) -> None:
    config = json.loads(V2_CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["epochs"] == 5
    assert config["gradient_accumulation_steps"] == 4
