"""Lingua language detection shared by the product search pipeline."""

import re

from lingua import LanguageDetectorBuilder

_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()


def detect_language(text: str | None) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return "unknown"
    language = _DETECTOR.detect_language_of(normalized)
    if language is None or language.iso_code_639_1 is None:
        return "unknown"
    return language.iso_code_639_1.name.lower()

