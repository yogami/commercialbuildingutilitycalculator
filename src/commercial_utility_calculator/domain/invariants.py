"""Domain invariants and automated verification gates."""

from datetime import date, timedelta
from decimal import Decimal
from typing import List

from commercial_utility_calculator.domain.entities import CostInvoice, Meter, MeterReading, PhysicalSpace
from commercial_utility_calculator.application.services.area_day_allocator import AreaDayAllocationResult
from commercial_utility_calculator.application.services.cost_circle_allocator import CostAllocationLine
from commercial_utility_calculator.application.services.meter_hierarchy_engine import MeterHierarchyEngine


class PennyBalanceBreachError(ValueError):
    """Raised when allocated cost sums do not match invoice totals to the exact cent."""
    pass


class AreaContinuityBreachError(ValueError):
    """Raised when the daily sum of allocated space does not match total physical building area."""
    pass


class NegativeValueBreachError(ValueError):
    """Raised when any negative cost, area, or consumption value is detected."""
    pass


class InvariantValidator:
    """The Hard Test Gates: Enforces statutory accounting and physics conservation invariants."""

    def assert_all_invariants(
        self,
        area_result: AreaDayAllocationResult,
        cost_lines: List[CostAllocationLine],
        spaces: List[PhysicalSpace],
        invoices: List[CostInvoice],
        meters: List[Meter],
        readings: List[MeterReading],
        billing_start: date,
        billing_end: date,
    ) -> None:
        self.assert_penny_balance(cost_lines, invoices)
        self.assert_area_continuity(area_result, spaces, billing_start, billing_end)
        self.assert_non_negative_allocations(cost_lines)
        if meters and readings:
            self.assert_meter_conservation(meters, readings, billing_start, billing_end)

    def assert_penny_balance(
        self,
        cost_lines: List[CostAllocationLine],
        invoices: List[CostInvoice],
    ) -> None:
        total_invoiced = sum((inv.net_amount_eur for inv in invoices), Decimal("0.00"))
        total_allocated = sum((line.net_amount_eur for line in cost_lines), Decimal("0.00"))

        if total_invoiced != total_allocated:
            discrepancy = total_allocated - total_invoiced
            raise PennyBalanceBreachError(
                f"Penny balance breached: allocated net {total_allocated} EUR != "
                f"invoiced net {total_invoiced} EUR (diff: {discrepancy} EUR)"
            )

    def assert_area_continuity(
        self,
        area_result: AreaDayAllocationResult,
        spaces: List[PhysicalSpace],
        billing_start: date,
        billing_end: date,
    ) -> None:
        total_physical_sqm = sum((s.area_sqm for s in spaces), Decimal("0.00"))
        day_count = (billing_end - billing_start).days + 1

        for day_offset in range(day_count):
            target_date = billing_start + timedelta(days=day_offset)
            day_sum = sum(
                (s.area_sqm for s in area_result.slices if s.start_date <= target_date <= s.end_date),
                Decimal("0.00"),
            )
            if day_sum != total_physical_sqm:
                raise AreaContinuityBreachError(
                    f"Area continuity breach on {target_date}: allocated {day_sum} m² != physical {total_physical_sqm} m²"
                )

    def assert_non_negative_allocations(self, lines: List[CostAllocationLine]) -> None:
        for line in lines:
            if line.net_amount_eur < Decimal("0.00"):
                raise NegativeValueBreachError(f"Negative net amount on line {line.invoice_id}: {line.net_amount_eur}")
            if line.billed_amount_eur < Decimal("0.00"):
                raise NegativeValueBreachError(f"Negative billed amount on line {line.invoice_id}: {line.billed_amount_eur}")
            if line.numerator_sqm_days < Decimal("0.00"):
                raise NegativeValueBreachError(f"Negative sqm-days on line {line.invoice_id}: {line.numerator_sqm_days}")

    def assert_meter_conservation(
        self,
        meters: List[Meter],
        readings: List[MeterReading],
        billing_start: date,
        billing_end: date,
    ) -> None:
        engine = MeterHierarchyEngine()
        engine.calculate_balances(meters, readings, billing_start, billing_end)
