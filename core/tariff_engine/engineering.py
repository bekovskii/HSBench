"""Conservative assembled versus unassembled duty comparison."""

from decimal import Decimal

from app.schemas.tariff import TariffEngineeringRequest, TariffEngineeringResult
from core.duty_lookup import lookup_hs6
from core.tariff_engine.savings import audit_tariff_engineering_savings


def compare_assembled_unassembled(request: TariffEngineeringRequest) -> TariffEngineeringResult:
    assembled = lookup_hs6(request.assembled_hs6)
    unassembled = lookup_hs6(request.unassembled_hs6)
    assembled_rate = _rate(assembled, request.destination.value)
    unassembled_rate = _rate(unassembled, request.destination.value)
    verified_on = _verified_date(assembled, unassembled)

    if request.presented_unassembled and request.complete_article_or_essential_character_supported is True:
        same_rate = assembled_rate
        return TariffEngineeringResult(
            status="no_saving",
            assembled_hs6=request.assembled_hs6,
            unassembled_hs6=request.assembled_hs6,
            destination=request.destination,
            assembled_mfn_pct=same_rate,
            unassembled_mfn_pct=same_rate,
            annual_import_value=request.annual_import_value,
            currency=request.currency,
            potential_savings=Decimal("0.00"),
            explanation=(
                "The supplied facts indicate that GRI 2(a) may classify the unassembled presentation "
                "as the complete article. The rate comparison therefore uses the assembled article's HS6; "
                "a customs specialist must confirm the legal facts and applicable notes."
            ),
            data_verified_on=verified_on,
        )

    if request.presented_unassembled and request.complete_article_or_essential_character_supported is None:
        explanation = "GRI 2(a) facts are unresolved; provide the presentation, completeness, and essential-character evidence."
    elif assembled_rate is None or unassembled_rate is None:
        explanation = "One or both HS6 codes are outside the bundled sample tariff; no rate or savings estimate is available."
    elif request.assembled_hs6 != request.unassembled_hs6 and not request.alternative_classifications_verified:
        explanation = "Different classifications need official supporting sources before their rates can be compared as a scenario."
    else:
        audit = audit_tariff_engineering_savings(
            assembled_rate, unassembled_rate, request.annual_import_value
        )
        savings = Decimal(str(audit["annual_customs_savings_usd"]))
        status = "potential_saving" if savings > 0 else "no_saving"
        return TariffEngineeringResult(
            status=status,
            assembled_hs6=request.assembled_hs6,
            unassembled_hs6=request.unassembled_hs6,
            destination=request.destination,
            assembled_mfn_pct=assembled_rate,
            unassembled_mfn_pct=unassembled_rate,
            annual_import_value=request.annual_import_value,
            currency=request.currency,
            potential_savings=savings,
            explanation=(
                "Indicative arithmetic only, based on the bundled sample rates and supplied verified classifications. "
                "This does not establish tariff-engineering legality or customs treatment."
            ),
            data_verified_on=verified_on,
        )

    return TariffEngineeringResult(
        status="review_required",
        assembled_hs6=request.assembled_hs6,
        unassembled_hs6=request.unassembled_hs6,
        destination=request.destination,
        assembled_mfn_pct=assembled_rate,
        unassembled_mfn_pct=unassembled_rate,
        annual_import_value=request.annual_import_value,
        currency=request.currency,
        potential_savings=None,
        explanation=explanation,
        data_verified_on=verified_on,
    )


def _rate(row: dict[str, str] | None, destination: str) -> Decimal | None:
    raw = row.get(f"{destination.lower()}_mfn_pct") if row else None
    return Decimal(raw) if raw else None


def _verified_date(*rows: dict[str, str] | None):
    dates = [row["last_verified"] for row in rows if row and row.get("last_verified")]
    if not dates:
        return None
    from datetime import date

    return min(date.fromisoformat(value) for value in dates)


if __name__ == "__main__":
    from app.schemas.tariff import Market

    sample = TariffEngineeringRequest(
        assembled_hs6="610910",
        unassembled_hs6="010612",
        destination=Market.US,
        annual_import_value=Decimal("1000"),
        presented_unassembled=False,
        alternative_classifications_verified=True,
        classification_sources=["official classification source"],
    )
    assert compare_assembled_unassembled(sample).potential_savings == Decimal("165.0")
    gri_2a = TariffEngineeringRequest(
        assembled_hs6="610910",
        unassembled_hs6="010612",
        destination=Market.US,
        annual_import_value=Decimal("1000"),
        presented_unassembled=True,
        complete_article_or_essential_character_supported=True,
        evidence_references=["entry presentation record"],
    )
    assert compare_assembled_unassembled(gri_2a).potential_savings == Decimal("0.00")

