"""Module D: Hybrid metering and direct deductions (Vorwegabzug)."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict


@dataclass(frozen=True)
class VorwegabzugResult:
    cost_per_unit: Decimal
    direct_deductions: Dict[str, Decimal]
    residual_pool_consumption: Decimal
    residual_pool_cost: Decimal


class VorwegabzugEngine:
    """Executes Vorwegabzug by deducting submetered consumption first before apportioning residual pools."""

    def calculate_vorwegabzug(
        self,
        total_invoice_amount: Decimal,
        total_grid_consumption: Decimal,
        dedicated_meter_consumptions: Dict[str, Decimal],
    ) -> VorwegabzugResult:
        if total_grid_consumption <= Decimal("0.0"):
            return self._build_empty_result(total_invoice_amount)

        cost_per_unit = total_invoice_amount / total_grid_consumption
        deductions = self._calculate_deductions(dedicated_meter_consumptions, cost_per_unit)

        total_deductions = sum(deductions.values(), Decimal("0.00"))
        total_dedicated_cons = sum(dedicated_meter_consumptions.values(), Decimal("0.0"))

        residual_cons = total_grid_consumption - total_dedicated_cons
        residual_cost = total_invoice_amount - total_deductions

        return VorwegabzugResult(
            cost_per_unit=cost_per_unit.quantize(Decimal("0.0001")),
            direct_deductions=deductions,
            residual_pool_consumption=residual_cons,
            residual_pool_cost=residual_cost.quantize(Decimal("0.01")),
        )

    def _build_empty_result(self, total_invoice_amount: Decimal) -> VorwegabzugResult:
        return VorwegabzugResult(
            cost_per_unit=Decimal("0.00"),
            direct_deductions={},
            residual_pool_consumption=Decimal("0.0"),
            residual_pool_cost=total_invoice_amount,
        )

    def _calculate_deductions(
        self, dedicated_consumptions: Dict[str, Decimal], cost_per_unit: Decimal
    ) -> Dict[str, Decimal]:
        deductions: Dict[str, Decimal] = {}
        for entity_id, consumption in dedicated_consumptions.items():
            deduction = consumption * cost_per_unit
            deductions[entity_id] = deduction.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return deductions
