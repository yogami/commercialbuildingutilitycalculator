"""Tests for Phase 4: Meter hierarchy DAG, Vorwegabzug, and correction factors."""

from datetime import date
from decimal import Decimal
import pytest

from commercial_utility_calculator.domain.entities import Meter, MeterReading, PhysicalSpace
from commercial_utility_calculator.domain.enums import Medium, UsageType
from commercial_utility_calculator.application.services.meter_hierarchy_engine import (
    MeterHierarchyEngine,
    MeterBalanceReport,
    ConservationBreachError,
)
from commercial_utility_calculator.application.services.correction_factor_engine import (
    CorrectionFactorEngine,
    CorrectionResult,
    AnomalyThresholdExceededError,
)
from commercial_utility_calculator.application.services.vorwegabzug_engine import (
    VorwegabzugEngine,
    VorwegabzugResult,
)
from commercial_utility_calculator.application.services.monthly_reading_service import (
    MonthlyReadingService,
)


def test_meter_dag_and_residual_calculation() -> None:
    root = Meter(
        meter_id="M-ROOT",
        serial_number="SN-ROOT",
        medium=Medium.ELECTRICITY,
        parent_meter_id=None,
    )
    child1 = Meter(
        meter_id="M-SUB1",
        serial_number="SN-SUB1",
        medium=Medium.ELECTRICITY,
        parent_meter_id="M-ROOT",
        served_space_ids=["SP-101"],
    )
    child2 = Meter(
        meter_id="M-SUB2",
        serial_number="SN-SUB2",
        medium=Medium.ELECTRICITY,
        parent_meter_id="M-ROOT",
        served_space_ids=["SP-102"],
    )

    readings = [
        MeterReading(meter_id="M-ROOT", reading_date=date(2025, 1, 1), value=Decimal("10000.0")),
        MeterReading(meter_id="M-ROOT", reading_date=date(2025, 12, 31), value=Decimal("110000.0")),
        MeterReading(meter_id="M-SUB1", reading_date=date(2025, 1, 1), value=Decimal("1000.0")),
        MeterReading(meter_id="M-SUB1", reading_date=date(2025, 12, 31), value=Decimal("41000.0")),
        MeterReading(meter_id="M-SUB2", reading_date=date(2025, 1, 1), value=Decimal("5000.0")),
        MeterReading(meter_id="M-SUB2", reading_date=date(2025, 12, 31), value=Decimal("60000.0")),
    ]

    engine = MeterHierarchyEngine()
    report = engine.calculate_balances(
        meters=[root, child1, child2],
        readings=readings,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    # Root consumption = 100,000. Child1 = 40,000, Child2 = 55,000.
    # Residual = 100,000 - 95,000 = 5,000 kWh
    balance = report.get_balance("M-ROOT")
    assert balance.parent_consumption == Decimal("100000.0")
    assert balance.children_sum_consumption == Decimal("95000.0")
    assert balance.residual_unmetered_base_load == Decimal("5000.0")


def test_conservation_check_fails_when_children_exceed_parent() -> None:
    root = Meter(
        meter_id="M-ROOT",
        serial_number="SN-ROOT",
        medium=Medium.ELECTRICITY,
        parent_meter_id=None,
    )
    child = Meter(
        meter_id="M-CHILD",
        serial_number="SN-CHILD",
        medium=Medium.ELECTRICITY,
        parent_meter_id="M-ROOT",
    )

    readings = [
        MeterReading(meter_id="M-ROOT", reading_date=date(2025, 1, 1), value=Decimal("0.0")),
        MeterReading(meter_id="M-ROOT", reading_date=date(2025, 12, 31), value=Decimal("1000.0")),
        MeterReading(meter_id="M-CHILD", reading_date=date(2025, 1, 1), value=Decimal("0.0")),
        MeterReading(meter_id="M-CHILD", reading_date=date(2025, 12, 31), value=Decimal("1050.0")),
    ]

    engine = MeterHierarchyEngine()
    with pytest.raises(ConservationBreachError, match="exceeds parent"):
        engine.calculate_balances(
            meters=[root, child],
            readings=readings,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )


def test_correction_factor_scaling_within_threshold() -> None:
    # Drift = 3% (e.g. 100,000 root vs 97,000 children)
    # Threshold for electricity is 8.0%. Scaling should succeed.
    engine = CorrectionFactorEngine()
    result = engine.evaluate_and_adjust(
        medium=Medium.ELECTRICITY,
        parent_consumption=Decimal("100000.0"),
        children_consumptions={"M-1": Decimal("50000.0"), "M-2": Decimal("47000.0")},
    )

    assert result.action == "proportional_scaling"
    # factor = 100000 / 97000
    assert result.correction_factor > Decimal("1.0")
    # Assert raw numbers preserved side-by-side
    assert result.raw_consumptions["M-1"] == Decimal("50000.0")
    assert result.adjusted_consumptions["M-1"] > Decimal("50000.0")


def test_correction_factor_excess_routes_to_overhead() -> None:
    # 20% gap: 100,000 root vs 80,000 children. Exceeds 8% electricity threshold.
    engine = CorrectionFactorEngine()
    result = engine.evaluate_and_adjust(
        medium=Medium.ELECTRICITY,
        parent_consumption=Decimal("100000.0"),
        children_consumptions={"M-1": Decimal("40000.0"), "M-2": Decimal("40000.0")},
    )

    assert result.action == "overhead_reallocation"
    assert result.excess_overhead_consumption == Decimal("20000.0")
    # Children remain at raw values
    assert result.adjusted_consumptions["M-1"] == Decimal("40000.0")


def test_vorwegabzug_direct_deductions() -> None:
    # Utility invoice: 10,000 EUR for 50,000 kWh -> 0.20 EUR / kWh
    # Tenant 1 has dedicated meter: 20,000 kWh -> 4,000 EUR direct deduction
    # Tenant 2 has dedicated meter: 20,000 kWh -> 4,000 EUR direct deduction
    # Remaining unmetered pool: 10,000 kWh -> 2,000 EUR
    engine = VorwegabzugEngine()
    result = engine.calculate_vorwegabzug(
        total_invoice_amount=Decimal("10000.00"),
        total_grid_consumption=Decimal("50000.0"),
        dedicated_meter_consumptions={"T-1": Decimal("20000.0"), "T-2": Decimal("20000.0")},
    )

    assert result.cost_per_unit == Decimal("0.20")
    assert result.direct_deductions["T-1"] == Decimal("4000.00")
    assert result.direct_deductions["T-2"] == Decimal("4000.00")
    assert result.residual_pool_cost == Decimal("2000.00")
    assert result.residual_pool_consumption == Decimal("10000.0")


def test_monthly_reading_service_mid_month_split() -> None:
    # Monthly readings: June 1 = 10,000; June 30 = 13,000 -> 3,000 kWh delta
    # Tenant moves out on June 10 (10 days). Remaining 20 days is landlord vacancy.
    service = MonthlyReadingService()
    monthly_readings = {
        date(2025, 6, 1): Decimal("10000.0"),
        date(2025, 6, 30): Decimal("13000.0"),
    }
    split = service.split_monthly_consumption(
        monthly_readings=monthly_readings,
        month_start=date(2025, 6, 1),
        month_end=date(2025, 6, 30),
        split_date=date(2025, 6, 10),
    )

    # 10 days out of 30 days = 1/3 = 1,000 kWh
    # 20 days out of 30 days = 2/3 = 2,000 kWh
    assert split.period_1_consumption == Decimal("1000.0")
    assert split.period_2_consumption == Decimal("2000.0")
    assert split.period_1_consumption + split.period_2_consumption == Decimal("3000.0")


def test_vdi_2067_degree_day_promille_weight() -> None:
    service = MonthlyReadingService()
    # Entire non-leap year (2025) should sum to 1000 promille
    total_weight = service.get_vdi_weight_for_period(date(2025, 1, 1), date(2025, 12, 31))
    assert total_weight == Decimal("1000.00")

    # Winter months (January) should carry significant weight (170 promille)
    jan_weight = service.get_vdi_weight_for_period(date(2025, 1, 1), date(2025, 1, 31))
    assert jan_weight == Decimal("170.00")
