"""Validated arithmetic adapted from GenPark's savings audit method."""

from decimal import Decimal, ROUND_HALF_UP


def audit_tariff_engineering_savings(
    original_duty_rate_pct: float | Decimal,
    candidate_duty_rate_pct: float | Decimal,
    annual_import_volume_usd: float | Decimal,
) -> dict:
    original = Decimal(str(original_duty_rate_pct))
    candidate = Decimal(str(candidate_duty_rate_pct))
    annual_value = Decimal(str(annual_import_volume_usd))
    if not original.is_finite() or not candidate.is_finite() or not annual_value.is_finite():
        raise ValueError("Rates and import volume must be finite numbers")
    if not 0 <= original <= 100 or not 0 <= candidate <= 100:
        raise ValueError("Duty rates must be between 0 and 100 percent")
    if annual_value < 0:
        raise ValueError("Import volume cannot be negative")
    spread = max(Decimal("0"), original - candidate)
    savings = (annual_value * spread / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "annual_import_usd": float(annual_value),
        "duty_reduction_pct": float(spread),
        "annual_customs_savings_usd": float(savings),
        "roi_verdict": "SIGNIFICANT_CUSTOMS_ARBITRAGE" if savings > 10_000 else "LOW_IMPACT",
    }

