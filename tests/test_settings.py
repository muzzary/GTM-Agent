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
    assert settings.brave_search_api_key is None


def test_brave_search_key_is_loaded_as_a_secret() -> None:
    settings = Settings.from_mapping({"GTM_BRAVE_SEARCH_API_KEY": "brave-secret"})

    assert settings.brave_search_api_key is not None
    assert settings.brave_search_api_key.get_secret_value() == "brave-secret"
    assert "brave-secret" not in repr(settings)


def test_research_contact_rejects_header_injection() -> None:
    with pytest.raises(ValidationError):
        Settings.from_mapping(
            {"GTM_RESEARCH_CONTACT": "owner@example.com\r\nX-Test: 1"}
        )


@pytest.mark.parametrize("path", ["../cache.sqlite3", "C:/Windows/cache.sqlite3"])
def test_research_cache_path_stays_in_ignored_data_directory(path: str) -> None:
    with pytest.raises(ValidationError):
        Settings.from_mapping({"GTM_RESEARCH_CACHE_PATH": path})


def test_translation_endpoint_and_secret_are_optional_and_paired() -> None:
    settings = Settings.from_mapping(
        {
            "GTM_TRANSLATION_ENDPOINT": "https://colab-tunnel.example/translate",
            "GTM_TRANSLATION_API_KEY": "test-secret",
        }
    )

    assert settings.translation_endpoint.endswith("/translate")
    assert settings.translation_api_key is not None
    assert settings.translation_api_key.get_secret_value() == "test-secret"


@pytest.mark.parametrize(
    "values",
    [
        {"GTM_TRANSLATION_ENDPOINT": "https://colab-tunnel.example/translate"},
        {"GTM_TRANSLATION_API_KEY": "test-secret"},
        {
            "GTM_TRANSLATION_ENDPOINT": "http://colab-tunnel.example/translate",
            "GTM_TRANSLATION_API_KEY": "test-secret",
        },
    ],
)
def test_translation_configuration_rejects_partial_or_insecure_values(
    values: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        Settings.from_mapping(values)
