"""Google AI Studio calls for vocabulary expansion and GRI reranking."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel

from app.schemas.classification import ClassificationResponse, SearchTermsResponse

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "gri_system_prompt.md"
SCHEMA_PATH = ROOT / "schemas" / "classification_response.schema.json"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiUnavailable(RuntimeError):
    """Raised when credentials or the model endpoint are unavailable."""


def _generate_json(system_instruction: str, user_payload: dict, response_model: type[BaseModel]):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip()
    if not api_key or not model:
        raise GeminiUnavailable("Set GEMINI_API_KEY and GEMINI_MODEL to enable GRI classification.")

    request_body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(user_payload, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    request = Request(
        GEMINI_URL.format(model=quote(model, safe="")),
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            raw_response = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise GeminiUnavailable(f"Google AI Studio returned HTTP {exc.code}: {detail}") from exc
    except (TimeoutError, URLError) as exc:
        raise GeminiUnavailable(f"Google AI Studio request failed: {exc}") from exc

    try:
        text = "".join(part["text"] for part in raw_response["candidates"][0]["content"]["parts"] if "text" in part)
        return response_model.model_validate_json(text)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GeminiUnavailable(f"Model response did not satisfy {response_model.__name__}.") from exc


def generate_search_terms(product_facts: dict) -> SearchTermsResponse:
    return _generate_json(
        "Produce 5 to 8 concise English customs and HS search terms using only the supplied product facts. "
        "Do not assign an HS code or infer missing product facts. Return JSON with a single terms array.",
        {"product_facts": product_facts},
        SearchTermsResponse,
    )


def classify_with_gri(payload: dict) -> ClassificationResponse:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload["canonical_json_schema"] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _generate_json(prompt, payload, ClassificationResponse)

