import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2

from src.schemas.research import TranslationStatus


@dataclass(frozen=True)
class TranslationResult:
    english_text: str
    source_language: str
    status: TranslationStatus


class ResearchTranslator(Protocol):
    def translate_to_english(self, text: str) -> TranslationResult: ...


class ConservativeEnglishTranslator:
    """Passes likely English through and flags other text for a model adapter."""

    _english_markers = frozenset(
        {
            "about",
            "company",
            "customer",
            "information",
            "news",
            "our",
            "product",
            "project",
            "service",
            "solution",
            "team",
            "the",
            "we",
        }
    )

    def translate_to_english(self, text: str) -> TranslationResult:
        words = set(re.findall(r"[a-z]+", text.casefold()))
        if words & self._english_markers:
            return TranslationResult(text, "en", TranslationStatus.NOT_NEEDED)
        return TranslationResult("", "und", TranslationStatus.UNAVAILABLE)


class TranslationTransport(Protocol):
    def translate(
        self,
        endpoint: str,
        api_key: str,
        payload: Mapping[str, str],
    ) -> Mapping[str, Any]: ...


class HttpxTranslationTransport:
    def translate(
        self,
        endpoint: str,
        api_key: str,
        payload: Mapping[str, str],
    ) -> Mapping[str, Any]:
        try:
            with httpx2.Client(
                timeout=httpx2.Timeout(30.0, connect=5.0),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=dict(payload),
                )
                response.raise_for_status()
                value = response.json()
        except (httpx2.HTTPError, ValueError) as error:
            raise RuntimeError("translation_unavailable") from error
        if not isinstance(value, dict):
            raise RuntimeError("translation_invalid_response")
        return value


class ColabResearchTranslator:
    """Calls an operator-configured Colab model without exposing its API key."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        transport: TranslationTransport | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._transport = transport or HttpxTranslationTransport()

    def translate_to_english(self, text: str) -> TranslationResult:
        try:
            value = self._transport.translate(
                self._endpoint,
                self._api_key,
                {
                    "task": "translate",
                    "target_language": "en",
                    "text": text[:8_000],
                },
            )
        except RuntimeError:
            return TranslationResult("", "und", TranslationStatus.UNAVAILABLE)
        translated_text = value.get("translated_text")
        source_language = value.get("source_language")
        if (
            not isinstance(translated_text, str)
            or not translated_text.strip()
            or len(translated_text) > 8_000
            or not isinstance(source_language, str)
            or re.fullmatch(r"[a-z]{2,3}|und", source_language) is None
        ):
            return TranslationResult("", "und", TranslationStatus.UNAVAILABLE)
        status = (
            TranslationStatus.NOT_NEEDED
            if source_language == "en"
            else TranslationStatus.TRANSLATED
        )
        return TranslationResult(translated_text.strip(), source_language, status)
