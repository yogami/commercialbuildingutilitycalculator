"""Master application engine orchestrating all modules and enforcing test gates."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from commercial_utility_calculator.domain.entities import (
    CostInvoice,
    Meter,
    MeterReading,
    PhysicalSpace,
    TenantLease,
)
from commercial_utility_calculator.domain.invariants import InvariantValidator
from commercial_utility_calculator.application.services.area_day_allocator import (
    AreaDayAllocator,
    AreaDayAllocationResult,
    LANDLORD_VACANCY_ID,
    LANDLORD_VACANCY_NAME,
    SpaceOccupancySlice,
)
from commercial_utility_calculator.application.services.cost_circle_allocator import (
    CostAllocationLine,
    CostCircleAllocator,
)


@dataclass
class TenantStatement:
    tenant_id: str
    tenant_name: str
    vat_opt_in: bool
    occupancy_slices: List[SpaceOccupancySlice]
    cost_lines: List[CostAllocationLine]
    total_net_eur: Decimal
    total_vat_eur: Decimal
    total_gross_eur: Decimal
    total_prepayments_eur: Decimal
    balance_due_eur: Decimal
    recommended_new_prepayment_eur: Decimal = Decimal("0.00")
    street_address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None


@dataclass
class EngineCalculationResult:
    billing_start: date
    billing_end: date
    area_result: AreaDayAllocationResult
    cost_lines: List[CostAllocationLine]
    tenant_statements: Dict[str, TenantStatement]
    invoices: List[CostInvoice]


class CommercialUtilityEngine:
    """Audit-proof deterministic calculation engine for commercial real estate."""

    def __init__(
        self,
        area_allocator: Optional[AreaDayAllocator] = None,
        cost_allocator: Optional[CostCircleAllocator] = None,
        validator: Optional[InvariantValidator] = None,
    ) -> None:
        self.area_allocator = area_allocator or AreaDayAllocator()
        self.cost_allocator = cost_allocator or CostCircleAllocator()
        self.validator = validator or InvariantValidator()

    def calculate(
        self,
        spaces: List[PhysicalSpace],
        meters: List[Meter],
        readings: List[MeterReading],
        leases: List[TenantLease],
        invoices: List[CostInvoice],
        billing_start: date,
        billing_end: date,
    ) -> EngineCalculationResult:
        area_result = self.area_allocator.calculate_area_days(spaces, leases, billing_start, billing_end)
        cost_lines = self._allocate_all_invoices(invoices, area_result, spaces, leases)

        self.validator.assert_all_invariants(
            area_result=area_result,
            cost_lines=cost_lines,
            spaces=spaces,
            invoices=invoices,
            meters=meters,
            readings=readings,
            billing_start=billing_start,
            billing_end=billing_end,
        )

        statements = self._build_tenant_statements(area_result, cost_lines, leases, billing_start, billing_end)

        return EngineCalculationResult(
            billing_start=billing_start,
            billing_end=billing_end,
            area_result=area_result,
            cost_lines=cost_lines,
            tenant_statements=statements,
            invoices=invoices,
        )

    def _allocate_all_invoices(
        self,
        invoices: List[CostInvoice],
        area_result: AreaDayAllocationResult,
        spaces: List[PhysicalSpace],
        leases: List[TenantLease],
    ) -> List[CostAllocationLine]:
        lines: List[CostAllocationLine] = []
        for inv in invoices:
            inv_lines = self.cost_allocator.allocate_invoice(inv, area_result, spaces, leases)
            lines.extend(inv_lines)
        return lines

    def _build_tenant_statements(
        self,
        area_result: AreaDayAllocationResult,
        cost_lines: List[CostAllocationLine],
        leases: List[TenantLease],
        billing_start: date,
        billing_end: date,
    ) -> Dict[str, TenantStatement]:
        statements: Dict[str, TenantStatement] = {}
        all_tenant_ids = set(area_result.tenant_shares.keys())

        for tid in all_tenant_ids:
            statement = self._build_single_statement(tid, area_result, cost_lines, leases, billing_start, billing_end)
            statements[tid] = statement

        return statements

    def _build_single_statement(
        self,
        tenant_id: str,
        area_result: AreaDayAllocationResult,
        cost_lines: List[CostAllocationLine],
        leases: List[TenantLease],
        billing_start: date,
        billing_end: date,
    ) -> TenantStatement:
        t_share = area_result.get_tenant_share(tenant_id)
        t_lines = [l for l in cost_lines if l.tenant_id == tenant_id]

        net_sum = sum((l.net_amount_eur for l in t_lines), Decimal("0.00"))
        vat_sum = sum((l.vat_amount_eur for l in t_lines), Decimal("0.00"))
        gross_sum = sum((l.gross_amount_eur for l in t_lines), Decimal("0.00"))

        tenant_name = self._resolve_tenant_name(tenant_id, t_share.tenant_name)
        vat_opt_in = self._resolve_vat_opt_in(tenant_id, leases)
        prepayments = self._calculate_tenant_prepayments(tenant_id, leases, billing_start, billing_end)

        billed_total = (net_sum + vat_sum) if vat_opt_in else gross_sum
        balance_due = billed_total - prepayments

        rec_prepay = (billed_total / Decimal("12.0")).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        matching_lease = next((l for l in leases if l.tenant_id == tenant_id), None)

        return TenantStatement(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            vat_opt_in=vat_opt_in,
            occupancy_slices=t_share.slices,
            cost_lines=t_lines,
            total_net_eur=net_sum,
            total_vat_eur=vat_sum,
            total_gross_eur=gross_sum,
            total_prepayments_eur=prepayments,
            balance_due_eur=balance_due,
            recommended_new_prepayment_eur=rec_prepay,
            street_address=matching_lease.street_address if matching_lease else None,
            postal_code=matching_lease.postal_code if matching_lease else None,
            city=matching_lease.city if matching_lease else None,
        )

    def _resolve_tenant_name(self, tenant_id: str, default_name: str) -> str:
        if tenant_id == LANDLORD_VACANCY_ID:
            return LANDLORD_VACANCY_NAME
        return default_name

    def _resolve_vat_opt_in(self, tenant_id: str, leases: List[TenantLease]) -> bool:
        if tenant_id == LANDLORD_VACANCY_ID:
            return True
        for l in leases:
            if l.tenant_id == tenant_id:
                return l.vat_opt_in
        return True

    def _calculate_tenant_prepayments(
        self,
        tenant_id: str,
        leases: List[TenantLease],
        billing_start: date,
        billing_end: date,
    ) -> Decimal:
        if tenant_id == LANDLORD_VACANCY_ID:
            return Decimal("0.00")

        total_prep = Decimal("0.00")
        year_days = Decimal((billing_end - billing_start).days + 1)

        for l in leases:
            if l.tenant_id == tenant_id:
                eff_start = max(l.start_date, billing_start)
                eff_end = min(l.end_date, billing_end)
                active_days = Decimal((eff_end - eff_start).days + 1)
                months_equiv = (active_days / year_days) * Decimal("12.0")
                total_prep += l.monthly_prepayment_eur * months_equiv

        return total_prep.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
