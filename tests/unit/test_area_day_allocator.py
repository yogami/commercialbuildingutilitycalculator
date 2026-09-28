"""Tests for Phase 2: Time-weighted area-day calculator (m²-Tage / Unterjährige Flächenänderungen)."""

from datetime import date
from decimal import Decimal
import pytest

from commercial_utility_calculator.domain.entities import PhysicalSpace, TenantLease
from commercial_utility_calculator.domain.enums import UsageType
from commercial_utility_calculator.application.services.area_day_allocator import (
    AreaDayAllocator,
    SpaceOccupancySlice,
)


@pytest.fixture
def sample_spaces() -> list[PhysicalSpace]:
    return [
        PhysicalSpace(
            space_id="SP-101",
            building_id="BLDG-1",
            floor=1,
            room_number="101",
            area_sqm=Decimal("100.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-1"],
        ),
        PhysicalSpace(
            space_id="SP-102",
            building_id="BLDG-1",
            floor=1,
            room_number="102",
            area_sqm=Decimal("200.00"),
            usage_type=UsageType.OFFICE,
            cost_circle_scope=["CAMPUS", "BLDG-1"],
        ),
    ]


def test_full_year_occupancy_no_vacancy(sample_spaces: list[PhysicalSpace]) -> None:
    leases = [
        TenantLease(
            lease_id="L-1",
            tenant_id="T-1",
            tenant_name="Tenant One GmbH",
            space_id="SP-101",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
        ),
        TenantLease(
            lease_id="L-2",
            tenant_id="T-2",
            tenant_name="Tenant Two AG",
            space_id="SP-102",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=False,
        ),
    ]

    allocator = AreaDayAllocator()
    result = allocator.calculate_area_days(
        spaces=sample_spaces,
        leases=leases,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )

    # 365 days in 2025
    assert result.total_days == 365
    assert result.total_sqm_days == Decimal("300.00") * Decimal("365")  # 109,500
    assert result.vacancy_sqm_days == Decimal("0.00")

    # Tenant 1: 100 sqm * 365 = 36,500
    t1_share = result.get_tenant_share("T-1")
    assert t1_share.total_sqm_days == Decimal("36500.00")

    # Tenant 2: 200 sqm * 365 = 73,000
    t2_share = result.get_tenant_share("T-2")
    assert t2_share.total_sqm_days == Decimal("73000.00")


def test_mid_year_move_with_vacancy_absorption(sample_spaces: list[PhysicalSpace]) -> None:
    # Space 101 occupied only until June 30 (181 days). Remainder is vacant (184 days).
    # Space 102 occupied all year.
    leases = [
        TenantLease(
            lease_id="L-1",
            tenant_id="T-1",
            tenant_name="Tenant One GmbH",
            space_id="SP-101",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
            vat_opt_in=True,
        ),
        TenantLease(
            lease_id="L-2",
            tenant_id="T-2",
            tenant_name="Tenant Two AG",
            space_id="SP-102",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=False,
        ),
    ]

    allocator = AreaDayAllocator()
    result = allocator.calculate_area_days(
        spaces=sample_spaces,
        leases=leases,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )

    # 181 days * 100 = 18,100 sqm-days for T-1
    t1_share = result.get_tenant_share("T-1")
    assert t1_share.total_sqm_days == Decimal("18100.00")

    # 184 days * 100 = 18,400 sqm-days for Landlord vacancy
    landlord_share = result.get_landlord_vacancy_share()
    t2_share = result.get_tenant_share("T-2")
    assert landlord_share.total_sqm_days == Decimal("18400.00")

    # Invariant: tenant sqm-days + landlord vacancy sqm-days == total physical sqm-days
    total_expected = Decimal("300.00") * Decimal("365")
    assert t1_share.total_sqm_days + t2_share.total_sqm_days + landlord_share.total_sqm_days == total_expected


def test_area_continuity_invariant_daily_check(sample_spaces: list[PhysicalSpace]) -> None:
    # Mid-year expansion: Tenant 1 is in SP-101 all year.
    # Tenant 1 also expands into SP-102 on July 1 (vacant Jan 1 to June 30).
    leases = [
        TenantLease(
            lease_id="L-1A",
            tenant_id="T-1",
            tenant_name="Tenant One GmbH",
            space_id="SP-101",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
        ),
        TenantLease(
            lease_id="L-1B",
            tenant_id="T-1",
            tenant_name="Tenant One GmbH",
            space_id="SP-102",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=True,
        ),
    ]

    allocator = AreaDayAllocator()
    result = allocator.calculate_area_days(
        spaces=sample_spaces,
        leases=leases,
        billing_start=date(2025, 1, 1),
        billing_end=date(2025, 12, 31),
    )

    # Assert daily continuity invariant
    allocator.assert_daily_area_continuity(result, sample_spaces, date(2025, 1, 1), date(2025, 12, 31))


def test_overlapping_leases_rejected(sample_spaces: list[PhysicalSpace]) -> None:
    # Two active leases for SP-101 at the same time
    leases = [
        TenantLease(
            lease_id="L-1",
            tenant_id="T-1",
            tenant_name="Tenant One GmbH",
            space_id="SP-101",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 8, 31),
            vat_opt_in=True,
        ),
        TenantLease(
            lease_id="L-2",
            tenant_id="T-2",
            tenant_name="Tenant Two AG",
            space_id="SP-101",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 12, 31),
            vat_opt_in=False,
        ),
    ]

    allocator = AreaDayAllocator()
    with pytest.raises(ValueError, match="overlapping|Overlap"):
        allocator.calculate_area_days(
            spaces=sample_spaces,
            leases=leases,
            billing_start=date(2025, 1, 1),
            billing_end=date(2025, 12, 31),
        )
