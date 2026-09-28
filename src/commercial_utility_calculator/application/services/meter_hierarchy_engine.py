"""Module B: Meter hierarchy DAG and anomaly balances (Zählerbaum & Differenzmessung)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
import networkx as nx

from commercial_utility_calculator.domain.entities import Meter, MeterReading


class ConservationBreachError(ValueError):
    """Raised when child meters exceed parent meter consumption beyond physics tolerances."""
    pass


@dataclass(frozen=True)
class MeterBalance:
    parent_meter_id: str
    parent_consumption: Decimal
    children_sum_consumption: Decimal
    residual_unmetered_base_load: Decimal


@dataclass
class MeterBalanceReport:
    balances: Dict[str, MeterBalance]

    def get_balance(self, parent_meter_id: str) -> MeterBalance:
        return self.balances[parent_meter_id]


class MeterHierarchyEngine:
    """Builds meter DAG, validates physical conservation, and calculates unmetered residual base loads."""

    def calculate_balances(
        self,
        meters: List[Meter],
        readings: List[MeterReading],
        start_date: date,
        end_date: date,
    ) -> MeterBalanceReport:
        graph = self._build_meter_dag(meters)
        consumption_map = self._calculate_meter_consumptions(meters, readings, start_date, end_date)
        balances = self._evaluate_hierarchy_balances(meters, graph, consumption_map)
        return MeterBalanceReport(balances=balances)

    def _build_meter_dag(self, meters: List[Meter]) -> nx.DiGraph:
        dag = nx.DiGraph()
        for meter in meters:
            dag.add_node(meter.meter_id, meter=meter)
            if meter.parent_meter_id:
                dag.add_edge(meter.parent_meter_id, meter.meter_id)
        if not nx.is_directed_acyclic_graph(dag):
            raise ValueError("Cyclic dependency detected in meter hierarchy!")
        return dag

    def _calculate_meter_consumptions(
        self,
        meters: List[Meter],
        readings: List[MeterReading],
        start_date: date,
        end_date: date,
    ) -> Dict[str, Decimal]:
        consumptions: Dict[str, Decimal] = {}
        for meter in meters:
            start_val = self._find_reading_value(readings, meter.meter_id, start_date)
            end_val = self._find_reading_value(readings, meter.meter_id, end_date)
            delta = (end_val - start_val) * meter.multiplier
            consumptions[meter.meter_id] = delta
        return consumptions

    def _find_reading_value(self, readings: List[MeterReading], meter_id: str, target_date: date) -> Decimal:
        matches = [r for r in readings if r.meter_id == meter_id and r.reading_date == target_date]
        if not matches:
            raise ValueError(f"Missing meter reading for meter {meter_id} on {target_date}")
        return matches[0].value

    def _evaluate_hierarchy_balances(
        self,
        meters: List[Meter],
        graph: nx.DiGraph,
        consumption_map: Dict[str, Decimal],
    ) -> Dict[str, MeterBalance]:
        balances: Dict[str, MeterBalance] = {}
        meter_lookup = {m.meter_id: m for m in meters}

        for meter_id in graph.nodes:
            children_ids = list(graph.successors(meter_id))
            if not children_ids:
                continue
            parent_meter = meter_lookup[meter_id]
            balance = self._calculate_single_balance(parent_meter, children_ids, consumption_map)
            balances[meter_id] = balance

        return balances

    def _calculate_single_balance(
        self,
        parent_meter: Meter,
        children_ids: List[str],
        consumption_map: Dict[str, Decimal],
    ) -> MeterBalance:
        parent_cons = consumption_map[parent_meter.meter_id]
        children_sum = sum((consumption_map[cid] for cid in children_ids), Decimal("0.0"))

        if children_sum > parent_cons and not parent_meter.is_bidirectional_solar:
            raise ConservationBreachError(
                f"Conservation breach on meter {parent_meter.meter_id}: "
                f"children sum {children_sum} exceeds parent {parent_cons}"
            )

        residual = parent_cons - children_sum
        return MeterBalance(
            parent_meter_id=parent_meter.meter_id,
            parent_consumption=parent_cons,
            children_sum_consumption=children_sum,
            residual_unmetered_base_load=residual,
        )
