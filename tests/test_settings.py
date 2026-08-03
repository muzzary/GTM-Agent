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


def test_research_settings_are_optional_until_live_research_is_used() -> None:
    settings = Settings.from_mapping({})

    assert settings.research_contact is None
    assert str(settings.research_cache_path).replace("\\", "/") == (
        "data/research-cache.sqlite3"
    )


def test_research_contact_rejects_header_injection() -> None:
    with pytest.raises(ValidationError):
        Settings.from_mapping(
            {"GTM_RESEARCH_CONTACT": "owner@example.com\r\nX-Test: 1"}
        )


@pytest.mark.parametrize("path", ["../cache.sqlite3", "C:/Windows/cache.sqlite3"])
def test_research_cache_path_stays_in_ignored_data_directory(path: str) -> None:
    with pytest.raises(ValidationError):
        Settings.from_mapping({"GTM_RESEARCH_CACHE_PATH": path})
