from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import ValidationError

from src.research.translation import ColabResearchTranslator
from src.schemas.research import ResearchFinding, TranslationStatus


class FakeTransport:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, str, Mapping[str, str]]] = []

    def translate(
        self,
        endpoint: str,
        api_key: str,
        payload: Mapping[str, str],
    ) -> Mapping[str, Any]:
        self.calls.append((endpoint, api_key, payload))
        return self.response


def test_colab_translator_returns_english_text_and_language_metadata() -> None:
    transport = FakeTransport(
        {
            "translated_text": "The company provides logistics software.",
            "source_language": "de",
        }
    )
    translator = ColabResearchTranslator(
        "https://colab-tunnel.example/translate",
        "secret-key",
        transport,
    )

    result = translator.translate_to_english("Das Unternehmen bietet Software an.")

    assert result.english_text == "The company provides logistics software."
    assert result.source_language == "de"
    assert result.status is TranslationStatus.TRANSLATED
    assert transport.calls[0][2]["target_language"] == "en"


def test_colab_translator_rejects_untrusted_response_shape() -> None:
    translator = ColabResearchTranslator(
        "https://colab-tunnel.example/translate",
        "secret-key",
        FakeTransport({"translated_text": "", "source_language": "made-up"}),
    )

    result = translator.translate_to_english("source text")

    assert result.status is TranslationStatus.UNAVAILABLE


def test_finding_rejects_inconsistent_translation_metadata() -> None:
    with pytest.raises(ValidationError):
        ResearchFinding(
            section="company",
            heading="Company",
            summary="English text",
            source_language="en",
            translation_status=TranslationStatus.TRANSLATED,
            evidence_ids=("evidence-example1",),
        )
