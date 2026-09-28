"""Module E: Multi-building cost circles (Mehrhausanlagen-Umlage nach Kostenkreisen)."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Set, Tuple

from commercial_utility_calculator.domain.entities import CostInvoice, PhysicalSpace, TenantLease
from commercial_utility_calculator.application.services.area_day_allocator import (
    AreaDayAllocationResult,
    LANDLORD_VACANCY_ID,
    LANDLORD_VACANCY_NAME,
    SpaceOccupancySlice,
)


@dataclass(frozen=True)
class CostAllocationLine:
    invoice_id: str
    cost_category: str
    cost_circle_scope: str
    tenant_id: str
    tenant_name: str
    space_id: str
    numerator_sqm_days: Decimal
    denominator_sqm_days: Decimal
    cost_ratio: Decimal
    net_amount_eur: Decimal
    vat_rate_percent: Decimal
    vat_amount_eur: Decimal
    gross_amount_eur: Decimal
    vat_opt_in: bool
    billed_amount_eur: Decimal


class CostCircleAllocator:
    """Allocates supplier invoices across spaces and tenants within defined scopes."""

    def allocate_invoice(
        self,
        invoice: CostInvoice,
        area_result: AreaDayAllocationResult,
        spaces: List[PhysicalSpace],
        leases: List[TenantLease],
    ) -> List[CostAllocationLine]:
        matching_space_ids = self._get_matching_space_ids(spaces, invoice.cost_circle_scope)
        scope_slices = [s for s in area_result.slices if s.space_id in matching_space_ids]

        denominator_sqm_days = sum((s.sqm_days for s in scope_slices), Decimal("0.00"))
        if denominator_sqm_days == Decimal("0.00"):
            return []

        net_cents = int((invoice.net_amount_eur * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        gross_cents = int((invoice.gross_amount_eur * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        allocated_net_cents = self._distribute_cents(scope_slices, denominator_sqm_days, net_cents)
        allocated_gross_cents = self._distribute_cents(scope_slices, denominator_sqm_days, gross_cents)

        vat_map = self._build_lease_vat_map(leases)
        return self._build_allocation_lines(
            invoice=invoice,
            slices=scope_slices,
            denominator=denominator_sqm_days,
            net_cents=allocated_net_cents,
            gross_cents=allocated_gross_cents,
            vat_map=vat_map,
        )

    def _get_matching_space_ids(self, spaces: List[PhysicalSpace], scope: str) -> Set[str]:
        if scope == "CAMPUS":
            return {s.space_id for s in spaces}
        return {s.space_id for s in spaces if scope in s.cost_circle_scope}

    def _build_lease_vat_map(self, leases: List[TenantLease]) -> Dict[str, bool]:
        vat_map: Dict[str, bool] = {LANDLORD_VACANCY_ID: True}
        for lease in leases:
            vat_map[lease.tenant_id] = lease.vat_opt_in
        return vat_map

    def _distribute_cents(
        self,
        slices: List[SpaceOccupancySlice],
        denominator: Decimal,
        total_cents: int,
    ) -> List[int]:
        if not slices or total_cents == 0:
            return [0] * len(slices)

        raw_shares: List[Tuple[int, Decimal, int]] = []
        base_sum = 0
        base_allocations = [0] * len(slices)

        for idx, item in enumerate(slices):
            exact = (Decimal(total_cents) * item.sqm_days) / denominator
            base = int(exact)
            base_allocations[idx] = base
            base_sum += base
            remainder = exact - Decimal(base)
            raw_shares.append((idx, remainder, base))

        discrepancy = total_cents - base_sum
        raw_shares.sort(key=lambda x: (x[1], x[0]), reverse=True)

        for i in range(discrepancy):
            target_idx = raw_shares[i][0]
            base_allocations[target_idx] += 1

        return base_allocations

    def _build_allocation_lines(
        self,
        invoice: CostInvoice,
        slices: List[SpaceOccupancySlice],
        denominator: Decimal,
        net_cents: List[int],
        gross_cents: List[int],
        vat_map: Dict[str, bool],
    ) -> List[CostAllocationLine]:
        lines: List[CostAllocationLine] = []

        for idx, item in enumerate(slices):
            line = self._create_line_from_slice(
                invoice=invoice,
                item=item,
                denominator=denominator,
                slice_net_cents=net_cents[idx],
                slice_gross_cents=gross_cents[idx],
                vat_map=vat_map,
            )
            lines.append(line)

        return lines

    def _create_line_from_slice(
        self,
        invoice: CostInvoice,
        item: SpaceOccupancySlice,
        denominator: Decimal,
        slice_net_cents: int,
        slice_gross_cents: int,
        vat_map: Dict[str, bool],
    ) -> CostAllocationLine:
        net_eur = (Decimal(slice_net_cents) / Decimal("100")).quantize(Decimal("0.01"))
        gross_eur = (Decimal(slice_gross_cents) / Decimal("100")).quantize(Decimal("0.01"))
        cost_ratio = (item.sqm_days / denominator).quantize(Decimal("0.000001"))

        is_opted = vat_map.get(item.tenant_id, True)
        vat_eur = self._calculate_vat_amount(net_eur, invoice.vat_rate_percent)
        billed_eur = self._determine_billed_amount(net_eur, vat_eur, gross_eur, is_opted)

        return CostAllocationLine(
            invoice_id=invoice.invoice_id,
            cost_category=invoice.cost_category,
            cost_circle_scope=invoice.cost_circle_scope,
            tenant_id=item.tenant_id,
            tenant_name=item.tenant_name,
            space_id=item.space_id,
            numerator_sqm_days=item.sqm_days,
            denominator_sqm_days=denominator,
            cost_ratio=cost_ratio,
            net_amount_eur=net_eur,
            vat_rate_percent=invoice.vat_rate_percent,
            vat_amount_eur=vat_eur,
            gross_amount_eur=gross_eur,
            vat_opt_in=is_opted,
            billed_amount_eur=billed_eur,
        )

    def _calculate_vat_amount(self, net_eur: Decimal, rate_percent: Decimal) -> Decimal:
        raw_vat = net_eur * (rate_percent / Decimal("100"))
        return raw_vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _determine_billed_amount(
        self, net_eur: Decimal, vat_eur: Decimal, gross_eur: Decimal, is_opted: bool
    ) -> Decimal:
        if is_opted:
            return net_eur + vat_eur
        return gross_eur
