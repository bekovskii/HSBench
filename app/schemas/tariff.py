"""Validated inputs and outputs for tariff and preferential-origin audits."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from app.schemas.classification import StrictModel, _normalize_code


class Market(StrEnum):
    US = "US"
    EU = "EU"
    UK = "UK"
    CN = "CN"


class CriterionKind(StrEnum):
    WHOLLY_OBTAINED = "wholly_obtained"
    TARIFF_SHIFT = "tariff_shift"
    REGIONAL_VALUE_CONTENT = "regional_value_content"
    SPECIFIC_PROCESS = "specific_process"


class ValueMethod(StrEnum):
    BUILD_DOWN = "build_down"
    BUILD_UP = "build_up"


class OriginatingStatus(StrEnum):
    ORIGINATING = "originating"
    NON_ORIGINATING = "non_originating"
    UNKNOWN = "unknown"


class Component(StrictModel):
    hs_code: str
    origin_status: OriginatingStatus
    customs_value: Decimal | None = Field(default=None, ge=0)
    evidence_references: list[str] = Field(default_factory=list)

    @field_validator("hs_code", mode="before")
    @classmethod
    def normalize_component_code(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={2, 4, 6, 8, 10, 12})


class FTACriterion(StrictModel):
    kind: CriterionKind
    required_change_digits: Literal[2, 4, 6] | None = None
    rvc_threshold_pct: Decimal | None = Field(default=None, ge=0, le=100)
    rvc_method: ValueMethod | None = None
    wholly_obtained: bool | None = None
    specific_process_met: bool | None = None
    evidence_references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def criterion_has_rule_parameters(self) -> Self:
        if self.kind == CriterionKind.TARIFF_SHIFT and self.required_change_digits not in {2, 4, 6}:
            raise ValueError("tariff_shift requires required_change_digits of 2, 4, or 6")
        if self.kind == CriterionKind.REGIONAL_VALUE_CONTENT and (
            self.rvc_threshold_pct is None or self.rvc_method is None
        ):
            raise ValueError("regional_value_content requires its official threshold and calculation method")
        if self.kind == CriterionKind.WHOLLY_OBTAINED and self.wholly_obtained is None:
            raise ValueError("wholly_obtained requires a documented true/false determination")
        if self.kind == CriterionKind.SPECIFIC_PROCESS and self.specific_process_met is None:
            raise ValueError("specific_process requires a documented true/false determination")
        return self


class FTAAssessmentRequest(StrictModel):
    agreement: str = Field(min_length=1)
    destination: Market
    origin_country: str = Field(min_length=2)
    product_hs6: str = Field(pattern=r"^\d{6}$")
    rule_source: str = Field(min_length=1)
    rule_source_verified: bool = False
    rule_effective_date: date
    rule_summary: str = Field(min_length=1)
    criteria_logic: Literal["all", "any"] = "all"
    criteria: list[FTACriterion] = Field(min_length=1)
    components: list[Component] = Field(default_factory=list)
    product_wholly_obtained: bool | None = None
    product_value: Decimal | None = Field(default=None, gt=0)
    evidence_references: list[str] = Field(default_factory=list)

    @field_validator("product_hs6", mode="before")
    @classmethod
    def normalize_product_code(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={6, 8, 10, 12})[:6]


class FTACriterionResult(StrictModel):
    kind: CriterionKind
    status: Literal["pass", "fail", "unknown"]
    explanation: str
    calculated_value_pct: Decimal | None = None
    evidence_references: list[str]


class FTAAssessmentResult(StrictModel):
    agreement: str
    destination: Market
    origin_country: str
    product_hs6: str
    status: Literal["qualified", "not_qualified", "insufficient_data"]
    rule_source: str
    rule_source_verified: bool
    rule_effective_date: date
    rule_summary: str
    criteria_results: list[FTACriterionResult]
    explanation: str
    evidence_references: list[str]


class TariffEngineeringRequest(StrictModel):
    assembled_hs6: str = Field(pattern=r"^\d{6}$")
    unassembled_hs6: str = Field(pattern=r"^\d{6}$")
    destination: Market
    annual_import_value: Decimal = Field(ge=0)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    presented_unassembled: bool
    complete_article_or_essential_character_supported: bool | None = None
    alternative_classifications_verified: bool = False
    classification_sources: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)

    @field_validator("assembled_hs6", "unassembled_hs6", mode="before")
    @classmethod
    def normalize_hs6(cls, value: object) -> str:
        return _normalize_code(value, allowed_lengths={6, 8, 10, 12})[:6]

    @model_validator(mode="after")
    def source_required_for_verified_alternative(self) -> Self:
        if self.alternative_classifications_verified and not self.classification_sources:
            raise ValueError("verified alternative classifications require source references")
        if self.presented_unassembled and self.complete_article_or_essential_character_supported is True and not self.evidence_references:
            raise ValueError("a positive GRI 2(a) determination requires evidence references")
        return self


class TariffEngineeringResult(StrictModel):
    status: Literal["no_saving", "review_required", "potential_saving"]
    assembled_hs6: str
    unassembled_hs6: str
    destination: Market
    assembled_mfn_pct: Decimal | None
    unassembled_mfn_pct: Decimal | None
    annual_import_value: Decimal
    currency: str
    potential_savings: Decimal | None
    explanation: str
    legal_review_required: bool = True
    data_verified_on: date | None = None

