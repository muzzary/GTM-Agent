import pytest
from pydantic import ValidationError

from src.runtime.settings import Settings


def test_settings_use_safe_local_defaults() -> None:
    settings = Settings.from_mapping({})

    assert settings.app_env == "development"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000


def test_settings_reject_invalid_port() -> None:
    with pytest.raises(ValidationError):
        Settings.from_mapping({"GTM_API_PORT": "70000"})
