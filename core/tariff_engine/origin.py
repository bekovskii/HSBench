"""FTA origin qualification checks driven only by a supplied official rule."""

from datetime import date
from decimal import Decimal

from app.schemas.tariff import (
    CriterionKind,
    FTAAssessmentRequest,
    FTAAssessmentResult,
    FTACriterionResult,
    OriginatingStatus,
    ValueMethod,
)


def evaluate_fta_origin(request: FTAAssessmentRequest, today: date | None = None) -> FTAAssessmentResult:
    """Evaluate supplied agreement criteria; this module contains no invented FTA rules."""
    today = today or date.today()
    evidence = list(dict.fromkeys(request.evidence_references))
    results: list[FTACriterionResult] = []

    for criterion in request.criteria:
        criterion_evidence = list(dict.fromkeys(evidence + criterion.evidence_references))
        status = "unknown"
        calculated_value = None
        explanation = "The supplied evidence is insufficient to evaluate this rule."

        if criterion.kind == CriterionKind.WHOLLY_OBTAINED:
            determination = request.product_wholly_obtained
            if determination is not None and criterion_evidence:
                status = "pass" if determination else "fail"
                explanation = "The supplied wholly-obtained determination and evidence were applied."
            else:
                explanation = "Provide a documented wholly-obtained determination and supporting evidence."

        elif criterion.kind == CriterionKind.TARIFF_SHIFT:
            non_originating = [item for item in request.components if item.origin_status == OriginatingStatus.NON_ORIGINATING]
            unknown = [item for item in request.components if item.origin_status == OriginatingStatus.UNKNOWN]
            digits = criterion.required_change_digits
            if unknown or not request.components or any(not item.evidence_references for item in request.components):
                explanation = "Provide origin status and HS codes for every material in the bill of materials."
            elif not non_originating:
                status = "pass"
                explanation = "No non-originating material was identified in the supplied bill of materials."
            elif any(len(item.hs_code) < digits for item in non_originating):
                explanation = f"Each non-originating material needs at least {digits} HS digits to check the tariff shift."
            else:
                unchanged = [item.hs_code for item in non_originating if item.hs_code[:digits] == request.product_hs6[:digits]]
                status = "fail" if unchanged else "pass"
                explanation = (
                    f"Tariff shift not met for component codes: {', '.join(unchanged)}."
                    if unchanged
                    else f"All supplied non-originating material codes change at the required {digits}-digit level."
                )

        elif criterion.kind == CriterionKind.REGIONAL_VALUE_CONTENT:
            if request.product_value is None or any(
                item.customs_value is None or item.origin_status == OriginatingStatus.UNKNOWN or not item.evidence_references
                for item in request.components
            ):
                explanation = "Provide the agreement-defined product value and origin/value for every component."
            elif not request.components or not criterion_evidence:
                explanation = "Provide a complete bill of materials and supporting valuation evidence."
            else:
                originating_value = sum(
                    (item.customs_value for item in request.components if item.origin_status == OriginatingStatus.ORIGINATING),
                    Decimal("0"),
                )
                non_originating_value = sum(
                    (item.customs_value for item in request.components if item.origin_status == OriginatingStatus.NON_ORIGINATING),
                    Decimal("0"),
                )
                if criterion.rvc_method == ValueMethod.BUILD_UP:
                    calculated_value = originating_value / request.product_value * 100
                else:
                    calculated_value = (request.product_value - non_originating_value) / request.product_value * 100
                status = "pass" if calculated_value >= criterion.rvc_threshold_pct else "fail"
                explanation = (
                    f"Calculated RVC {calculated_value:.2f}% using {criterion.rvc_method.value}; "
                    f"the supplied agreement threshold is {criterion.rvc_threshold_pct}%."
                )

        elif criterion.kind == CriterionKind.SPECIFIC_PROCESS:
            if criterion.specific_process_met is not None and criterion_evidence:
                status = "pass" if criterion.specific_process_met else "fail"
                explanation = "The supplied specific-process determination and evidence were applied."
            else:
                explanation = "Provide the required process determination and supporting production records."

        results.append(
            FTACriterionResult(
                kind=criterion.kind,
                status=status,
                explanation=explanation,
                calculated_value_pct=calculated_value,
                evidence_references=criterion_evidence,
            )
        )

    statuses = [result.status for result in results]
    if request.rule_effective_date > today:
        outcome = "insufficient_data"
        summary = "The cited rule is not effective yet; current qualification cannot be concluded."
    elif request.criteria_logic == "all":
        outcome = "not_qualified" if "fail" in statuses else "insufficient_data" if "unknown" in statuses else "qualified"
        summary = "Every required supplied criterion passed." if outcome == "qualified" else "At least one required criterion failed." if outcome == "not_qualified" else "At least one required criterion remains unverified."
    else:
        outcome = "qualified" if "pass" in statuses else "insufficient_data" if "unknown" in statuses else "not_qualified"
        summary = "At least one supplied alternative criterion passed." if outcome == "qualified" else "No supplied alternative criterion passed." if outcome == "not_qualified" else "No alternative passed and at least one remains unverified."

    return FTAAssessmentResult(
        agreement=request.agreement,
        destination=request.destination,
        origin_country=request.origin_country,
        product_hs6=request.product_hs6,
        status=outcome,
        rule_source=request.rule_source,
        rule_effective_date=request.rule_effective_date,
        rule_summary=request.rule_summary,
        criteria_results=results,
        explanation=summary,
        evidence_references=evidence,
    )


if __name__ == "__main__":
    from app.schemas.tariff import Component, FTACriterion, Market

    sample = FTAAssessmentRequest(
        agreement="Sample agreement",
        destination=Market.US,
        origin_country="MX",
        product_hs6="850760",
        rule_source="official agreement rule supplied by the caller",
        rule_effective_date=date(2025, 1, 1),
        rule_summary="Four-digit tariff shift",
        criteria=[FTACriterion(kind=CriterionKind.TARIFF_SHIFT, required_change_digits=4)],
        components=[Component(hs_code="730799", origin_status=OriginatingStatus.NON_ORIGINATING, evidence_references=["BOM-1"])],
        evidence_references=["production-record-1"],
    )
    assert evaluate_fta_origin(sample, today=date(2026, 1, 1)).status == "qualified"

