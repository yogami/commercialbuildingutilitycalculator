"""Module C: Technical correction factors (Angleichungsfaktor)."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from commercial_utility_calculator.domain.enums import Medium


class AnomalyThresholdExceededError(ValueError):
    """Raised when technical drift exceeds statutory tolerance thresholds."""
    pass


@dataclass(frozen=True)
class CorrectionResult:
    medium: Medium
    action: str
    parent_consumption: Decimal
    children_sum_consumption: Decimal
    drift_percentage: Decimal
    correction_factor: Decimal
    raw_consumptions: Dict[str, Decimal]
    adjusted_consumptions: Dict[str, Decimal]
    excess_overhead_consumption: Decimal


class CorrectionFactorEngine:
    """Evaluates drift between parent meters and child meters, applying scaling or overhead routing."""

    THRESHOLD_ELECTRICITY = Decimal("8.0")
    THRESHOLD_WATER_HEAT = Decimal("10.0")

    def evaluate_and_adjust(
        self,
        medium: Medium,
        parent_consumption: Decimal,
        children_consumptions: Dict[str, Decimal],
    ) -> CorrectionResult:
        children_sum = sum(children_consumptions.values(), Decimal("0.0"))
        if parent_consumption == Decimal("0.0") or children_sum == Decimal("0.0"):
            return self._build_identity_result(medium, parent_consumption, children_consumptions)

        gap = parent_consumption - children_sum
        drift_pct = (gap / parent_consumption) * Decimal("100.0")
        max_threshold = self._get_threshold_for_medium(medium)

        if drift_pct <= max_threshold:
            return self._apply_proportional_scaling(
                medium, parent_consumption, children_sum, drift_pct, children_consumptions
            )
        return self._route_to_overhead(
            medium, parent_consumption, children_sum, drift_pct, gap, children_consumptions
        )

    def _get_threshold_for_medium(self, medium: Medium) -> Decimal:
        if medium == Medium.ELECTRICITY:
            return self.THRESHOLD_ELECTRICITY
        return self.THRESHOLD_WATER_HEAT

    def _build_identity_result(
        self,
        medium: Medium,
        parent_cons: Decimal,
        children: Dict[str, Decimal],
    ) -> CorrectionResult:
        return CorrectionResult(
            medium=medium,
            action="identity",
            parent_consumption=parent_cons,
            children_sum_consumption=sum(children.values(), Decimal("0.0")),
            drift_percentage=Decimal("0.0"),
            correction_factor=Decimal("1.0"),
            raw_consumptions=dict(children),
            adjusted_consumptions=dict(children),
            excess_overhead_consumption=Decimal("0.0"),
        )

    def _apply_proportional_scaling(
        self,
        medium: Medium,
        parent_cons: Decimal,
        children_sum: Decimal,
        drift_pct: Decimal,
        children: Dict[str, Decimal],
    ) -> CorrectionResult:
        factor = parent_cons / children_sum
        adjusted = {cid: val * factor for cid, val in children.items()}
        return CorrectionResult(
            medium=medium,
            action="proportional_scaling",
            parent_consumption=parent_cons,
            children_sum_consumption=children_sum,
            drift_percentage=drift_pct,
            correction_factor=factor,
            raw_consumptions=dict(children),
            adjusted_consumptions=adjusted,
            excess_overhead_consumption=Decimal("0.0"),
        )

    def _route_to_overhead(
        self,
        medium: Medium,
        parent_cons: Decimal,
        children_sum: Decimal,
        drift_pct: Decimal,
        gap: Decimal,
        children: Dict[str, Decimal],
    ) -> CorrectionResult:
        return CorrectionResult(
            medium=medium,
            action="overhead_reallocation",
            parent_consumption=parent_cons,
            children_sum_consumption=children_sum,
            drift_percentage=drift_pct,
            correction_factor=Decimal("1.0"),
            raw_consumptions=dict(children),
            adjusted_consumptions=dict(children),
            excess_overhead_consumption=gap,
        )
