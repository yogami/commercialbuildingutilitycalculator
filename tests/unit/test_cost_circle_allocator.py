"""Tests for Phase 3: Multi-building cost circle allocator with variable asset scopes."""

from datetime import date
from decimal import Decimal
import pytest

from commercial_utility_calculator.domain.entities import CostInvoice, PhysicalSpace, TenantLease
from commercial_utility_calculator.domain.enums import UsageType
from commercial_utility_calculator.application.services.area_day_allocator import AreaDayAllocator
from commercial_utility_calculator.application.services.cost_circle_allocator import (
    CostCircleAllocator,
    CostAllocationLine,
)


@pytest.fixture
def multi_bldg_spaces() -> list[PhysicalSpace]:
    return [
        PhysicalSpace(
            space_id="SP-101",
            building_id="BLDG-1",
            floor=2,
            room_number="101",
            area_sqm=Decimal("100.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-1", "ELEVATOR-BLDG1"],
        ),
        PhysicalSpace(
            space_id="SP-102",
            building_id="BLDG-1",
            floor=3,
            room_number="102",
            area_sqm=Decimal("100.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-1", "ELEVATOR-BLDG1"],
        ),
        PhysicalSpace(
            space_id="SP-201",
            building_id="BLDG-2",
            floor=1,
            room_number="201",
            area_sqm=Decimal("200.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-2"],  # No elevator
        ),
    ]


@pytest.fixture
def leases() -> list[TenantLease]:
    return [
        TenantLease(
            lease_id="L-A",
            tenant_id="T-A",
            tenant_name="Tech A GmbH",
            space_id="SP-101",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
        ),
        TenantLease(
            lease_id="L-B",
            tenant_id="T-B",
            tenant_name="Doctor B (Praxis)",
            space_id="SP-102",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=False,  # VAT-exempt medical practice
        ),
        TenantLease(
            lease_id="L-C",
            tenant_id="T-C",
            tenant_name="Consulting C GmbH",
            space_id="SP-201",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
        ),
    ]


def test_elevator_cost_circle_isolated_to_building_1(
    multi_bldg_spaces: list[PhysicalSpace], leases: list[TenantLease]
) -> None:
    area_allocator = AreaDayAllocator()
    area_result = area_allocator.calculate_area_days(
        spaces=multi_bldg_spaces,
        leases=leases,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )

    elevator_invoice = CostInvoice(
        invoice_id="INV-ELEV-1",
        cost_category="Aufzugswartung",
        asset_id="ASSET-ELEV-B1",
        net_amount_eur=Decimal("1200.00"),
        vat_rate_percent=Decimal("19.0"),
        gross_amount_eur=Decimal("1428.00"),
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
        cost_circle_scope="ELEVATOR-BLDG1",
    )

    cost_allocator = CostCircleAllocator()
    allocations = cost_allocator.allocate_invoice(
        invoice=elevator_invoice,
        area_result=area_result,
        spaces=multi_bldg_spaces,
        leases=leases,
    )

    # Only T-A and T-B should participate (SP-101 and SP-102, 100 sqm each = 50% / 50%)
    # T-C in BLDG-2 must be 0 EUR!
    t_a_alloc = [a for a in allocations if a.tenant_id == "T-A"]
    t_b_alloc = [a for a in allocations if a.tenant_id == "T-B"]
    t_c_alloc = [a for a in allocations if a.tenant_id == "T-C"]

    assert len(t_a_alloc) == 1
    assert len(t_b_alloc) == 1
    assert len(t_c_alloc) == 0

    assert t_a_alloc[0].net_amount_eur == Decimal("600.00")
    assert t_b_alloc[0].net_amount_eur == Decimal("600.00")

    # VAT check: T-A is opted in (19% VAT = 114.00, Gross = 714.00)
    assert t_a_alloc[0].vat_opt_in is True
    assert t_a_alloc[0].vat_amount_eur == Decimal("114.00")
    assert t_a_alloc[0].billed_amount_eur == Decimal("714.00")

    # T-B is exempt (Gross cost billed directly: 600.00 + 114.00 input tax = 714.00)
    assert t_b_alloc[0].vat_opt_in is False
    assert t_b_alloc[0].billed_amount_eur == Decimal("714.00")


def test_campus_wide_cost_circle(
    multi_bldg_spaces: list[PhysicalSpace], leases: list[TenantLease]
) -> None:
    area_allocator = AreaDayAllocator()
    area_result = area_allocator.calculate_area_days(
        spaces=multi_bldg_spaces,
        leases=leases,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )

    campus_invoice = CostInvoice(
        invoice_id="INV-SPRINKLER",
        cost_category="Sprinkleranlage",
        asset_id="ASSET-SPRINKLER",
        net_amount_eur=Decimal("4000.00"),
        vat_rate_percent=Decimal("19.0"),
        gross_amount_eur=Decimal("4760.00"),
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
        cost_circle_scope="CAMPUS",
    )

    cost_allocator = CostCircleAllocator()
    allocations = cost_allocator.allocate_invoice(
        invoice=campus_invoice,
        area_result=area_result,
        spaces=multi_bldg_spaces,
        leases=leases,
    )

    # Total area = 400 sqm. T-A = 100 sqm (25%), T-B = 100 sqm (25%), T-C = 200 sqm (50%)
    t_a_alloc = next(a for a in allocations if a.tenant_id == "T-A")
    t_b_alloc = next(a for a in allocations if a.tenant_id == "T-B")
    t_c_alloc = next(a for a in allocations if a.tenant_id == "T-C")

    assert t_a_alloc.net_amount_eur == Decimal("1000.00")
    assert t_b_alloc.net_amount_eur == Decimal("1000.00")
    assert t_c_alloc.net_amount_eur == Decimal("2000.00")

    # Penny balance invariant: sum of net amounts == invoice net amount
    total_net_allocated = sum((a.net_amount_eur for a in allocations), Decimal("0.00"))
    assert total_net_allocated == campus_invoice.net_amount_eur


def test_penny_balance_rounding_exact() -> None:
    # 3 spaces of equal 100 sqm each, invoice = 100.00 EUR net
    # Apportionment must yield exactly 33.33, 33.33, 33.34 summing to 100.00 EUR
    spaces = [
        PhysicalSpace(
            space_id=f"SP-{i}",
            building_id="BLDG-1",
            floor=1,
            room_number=f"10{i}",
            area_sqm=Decimal("100.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS"],
        )
        for i in range(1, 4)
    ]
    leases = [
        TenantLease(
            lease_id=f"L-{i}",
            tenant_id=f"T-{i}",
            tenant_name=f"Tenant {i}",
            space_id=f"SP-{i}",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
        )
        for i in range(1, 4)
    ]

    area_allocator = AreaDayAllocator()
    area_result = area_allocator.calculate_area_days(
        spaces=spaces,
        leases=leases,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )

    invoice = CostInvoice(
        invoice_id="INV-ODD",
        cost_category="Muellabfuhr",
        net_amount_eur=Decimal("100.00"),
        vat_rate_percent=Decimal("0.0"),
        gross_amount_eur=Decimal("100.00"),
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
        cost_circle_scope="CAMPUS",
    )

    cost_allocator = CostCircleAllocator()
    allocations = cost_allocator.allocate_invoice(
        invoice=invoice,
        area_result=area_result,
        spaces=spaces,
        leases=leases,
    )

    net_sum = sum((a.net_amount_eur for a in allocations), Decimal("0.00"))
    assert net_sum == Decimal("100.00")
    amounts = sorted([a.net_amount_eur for a in allocations])
    assert amounts == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
