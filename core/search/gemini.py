"""Local Ollama and optional Gemini structured generation."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict

from app.schemas.classification import (
    CandidateHeading,
    ClassificationResponse,
    ClassificationStatus,
    ExcludedPathReason,
    GriDecisionStep,
    GriRule,
    MissingInformation,
    ProductAnalysis,
    SearchTermsResponse,
)

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "gri_system_prompt.md"
SCHEMA_PATH = ROOT / "schemas" / "classification_response.schema.json"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class ModelUnavailable(RuntimeError):
    """Raised when the configured local or hosted model cannot be reached."""


GeminiUnavailable = ModelUnavailable


class ModelFinalClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hs_chapter: str
    hs_heading: str
    hs_subheading: str
    national_tariff_code: str | None = None
    applied_gri_summary: list[GriRule]
    legal_justification: str
    confidence_score: float


class GriModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification_status: ClassificationStatus
    hs_code_6: str
    product_analysis: ProductAnalysis
    gri_decision_tree: list[GriDecisionStep]
    candidate_headings: list[CandidateHeading]
    final_classification: ModelFinalClassification
    missing_information: MissingInformation
    excluded_paths_reason: list[ExcludedPathReason]


class _TranslatedTermsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms: list[str]


def _read_json_response(request: Request, response_model: type[BaseModel]):
    try:
        with urlopen(request, timeout=180) as response:
            raw_response = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise ModelUnavailable(f"Model endpoint returned HTTP {exc.code}: {detail}") from exc
    except (TimeoutError, URLError) as exc:
        raise ModelUnavailable(f"Model request failed: {exc}") from exc

    try:
        if request.full_url.endswith("/api/chat"):
            text = raw_response["message"]["content"]
        else:
            text = "".join(part["text"] for part in raw_response["candidates"][0]["content"]["parts"] if "text" in part)
        return response_model.model_validate_json(text)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ModelUnavailable(f"Model response did not satisfy {response_model.__name__}.") from exc


def _generate_json(system_instruction: str, user_payload: dict, response_model: type[BaseModel]):
    provider = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()
    user_text = json.dumps(user_payload, ensure_ascii=False)
    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        model = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M").strip()
        request_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_text},
            ],
            "format": response_model.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 16384, "num_predict": 4096},
        }
        request = Request(
            f"{base_url}/api/chat",
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return _read_json_response(request, response_model)

    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro").strip()
        if not api_key:
            raise ModelUnavailable("Set GEMINI_API_KEY to use the Gemini provider.")
        request_body = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
        }
        request = Request(
            GEMINI_URL.format(model=quote(model, safe="")),
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        return _read_json_response(request, response_model)

    raise ValueError("LLM_PROVIDER must be 'ollama' or 'gemini'.")


def _local_search_terms(product_facts: dict) -> SearchTermsResponse:
    description = str(product_facts.get("product_description") or "").strip()
    facets = [
        str(product_facts.get("primary_function") or "").strip(),
        " ".join(product_facts.get("material_composition") or []).strip(),
        str(product_facts.get("form_and_packaging") or "").strip(),
    ]
    terms: list[str] = []
    for term in [description, *facets, *(f"{description} {facet}" for facet in facets if facet)]:
        normalized = " ".join(term.split())
        if normalized and normalized.casefold() not in {item.casefold() for item in terms}:
            terms.append(normalized)
        if len(terms) == 8:
            break
    for suffix in ("HS code", "customs tariff", "product classification", "materials", "function"):
        term = f"{description} {suffix}".strip()
        if term.casefold() not in {item.casefold() for item in terms}:
            terms.append(term)
        if len(terms) == 8:
            break
    return SearchTermsResponse(terms=terms)


def _compact_local_payload(payload: dict) -> dict:
    candidates = []
    contexts: dict[tuple[str, str], dict] = {}
    exclusions: dict[tuple[str, str, str], dict] = {}
    for candidate in payload.get("candidates", []):
        chapter = candidate["chapter"]
        heading = candidate["heading"]
        for kind, item in (("chapter", chapter), ("heading", heading)):
            contexts[(kind, item["code"])] = {
                "level": kind,
                "code": item["code"],
                "description": item["description"],
                "notes": item.get("detail"),
            }
        for item in candidate.get("exclusions", []):
            key = (item["source_code"], item["target_code"], item["condition"])
            exclusions[key] = item
        candidates.append({
            "code": candidate["code"],
            "description": candidate["description"],
            "chapter_code": chapter["code"],
            "heading_code": heading["code"],
        })
    return {
        "product_facts": payload["product_facts"],
        "search_terms": payload["search_terms"],
        "candidates": candidates,
        "chapter_heading_context": list(contexts.values()),
        "exclusion_notes": list(exclusions.values()),
    }


def generate_search_terms(product_facts: dict) -> SearchTermsResponse:
    if os.environ.get("LLM_PROVIDER", "ollama").strip().lower() == "ollama":
        return _local_search_terms(product_facts)
    return _generate_json(
        "Produce 5 to 8 concise English customs and HS search terms using only the supplied product facts. "
        "Do not assign an HS code or infer missing product facts. Return JSON with a single terms array.",
        {"product_facts": product_facts},
        SearchTermsResponse,
    )


def translate_search_terms_to_chinese(terms: list[str]) -> list[str]:
    """Translate retrieval phrases locally so English products match the Chinese HS graph."""
    prompt = (
        "Translate each product search phrase into concise Simplified Chinese. Preserve order. "
        "Do not add facts, explanations, or HS codes. Return only the JSON terms array."
    )
    payload = {"terms": terms[:8]}
    if os.environ.get("LLM_PROVIDER", "ollama").strip().lower() != "ollama":
        return _generate_json(prompt, payload, _TranslatedTermsResponse).terms[:8]

    model = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M").strip()
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "format": _TranslatedTermsResponse.model_json_schema(),
        "think": False,
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 256},
    }
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _read_json_response(request, _TranslatedTermsResponse).terms[:8]


def classify_with_gri(payload: dict) -> GriModelResponse | ClassificationResponse:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    if os.environ.get("LLM_PROVIDER", "ollama").strip().lower() == "ollama":
        payload = _compact_local_payload(payload)
        return _generate_json(prompt, payload, GriModelResponse)
    else:
        payload["canonical_json_schema"] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _generate_json(prompt, payload, ClassificationResponse)
