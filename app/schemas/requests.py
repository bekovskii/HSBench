"""API request models composed from the canonical application contracts."""

from pydantic import Field

from app.schemas.classification import StrictModel
from app.schemas.tariff import FTAAssessmentRequest, Market, TariffEngineeringRequest


class ProductClassificationRequest(StrictModel):
    product_description: str = Field(min_length=3, max_length=4000)
    material_composition: list[str] = Field(default_factory=list, max_length=30)
    primary_function: str | None = Field(default=None, max_length=500)
    form_and_packaging: str | None = Field(default=None, max_length=500)
    destination: Market | None = None
    annual_import_value: float | None = Field(default=None, ge=0)
    fta_assessment: FTAAssessmentRequest | None = None
    tariff_engineering: TariffEngineeringRequest | None = None

