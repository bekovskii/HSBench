"""Canonical, strict Pydantic contract for GRI classification results."""

from __future__ import annotations

import json
import re
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GriRule(StrEnum):
    GRI_1 = "GRI_1"
    GRI_2A = "GRI_2A"
    GRI_2B = "GRI_2B"
    GRI_3A = "GRI_3A"
    GRI_3B = "GRI_3B"
    GRI_3C = "GRI_3C"
    GRI_4 = "GRI_4"
    GRI_5A = "GRI_5A"
    GRI_5B = "GRI_5B"
    GRI_6 = "GRI_6"


class ClassificationStatus(StrEnum):
    CLASSIFIED = "classified"
    NEEDS_MORE_INFORMATION = "needs_more_information"
    NO_SUPPORTED_CANDIDATE = "no_supported_candidate"


class CandidateStatus(StrEnum):
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class OriginStatus(StrEnum):
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_ASSESSED = "not_assessed"


class ProductAnalysis(StrictModel):
    normalized_description: str = Field(min_length=1, description="Eşyanın gümrük terminolojisine uygun standartlaştırılmış tanımı.")
    material_composition: list[str] = Field(description="Eşyayı oluşturan materyaller veya bileşenler.")
    primary_function: str = Field(min_length=1, description="Eşyanın ana fonksiyonu veya kullanım amacı.")
    form_and_packaging: str | None = Field(default=None, description="Sunuluş şekli: demonte, perakende set, özel kutulu vb.")


class GriDecisionStep(StrictModel):
    rule: GriRule = Field(description="Değerlendirilen Genel Yorum Kuralı.")
    is_applied: bool = Field(description="Kural sınıflandırma kararında aktif olarak kullanıldı mı?")
    reasoning: str = Field(min_length=1, description="Uygulama veya atlama gerekçesinin kısa, denetlenebilir özeti.")
    referenced_notes: list[str] = Field(default_factory=list, description="Dikkate alınan Bölüm, Fasıl veya Alt Pozisyon notları.")


class CandidateHeading(StrictModel):
    code: str = Field(pattern=r"^(?:\d{2}|\d{4}|\d{6}|\d{8}|\d{10}|\d{12})$", description="Aday pozisyon veya alt pozisyon kodu.")
    description: str | None = Field(default=None, description="Pozisyonun sağlanan tarife kaynağındaki tanımı.")
    status: CandidateStatus = Field(description="Adayın seçilme veya elenme durumu.")
    elimination_or_selection_reason: str = Field(min_length=1, description="Adayın seçilme veya elenme nedeni.")

    @field_validator("code", mode="before")
    @classmethod
    def normalize_heading_code(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={2, 4, 6, 8, 10, 12})


class FinalClassification(StrictModel):
    hs_chapter: str = Field(pattern=r"^(?:\d{2})?$", description="İki haneli HS fasıl kodu; bilinmiyorsa boş.")
    hs_heading: str = Field(pattern=r"^(?:\d{4})?$", description="Dört haneli HS pozisyon kodu; bilinmiyorsa boş.")
    hs_subheading: str = Field(pattern=r"^(?:\d{6})?$", description="Altı haneli HS alt pozisyonu; bilinmiyorsa boş.")
    national_tariff_code: str | None = Field(default=None, pattern=r"^(?:\d{6}|\d{8}|\d{10}|\d{12})$", description="Resmi kaynaktan doğrulanmış ulusal kod; bilinmiyorsa null.")
    applied_gri_summary: list[GriRule] = Field(description="Nihai kararda uygulanan kuralların sıralı listesi.")
    legal_justification: str = Field(min_length=1, description="Kararın kısa ve kaynaklara dayalı gerekçesi.")
    confidence_score: float = Field(ge=0, le=1, description="0.0–1.0 arası kanıt temelli güven puanı.")

    @field_validator("hs_chapter", mode="before")
    @classmethod
    def normalize_chapter(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={0, 2})

    @field_validator("hs_heading", mode="before")
    @classmethod
    def normalize_heading(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={0, 4})

    @field_validator("hs_subheading", mode="before")
    @classmethod
    def normalize_subheading(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={0, 6})

    @field_validator("national_tariff_code", mode="before")
    @classmethod
    def normalize_national_code(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        return _normalize_code(value, allowed_lengths={6, 8, 10, 12})

    @model_validator(mode="after")
    def hierarchy_matches(self) -> Self:
        if self.hs_subheading:
            if self.hs_chapter != self.hs_subheading[:2]:
                raise ValueError("hs_chapter must match the first two digits of hs_subheading")
            if self.hs_heading != self.hs_subheading[:4]:
                raise ValueError("hs_heading must match the first four digits of hs_subheading")
        elif self.hs_chapter or self.hs_heading:
            raise ValueError("chapter and heading must be empty when hs_subheading is unknown")
        if self.national_tariff_code and self.hs_subheading and not self.national_tariff_code.startswith(self.hs_subheading):
            raise ValueError("national_tariff_code must extend hs_subheading")
        return self


class MissingInformation(StrictModel):
    needs_more_info: bool = Field(description="Kesin sınıflandırma için kullanıcıdan ek bilgi gerekiyor mu?")
    clarification_questions: list[str] = Field(description="Eksik kritik teknik olgular için sorular.")

    @model_validator(mode="after")
    def questions_match_flag(self) -> Self:
        if self.needs_more_info != bool(self.clarification_questions):
            raise ValueError("clarification_questions must be present exactly when needs_more_info is true")
        return self


class ExcludedPathReason(StrictModel):
    code: str = Field(pattern=r"^(?:\d{2}|\d{4}|\d{6}|\d{8}|\d{10}|\d{12})$")
    description: str | None = None
    reason: str = Field(min_length=1)
    referenced_notes: list[str] = Field(default_factory=list)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_excluded_code(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={2, 4, 6, 8, 10, 12})


class MarketRates(StrictModel):
    US: float | None
    EU: float | None
    UK: float | None
    CN: float | None
    source: str
    verified_on: date | None

    @field_validator("US", "EU", "UK", "CN")
    @classmethod
    def valid_rate(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 100:
            raise ValueError("MFN rate must be between 0 and 100 percent")
        return value


class TariffEngineeringAdvice(StrictModel):
    status: str = Field(pattern="^(not_assessed|no_saving|review_required|potential_saving)$")
    scenario: str | None = None
    assembled_hs6: str | None = Field(default=None, pattern=r"^\d{6}$")
    unassembled_hs6: str | None = Field(default=None, pattern=r"^\d{6}$")
    destination: str | None = None
    assembled_mfn_pct: float | None = None
    unassembled_mfn_pct: float | None = None
    annual_import_value: float | None = Field(default=None, ge=0)
    potential_savings: float | None = Field(default=None, ge=0)
    currency: str | None = None
    data_verified_on: date | None = None
    explanation: str = Field(min_length=1)
    legal_review_required: bool = True


class FTAAssessment(StrictModel):
    agreement: str | None = None
    status: OriginStatus
    rule_source: str | None = None
    rule_effective_date: str | None = None
    rule_summary: str | None = None
    explanation: str = Field(min_length=1)
    evidence_references: list[str] = Field(default_factory=list)


class SearchMetadata(StrictModel):
    detected_language: str
    search_terms: list[str]
    candidate_count: int = Field(ge=0)
    source: str


class SearchTermsResponse(StrictModel):
    terms: list[str] = Field(min_length=5, max_length=8)

    @field_validator("terms")
    @classmethod
    def terms_are_unique(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(term.strip() for term in values if term.strip()))
        if not 5 <= len(cleaned) <= 8:
            raise ValueError("search_terms must contain 5 to 8 unique non-empty terms")
        return cleaned


class ClassificationResponse(StrictModel):
    """Merged response contract from ClassificationResponse.txt and the roadmap."""

    classification_status: ClassificationStatus = Field(description="Kararın sınıflandırıldı, ek bilgi gerekli veya aday bulunamadı durumu.")
    hs_code_6: str = Field(pattern=r"^(?:\d{6})?$", description="Doğrulanmış WCO HS6; belirlenemediyse boş.")
    hs_code_10: str | None = Field(pattern=r"^\d{10}$", description="Resmi kaynakta doğrulanmış 10 haneli kod; mevcut değilse null.")
    product_analysis: ProductAnalysis
    gri_decision_tree: list[GriDecisionStep] = Field(description="GYK 1–6 karar adımlarının sıralı kaydı.")
    candidate_headings: list[CandidateHeading] = Field(description="Analizde değerlendirilen aday pozisyonlar.")
    final_classification: FinalClassification
    missing_information: MissingInformation
    excluded_paths_reason: list[ExcludedPathReason] = Field(description="Graf yolundaki hariç tutmalar ve aday eleme gerekçeleri.")
    tariff_engineering_advice: TariffEngineeringAdvice = Field(description="Monte/demonte senaryosu; kanıt yoksa inceleme gerekli.")
    mfn_rates: MarketRates = Field(description="US, EU, UK ve CN için mevcut MFN örnek oranları ve kaynak tarihi.")
    fta_origin: FTAAssessment = Field(description="Sağlanan anlaşma kuralı ve menşe kanıtına göre FTA değerlendirmesi.")
    search_metadata: SearchMetadata = Field(description="Dil algılama, arama terimleri ve aday kaynağı.")

    @field_validator("hs_code_6", mode="before")
    @classmethod
    def normalize_hs6(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={0, 6})

    @field_validator("hs_code_10", mode="before")
    @classmethod
    def normalize_hs10(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        return _normalize_code(value, allowed_lengths={10})

    @model_validator(mode="after")
    def response_is_consistent(self) -> Self:
        final_code = self.final_classification.hs_subheading
        if self.hs_code_6 != final_code:
            raise ValueError("hs_code_6 must equal final_classification.hs_subheading")
        if self.hs_code_10 and self.final_classification.national_tariff_code != self.hs_code_10:
            raise ValueError("hs_code_10 must equal final_classification.national_tariff_code")
        if self.classification_status == ClassificationStatus.CLASSIFIED:
            if len(self.hs_code_6) != 6 or self.missing_information.needs_more_info:
                raise ValueError("classified results require a six-digit code and no unresolved required facts")
            if GriRule.GRI_6 not in self.final_classification.applied_gri_summary:
                raise ValueError("classified HS6 results must include GRI 6 in the applied rules")
        elif self.hs_code_6:
            raise ValueError("unclassified results must not contain a final HS6 code")
        if self.classification_status == ClassificationStatus.NEEDS_MORE_INFORMATION and not self.missing_information.needs_more_info:
            raise ValueError("needs_more_information status requires clarification questions")

        order = {rule: index for index, rule in enumerate(GriRule)}
        rules = [step.rule for step in self.gri_decision_tree]
        if len(set(rules)) != len(rules) or rules != sorted(rules, key=order.__getitem__):
            raise ValueError("gri_decision_tree must list each rule at most once in GRI order")
        applied = [step.rule for step in self.gri_decision_tree if step.is_applied]
        if applied != self.final_classification.applied_gri_summary:
            raise ValueError("applied_gri_summary must match applied decision-tree steps")
        selected = [item.code for item in self.candidate_headings if item.status == CandidateStatus.SELECTED]
        if self.hs_code_6 and self.hs_code_6 not in selected:
            raise ValueError("the final HS6 code must be among selected candidates")
        return self


def classification_json_schema() -> dict:
    schema = ClassificationResponse.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://tarifelab.local/schemas/classification-response.schema.json"
    return schema


def _normalize_code(value: object, allowed_lengths: set[int]) -> str:
    if not isinstance(value, (str, int)):
        raise ValueError("tariff code must be a string of digits")
    raw = str(value).strip()
    if not re.fullmatch(r"[0-9.\s-]*", raw):
        raise ValueError("tariff code may contain only digits and formatting separators")
    code = re.sub(r"[.\s-]", "", raw)
    if len(code) not in allowed_lengths:
        raise ValueError(f"tariff code must contain one of {sorted(allowed_lengths)} digits")
    return code


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[2] / "schemas" / "classification_response.schema.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(classification_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}")

