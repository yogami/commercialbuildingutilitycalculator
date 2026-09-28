"""Module A: Time-weighted area allocation (m²-Tage / Unterjährige Flächenänderungen)."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from commercial_utility_calculator.domain.entities import PhysicalSpace, TenantLease

LANDLORD_VACANCY_ID = "LANDLORD_VACANCY"
LANDLORD_VACANCY_NAME = "Leerstand (Eigentümer)"


@dataclass(frozen=True)
class SpaceOccupancySlice:
    space_id: str
    tenant_id: str
    tenant_name: str
    start_date: date
    end_date: date
    days: int
    area_sqm: Decimal
    sqm_days: Decimal
    is_vacancy: bool


@dataclass
class TenantAreaShare:
    tenant_id: str
    tenant_name: str
    slices: List[SpaceOccupancySlice] = field(default_factory=list)

    @property
    def total_sqm_days(self) -> Decimal:
        return sum((s.sqm_days for s in self.slices), Decimal("0.00"))


@dataclass
class AreaDayAllocationResult:
    billing_start: date
    billing_end: date
    total_days: int
    slices: List[SpaceOccupancySlice]
    total_sqm_days: Decimal
    vacancy_sqm_days: Decimal
    tenant_shares: Dict[str, TenantAreaShare]

    def get_tenant_share(self, tenant_id: str) -> TenantAreaShare:
        if tenant_id not in self.tenant_shares:
            return TenantAreaShare(tenant_id=tenant_id, tenant_name="Unknown")
        return self.tenant_shares[tenant_id]

    def get_landlord_vacancy_share(self) -> TenantAreaShare:
        return self.get_tenant_share(LANDLORD_VACANCY_ID)


class AreaDayAllocator:
    """Calculates exact daily time-weighted area allocations for commercial spaces."""

    def calculate_area_days(
        self,
        spaces: List[PhysicalSpace],
        leases: List[TenantLease],
        billing_start: date,
        billing_end: date,
    ) -> AreaDayAllocationResult:
        if billing_end < billing_start:
            raise ValueError(f"billing_end {billing_end} cannot precede billing_start {billing_start}")

        total_days = (billing_end - billing_start).days + 1
        slices = self._build_all_space_slices(spaces, leases, billing_start, billing_end)
        tenant_shares = self._group_by_tenant(slices)

        total_sqm_days = sum((s.sqm_days for s in slices), Decimal("0.00"))
        vacancy_sqm_days = sum((s.sqm_days for s in slices if s.is_vacancy), Decimal("0.00"))

        return AreaDayAllocationResult(
            billing_start=billing_start,
            billing_end=billing_end,
            total_days=total_days,
            slices=slices,
            total_sqm_days=total_sqm_days,
            vacancy_sqm_days=vacancy_sqm_days,
            tenant_shares=tenant_shares,
        )

    def assert_daily_area_continuity(
        self,
        result: AreaDayAllocationResult,
        spaces: List[PhysicalSpace],
        billing_start: date,
        billing_end: date,
    ) -> None:
        total_physical_sqm = sum((s.area_sqm for s in spaces), Decimal("0.00"))
        day_count = (billing_end - billing_start).days + 1

        for day_offset in range(day_count):
            current_day = billing_start + timedelta(days=day_offset)
            day_sqm = self._sum_sqm_for_day(result.slices, current_day)
            if day_sqm != total_physical_sqm:
                raise ValueError(
                    f"Area continuity breach on {current_day}: allocated {day_sqm} m² != physical {total_physical_sqm} m²"
                )

    def _sum_sqm_for_day(self, slices: List[SpaceOccupancySlice], target_date: date) -> Decimal:
        return sum(
            (s.area_sqm for s in slices if s.start_date <= target_date <= s.end_date),
            Decimal("0.00"),
        )

    def _build_all_space_slices(
        self,
        spaces: List[PhysicalSpace],
        leases: List[TenantLease],
        billing_start: date,
        billing_end: date,
    ) -> List[SpaceOccupancySlice]:
        all_slices: List[SpaceOccupancySlice] = []
        for space in spaces:
            space_leases = [l for l in leases if l.space_id == space.space_id]
            space_slices = self._build_single_space_slices(space, space_leases, billing_start, billing_end)
            all_slices.extend(space_slices)
        return all_slices

    def _build_single_space_slices(
        self,
        space: PhysicalSpace,
        leases: List[TenantLease],
        billing_start: date,
        billing_end: date,
    ) -> List[SpaceOccupancySlice]:
        clipped = self._clip_and_sort_leases(leases, billing_start, billing_end)
        self._validate_no_overlaps(clipped, space.space_id)
        return self._fill_occupancy_gaps(space, clipped, billing_start, billing_end)

    def _clip_and_sort_leases(
        self,
        leases: List[TenantLease],
        billing_start: date,
        billing_end: date,
    ) -> List[TenantLease]:
        active: List[TenantLease] = []
        for lease in leases:
            if lease.end_date < billing_start or lease.start_date > billing_end:
                continue
            effective_start = max(lease.start_date, billing_start)
            effective_end = min(lease.end_date, billing_end)
            clipped = lease.model_copy(update={"start_date": effective_start, "end_date": effective_end})
            active.append(clipped)
        active.sort(key=lambda l: l.start_date)
        return active

    def _validate_no_overlaps(self, sorted_leases: List[TenantLease], space_id: str) -> None:
        for idx in range(len(sorted_leases) - 1):
            cur = sorted_leases[idx]
            nxt = sorted_leases[idx + 1]
            if cur.end_date >= nxt.start_date:
                raise ValueError(
                    f"Overlapping leases for space {space_id}: {cur.lease_id} ({cur.start_date} to {cur.end_date}) "
                    f"conflicts with {nxt.lease_id} ({nxt.start_date} to {nxt.end_date})"
                )

    def _fill_occupancy_gaps(
        self,
        space: PhysicalSpace,
        leases: List[TenantLease],
        billing_start: date,
        billing_end: date,
    ) -> List[SpaceOccupancySlice]:
        slices: List[SpaceOccupancySlice] = []
        current_cursor = billing_start

        for lease in leases:
            if lease.start_date > current_cursor:
                gap_end = lease.start_date - timedelta(days=1)
                slices.append(self._create_slice(space, LANDLORD_VACANCY_ID, LANDLORD_VACANCY_NAME, current_cursor, gap_end, True))
            slices.append(self._create_slice(space, lease.tenant_id, lease.tenant_name, lease.start_date, lease.end_date, False))
            current_cursor = lease.end_date + timedelta(days=1)

        if current_cursor <= billing_end:
            slices.append(self._create_slice(space, LANDLORD_VACANCY_ID, LANDLORD_VACANCY_NAME, current_cursor, billing_end, True))

        return slices

    def _create_slice(
        self,
        space: PhysicalSpace,
        tenant_id: str,
        tenant_name: str,
        start_date: date,
        end_date: date,
        is_vacancy: bool,
    ) -> SpaceOccupancySlice:
        days = (end_date - start_date).days + 1
        sqm_days = space.area_sqm * Decimal(days)
        return SpaceOccupancySlice(
            space_id=space.space_id,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            start_date=start_date,
            end_date=end_date,
            days=days,
            area_sqm=space.area_sqm,
            sqm_days=sqm_days,
            is_vacancy=is_vacancy,
        )

    def _group_by_tenant(self, slices: List[SpaceOccupancySlice]) -> Dict[str, TenantAreaShare]:
        shares: Dict[str, TenantAreaShare] = {}
        for s in slices:
            if s.tenant_id not in shares:
                shares[s.tenant_id] = TenantAreaShare(tenant_id=s.tenant_id, tenant_name=s.tenant_name)
            shares[s.tenant_id].slices.append(s)
        return shares
