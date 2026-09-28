"""Tests for Phase 1: Relational schemas and data validation layer."""

from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from commercial_utility_calculator.domain.entities import (
    CostInvoice,
    Meter,
    MeterReading,
    PhysicalSpace,
    TenantLease,
)
from commercial_utility_calculator.domain.enums import Medium, UsageType


def test_physical_space_valid() -> None:
    space = PhysicalSpace(
        space_id="SP-A-101",
        building_id="BLDG-A",
        floor=1,
        room_number="101",
        area_sqm=Decimal("150.50"),
        usage_type=UsageType.OFFICE,
        cost_circle_scope=["CAMPUS", "BLDG-A"],
    )
    assert space.space_id == "SP-A-101"
    assert space.area_sqm == Decimal("150.50")
    assert space.floor == 1


def test_physical_space_rejects_negative_area() -> None:
    with pytest.raises(ValidationError):
        PhysicalSpace(
            space_id="SP-A-102",
            building_id="BLDG-A",
            floor=1,
            room_number="102",
            area_sqm=Decimal("-10.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS"],
        )


def test_meter_valid_and_defaults() -> None:
    meter = Meter(
        meter_id="MTR-E-ROOT",
        serial_number="SN-778899",
        medium=Medium.ELECTRICITY,
        parent_meter_id=None,
        served_space_ids=[],
        unit="kWh",
    )
    assert meter.parent_meter_id is None
    assert meter.multiplier == Decimal("1.0")
    assert not meter.is_bidirectional_solar


def test_meter_reading_rejects_negative_value() -> None:
    with pytest.raises(ValidationError):
        MeterReading(
            meter_id="MTR-E-ROOT",
            reading_date=date(2025, 1, 1),
            value=Decimal("-50.0"),
        )


def test_tenant_lease_date_validation() -> None:
    with pytest.raises(ValidationError):
        TenantLease(
            lease_id="L-001",
            tenant_id="T-001",
            tenant_name="Alpha Tech GmbH",
            space_id="SP-A-101",
            start_date=date(2025, 12, 31),
            end_date=date(2025, 1, 1),
            vat_opt_in=True,
            monthly_prepayment_eur=Decimal("500.00"),
        )


def test_tenant_lease_valid() -> None:
    lease = TenantLease(
        lease_id="L-001",
        tenant_id="T-001",
        tenant_name="Alpha Tech GmbH",
        space_id="SP-A-101",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        vat_opt_in=True,
        monthly_prepayment_eur=Decimal("500.00"),
    )
    assert lease.tenant_name == "Alpha Tech GmbH"
    assert lease.vat_opt_in is True


def test_cost_invoice_vat_calculation_consistency() -> None:
    invoice = CostInvoice(
        invoice_id="INV-2025-01",
        cost_category="Allgemeinstrom",
        asset_id=None,
        net_amount_eur=Decimal("1000.00"),
        vat_rate_percent=Decimal("19.0"),
        gross_amount_eur=Decimal("1190.00"),
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
        cost_circle_scope="CAMPUS",
    )
    assert invoice.net_amount_eur == Decimal("1000.00")
    assert invoice.gross_amount_eur == Decimal("1190.00")


def test_cost_invoice_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError):
        CostInvoice(
            invoice_id="INV-2025-02",
            cost_category="Grundsteuer",
            asset_id=None,
            net_amount_eur=Decimal("-500.00"),
            vat_rate_percent=Decimal("0.0"),
            gross_amount_eur=Decimal("-500.00"),
            billing_start=date(2025, 1, 1),
            billing_end=date(2025, 12, 31),
            cost_circle_scope="BLDG-A",
        )
