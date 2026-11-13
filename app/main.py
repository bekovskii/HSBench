"""FastAPI mock API for the MVP validation page."""

import re
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.schemas.classification import (
    ClassificationResponse,
    ClassificationStatus,
    FTAAssessment,
    GriDecisionStep,
    MarketRates,
    MissingInformation,
    ProductAnalysis,
    SearchMetadata,
    TariffEngineeringAdvice,
    USITCTariffData,
    USITCTariffStatus,
    classification_json_schema,
)
from app.schemas.requests import ProductClassificationRequest
from app.schemas.tariff import FTAAssessmentRequest, FTAAssessmentResult, TariffEngineeringRequest, TariffEngineeringResult
from app.schemas.hs_graph import HSGraph
from core.duty_lookup import lookup_hs6, mfn_rates, search
from core.duty_lookup.usitc import fetch_usitc_tariffs
from core.search.gemini import GeminiUnavailable, classify_with_gri, generate_search_terms
from core.search.service import search_candidates
from core.tariff_engine.engineering import compare_assembled_unassembled
from core.tariff_engine.origin import evaluate_fta_origin

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "early_access.sqlite3"
GRAPH = HSGraph.load()

app = FastAPI(title="TarifeLab MVP API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class PreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class EarlyAccessRequest(BaseModel):
    email: str = Field(max_length=254)
    consent: bool


def _query_text(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme in ("http", "https") and parsed.hostname:
        return unquote(parsed.path.replace("/", " ").replace("-", " ").replace("_", " ")).strip()
    return value.strip()


def _rates_for(code: str, us_tariff_data: USITCTariffData | None = None) -> MarketRates:
    row = lookup_hs6(code)
    rates = mfn_rates(code)
    rate_values = {_rate_percent(line.general_rate) for line in us_tariff_data.lines} if us_tariff_data else set()
    rates["US"] = next(iter(rate_values)) if rate_values and None not in rate_values and len(rate_values) == 1 else None
    return MarketRates(
        **rates,
        source="USITC HTS API (US); hs-code-lookup sample dataset (EU/UK/CN)" if row else "USITC HTS API (US); other markets unavailable",
        verified_on=row["last_verified"] if row else None,
    )


def _rate_percent(value: str) -> float | None:
    if value.casefold() == "free":
        return 0.0
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", value)
    return float(match.group(1)) if match else None


def _us_tariff_data(code: str) -> USITCTariffData:
    try:
        return USITCTariffData.model_validate(fetch_usitc_tariffs(code))
    except (ValueError, TypeError) as exc:
        return USITCTariffData(
            status=USITCTariffStatus.SOURCE_UNAVAILABLE,
            hs6_code=code,
            message=f"USITC HTS response could not be validated: {exc}",
        )


def _not_assessed_tariff_advice() -> TariffEngineeringAdvice:
    return TariffEngineeringAdvice(
        status="not_assessed",
        explanation="No verified assembled/unassembled scenario and current official tariff data were supplied.",
    )


def _not_assessed_fta() -> FTAAssessment:
    return FTAAssessment(
        status="not_assessed",
        rule_source_verified=False,
        explanation="No agreement-specific rule and origin evidence were supplied.",
    )


def _tariff_advice(request: TariffEngineeringRequest) -> TariffEngineeringAdvice:
    result = compare_assembled_unassembled(request)
    return TariffEngineeringAdvice(
        status=result.status,
        scenario=f"assembled {result.assembled_hs6} / unassembled {request.unassembled_hs6}",
        assembled_hs6=result.assembled_hs6,
        unassembled_hs6=result.unassembled_hs6,
        destination=result.destination.value,
        assembled_mfn_pct=float(result.assembled_mfn_pct) if result.assembled_mfn_pct is not None else None,
        unassembled_mfn_pct=float(result.unassembled_mfn_pct) if result.unassembled_mfn_pct is not None else None,
        annual_import_value=float(result.annual_import_value),
        potential_savings=float(result.potential_savings) if result.potential_savings is not None else None,
        currency=result.currency,
        data_verified_on=result.data_verified_on,
        explanation=result.explanation,
        legal_review_required=result.legal_review_required,
    )


def _fta_assessment(request: FTAAssessmentRequest | None) -> FTAAssessment:
    if request is None:
        return _not_assessed_fta()
    result = evaluate_fta_origin(request)
    return FTAAssessment(
        agreement=result.agreement,
        status=result.status,
        rule_source=result.rule_source,
        rule_source_verified=result.rule_source_verified,
        rule_effective_date=result.rule_effective_date.isoformat(),
        rule_summary=result.rule_summary,
        explanation=result.explanation + " " + "; ".join(item.explanation for item in result.criteria_results),
        evidence_references=result.evidence_references,
    )


def _no_candidate_response(payload: ProductClassificationRequest, query: str, terms: list[str], language: str, source: str) -> ClassificationResponse:
    return ClassificationResponse(
        classification_status=ClassificationStatus.NO_SUPPORTED_CANDIDATE,
        hs_code_6="",
        hs_code_10=None,
        product_analysis=ProductAnalysis(
            normalized_description=query,
            material_composition=payload.material_composition,
            primary_function=payload.primary_function or "Not provided",
            form_and_packaging=payload.form_and_packaging,
        ),
        gri_decision_tree=[GriDecisionStep(rule="GRI_1", is_applied=False, reasoning="No supported HS candidate was retrieved.")],
        candidate_headings=[],
        final_classification={
            "hs_chapter": "",
            "hs_heading": "",
            "hs_subheading": "",
            "national_tariff_code": None,
            "applied_gri_summary": [],
            "legal_justification": "The available candidate sources did not support a classification.",
            "confidence_score": 0,
        },
        missing_information=MissingInformation(needs_more_info=False, clarification_questions=[]),
        excluded_paths_reason=[],
        tariff_engineering_advice=_not_assessed_tariff_advice(),
        mfn_rates=MarketRates(US=None, EU=None, UK=None, CN=None, source="not_available_in_sample", verified_on=None),
        us_tariff_data=USITCTariffData(status=USITCTariffStatus.NOT_ASSESSED),
        fta_origin=_fta_assessment(payload.fta_assessment),
        search_metadata=SearchMetadata(detected_language=language, search_terms=terms, candidate_count=0, source=source),
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "graph_nodes": len(GRAPH.nodes) - 1}


@app.get("/api/contracts/classification-response")
def classification_response_contract():
    return classification_json_schema()


@app.get("/api/hs/{code}")
def query_hs_code(code: str):
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=422, detail="HS code must contain exactly 6 digits")
    try:
        return GRAPH.classification_context(code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/us-tariff/{code}", response_model=USITCTariffData)
def query_us_tariff(code: str):
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=422, detail="HS code must contain exactly 6 digits")
    return _us_tariff_data(code)


@app.post("/api/classify", response_model=ClassificationResponse)
def classify_product(payload: ProductClassificationRequest):
    query = _query_text(payload.product_description)
    if len(query) < 3:
        raise HTTPException(status_code=422, detail="Ürün URL'sinde aranabilir ürün metni veya açıklama bulunamadı.")
    facts = {
        "product_description": query,
        "material_composition": payload.material_composition,
        "primary_function": payload.primary_function,
        "form_and_packaging": payload.form_and_packaging,
    }
    try:
        terms = generate_search_terms(facts).terms
        rows, language, source = search_candidates(query, terms, limit=5)
    except GeminiUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ImportError, RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=f"Arama katmanı hazır değil: {exc}") from exc

    candidates: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        raw_code = str(row.get("hs6_code") or row.get("code") or "")
        code = "".join(character for character in raw_code if character.isdigit())
        child_codes = [child.code for child in GRAPH.children(code) if child.level == "subheading"] if len(code) == 4 else [code]
        for hs6 in child_codes:
            if len(hs6) != 6 or hs6 in seen:
                continue
            try:
                context = GRAPH.classification_context(hs6)
            except ValueError:
                continue
            seen.add(hs6)
            candidates.append({
                "code": hs6,
                "description": row.get("description") or GRAPH.node(hs6).name,
                "chapter": context["chapter"],
                "heading": context["heading"],
                "exclusions": context["exclusions"],
                "mfn_rates": mfn_rates(hs6),
            })
            if len(candidates) == 5:
                break
        if len(candidates) == 5:
            break

    if not candidates:
        return _no_candidate_response(payload, query, terms, language, source)

    try:
        result = classify_with_gri({"product_facts": facts, "search_terms": terms, "candidates": candidates})
    except GeminiUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if result.classification_status == ClassificationStatus.NO_SUPPORTED_CANDIDATE:
        return _no_candidate_response(payload, query, terms, language, source)

    allowed_codes = {candidate["code"] for candidate in candidates}
    if result.hs_code_6 and result.hs_code_6 not in allowed_codes:
        raise HTTPException(status_code=502, detail="Model result selected an HS6 code outside the retrieved candidates.")
    if any(item.code not in allowed_codes and item.code not in {code[:4] for code in allowed_codes} for item in result.candidate_headings):
        raise HTTPException(status_code=502, detail="Model result introduced a heading outside the retrieved candidate paths.")
    if any(item.code not in allowed_codes and item.code not in {code[:4] for code in allowed_codes} for item in result.excluded_paths_reason):
        raise HTTPException(status_code=502, detail="Model result introduced an exclusion path outside the retrieved candidates.")
    if payload.fta_assessment and result.hs_code_6 and payload.fta_assessment.product_hs6 != result.hs_code_6:
        fta = FTAAssessment(
            agreement=payload.fta_assessment.agreement,
            status="insufficient_data",
            rule_source=payload.fta_assessment.rule_source,
            rule_source_verified=payload.fta_assessment.rule_source_verified,
            rule_effective_date=payload.fta_assessment.rule_effective_date.isoformat(),
            rule_summary=payload.fta_assessment.rule_summary,
            explanation="FTA request HS6 does not match the selected classification; origin result was not attached.",
            evidence_references=payload.fta_assessment.evidence_references,
        )
    else:
        fta = _fta_assessment(payload.fta_assessment)

    values = result.model_dump()
    values["hs_code_10"] = None
    values["final_classification"]["hs_chapter"] = result.hs_code_6[:2]
    values["final_classification"]["hs_heading"] = result.hs_code_6[:4]
    values["final_classification"]["hs_subheading"] = result.hs_code_6
    values["product_analysis"]["material_composition"] = payload.material_composition
    values["product_analysis"]["primary_function"] = payload.primary_function or "Not provided"
    values["product_analysis"]["form_and_packaging"] = payload.form_and_packaging
    values["final_classification"]["national_tariff_code"] = None
    us_tariff_data = _us_tariff_data(result.hs_code_6)
    values["us_tariff_data"] = us_tariff_data.model_dump()
    values["mfn_rates"] = _rates_for(result.hs_code_6, us_tariff_data).model_dump()
    values["tariff_engineering_advice"] = (
        _tariff_advice(payload.tariff_engineering).model_dump()
        if payload.tariff_engineering
        else _not_assessed_tariff_advice().model_dump()
    )
    values["fta_origin"] = fta.model_dump()
    values["search_metadata"] = SearchMetadata(
        detected_language=language,
        search_terms=terms,
        candidate_count=len(candidates),
        source=source,
    ).model_dump()
    try:
        return ClassificationResponse.model_validate(values)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"GRI result failed canonical contract validation: {exc}") from exc


@app.post("/api/fta/evaluate", response_model=FTAAssessmentResult)
def evaluate_origin(payload: FTAAssessmentRequest):
    if GRAPH.node(payload.product_hs6) is None:
        raise HTTPException(status_code=404, detail="FTA assessment HS6 code is not present in the loaded HS graph.")
    return evaluate_fta_origin(payload)


@app.post("/api/tariff-engineering/compare", response_model=TariffEngineeringResult)
def compare_tariff_scenario(payload: TariffEngineeringRequest):
    for code in {payload.assembled_hs6, payload.unassembled_hs6}:
        if GRAPH.node(code) is None:
            raise HTTPException(status_code=404, detail=f"HS6 code {code} is not present in the loaded HS graph.")
    return compare_assembled_unassembled(payload)


@app.post("/api/preview")
def preview_product(payload: PreviewRequest):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Ürün açıklaması boş olamaz.")
    parsed = urlparse(query)
    if parsed.scheme in ("http", "https") and parsed.hostname:
        # URL is never fetched; only its visible path is used for the mock preview.
        query = unquote(parsed.path.replace("/", " ").replace("-", " ").replace("_", " "))
    candidates = [row for row in search(query) if len(row["hs6_code"]) == 6]
    return {
        "candidates": [
            {
                "code": row["hs6_code"],
                "description": row["description"],
                "rates": _rates_for(row["hs6_code"], us_tariff_data).model_dump(),
                "us_tariff_data": us_tariff_data.model_dump(),
                "verified": row["last_verified"],
            }
            for row in candidates
            for us_tariff_data in [_us_tariff_data(row["hs6_code"])]
        ],
        "notice": "Bu yalnızca 375 kodluk örnek tarifede İngilizce metin eşleşmesidir; resmi GTİP sınıflandırması değildir.",
    }


@app.post("/api/early-access", status_code=201)
def early_access(payload: EarlyAccessRequest):
    email = payload.email.strip().lower()
    if payload.consent is not True:
        raise HTTPException(status_code=400, detail="E-posta kaydı için açık rıza gereklidir.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=400, detail="Geçerli bir e-posta adresi girin.")
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS early_access (email TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        db.execute("INSERT OR IGNORE INTO early_access(email) VALUES (?)", (email,))
    return {"message": "Erken erişim listenize eklendiniz."}
