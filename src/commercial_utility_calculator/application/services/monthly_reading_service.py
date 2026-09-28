"""Monthly meter reading interpolation and VDI 2067 Gradtagszahlen seasonal weighting."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional


@dataclass(frozen=True)
class MonthlySplitResult:
    total_month_consumption: Decimal
    period_1_days: int
    period_2_days: int
    period_1_consumption: Decimal
    period_2_consumption: Decimal


class MonthlyReadingService:
    """Interpolates monthly meter readings for mid-month tenant transitions with VDI 2067 fallback."""

    # DIN 4713 / VDI 2067 German Heating Degree Day Promille Table
    VDI_2067_GRADTAGSZAHLEN: Dict[int, Decimal] = {
        1: Decimal("170"),  # January
        2: Decimal("150"),  # February
        3: Decimal("130"),  # March
        4: Decimal("80"),   # April
        5: Decimal("40"),   # May
        6: Decimal("13"),   # June
        7: Decimal("13"),   # July
        8: Decimal("14"),   # August
        9: Decimal("30"),   # September
        10: Decimal("80"),  # October
        11: Decimal("120"), # November
        12: Decimal("160"), # December
    }

    def split_monthly_consumption(
        self,
        monthly_readings: Dict[date, Decimal],
        month_start: date,
        month_end: date,
        split_date: date,
    ) -> MonthlySplitResult:
        if month_start not in monthly_readings or month_end not in monthly_readings:
            raise ValueError(f"Missing monthly reading boundary for {month_start} or {month_end}")

        delta = monthly_readings[month_end] - monthly_readings[month_start]
        total_days = (month_end - month_start).days + 1
        p1_days = (split_date - month_start).days + 1
        p2_days = total_days - p1_days

        p1_share = (delta * Decimal(p1_days)) / Decimal(total_days)
        p2_share = delta - p1_share

        return MonthlySplitResult(
            total_month_consumption=delta,
            period_1_days=p1_days,
            period_2_days=p2_days,
            period_1_consumption=p1_share.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            period_2_consumption=p2_share.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )

    def get_vdi_weight_for_period(self, start_date: date, end_date: date) -> Decimal:
        """Calculates VDI 2067 heating degree promille weight for a date interval within a year."""
        cur = start_date
        total_weight = Decimal("0.0")

        while cur <= end_date:
            month_weight = self.VDI_2067_GRADTAGSZAHLEN.get(cur.month, Decimal("0"))
            days_in_month = self._get_days_in_month(cur.year, cur.month)
            daily_weight = month_weight / Decimal(days_in_month)
            total_weight += daily_weight
            cur = self._advance_day(cur)

        return total_weight.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _get_days_in_month(self, year: int, month: int) -> int:
        if month == 2:
            return 29 if self._is_leap_year(year) else 28
        if month in {4, 6, 9, 11}:
            return 30
        return 31

    def _is_leap_year(self, year: int) -> bool:
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    def _advance_day(self, cur: date) -> date:
        from datetime import timedelta
        return cur + timedelta(days=1)
