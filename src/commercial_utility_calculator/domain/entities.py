"""Domain entities for commercial utility and cost allocation."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from commercial_utility_calculator.domain.enums import Medium, UsageType


class PhysicalSpace(BaseModel):
    model_config = ConfigDict(frozen=True)

    space_id: str = Field(..., min_length=1)
    building_id: str = Field(..., min_length=1)
    floor: int
    room_number: str
    area_sqm: Decimal = Field(..., gt=Decimal("0.0"))
    usage_type: UsageType
    cost_circle_scope: List[str] = Field(default_factory=list)


class Meter(BaseModel):
    model_config = ConfigDict(frozen=True)

    meter_id: str = Field(..., min_length=1)
    serial_number: str = Field(..., min_length=1)
    medium: Medium
    parent_meter_id: Optional[str] = None
    served_space_ids: List[str] = Field(default_factory=list)
    is_bidirectional_solar: bool = False
    multiplier: Decimal = Field(default=Decimal("1.0"), gt=Decimal("0.0"))
    unit: str = "kWh"


class MeterReading(BaseModel):
    model_config = ConfigDict(frozen=True)

    meter_id: str = Field(..., min_length=1)
    reading_date: date
    value: Decimal = Field(..., ge=Decimal("0.0"))


class TenantLease(BaseModel):
    model_config = ConfigDict(frozen=True)

    lease_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    tenant_name: str = Field(..., min_length=1)
    space_id: str = Field(..., min_length=1)
    start_date: date
    end_date: date
    vat_opt_in: bool = True
    monthly_prepayment_eur: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    street_address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    vat_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "TenantLease":
        if self.end_date < self.start_date:
            raise ValueError(f"end_date {self.end_date} cannot be before start_date {self.start_date}")
        return self


class CostInvoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    invoice_id: str = Field(..., min_length=1)
    cost_category: str = Field(..., min_length=1)
    asset_id: Optional[str] = None
    net_amount_eur: Decimal = Field(..., ge=Decimal("0.00"))
    vat_rate_percent: Decimal = Field(default=Decimal("19.0"), ge=Decimal("0.00"))
    gross_amount_eur: Decimal = Field(..., ge=Decimal("0.00"))
    billing_start: date
    billing_end: date
    cost_circle_scope: str = "CAMPUS"

    @model_validator(mode="after")
    def validate_dates(self) -> "CostInvoice":
        if self.billing_end < self.billing_start:
            raise ValueError(f"billing_end {self.billing_end} cannot be before billing_start {self.billing_start}")
        return self
