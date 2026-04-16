"""
Deadline Calculator Engine — Issue #52

Tính toán deadline thuế cho từng user dựa trên profile.
Pure business logic, không có side effects.

References:
- Thông tư 40/2021/TT-BTC (tỷ lệ thuế khoán theo ngành)
- Luật Quản lý thuế 2019 (phạt chậm nộp 0.03%/ngày)
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

# ---------------------------------------------------------------------------
# Tax estimation rates per Thông tư 40/2021/TT-BTC
# Keys map to profile["industry"] values used in onboarding.
# Each tuple: (vat_rate, pit_rate)
# ---------------------------------------------------------------------------
INDUSTRY_TAX_RATES: dict[str, tuple[float, float]] = {
    "trade": (0.005, 0.005),          # Thương mại / TMĐT — 1.0% total
    "ecommerce": (0.005, 0.005),
    "service": (0.05, 0.02),          # Dịch vụ — 7.0% total
    "manufacturing": (0.03, 0.015),   # Sản xuất / gia công — 4.5% total
    "consulting": (0.05, 0.02),       # Tư vấn / chuyên môn — 7.0% total
}

# Penalty rate for late filing: 0.03% of tax amount per day
# (Luật Quản lý thuế 2019, Điều 59)
LATE_PENALTY_RATE_PER_DAY = 0.0003

# Deadline lookahead window (days)
LOOKAHEAD_DAYS = 60

# Urgency thresholds (days remaining)
URGENCY_CRITICAL = 3
URGENCY_URGENT = 7
URGENCY_WARNING = 14


def _clamp_day(year: int, month: int, day: int) -> date:
    """Return a date clamped to the last valid day of the month."""
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, max_day))


def _next_month(ref: date) -> tuple[int, int]:
    """Return (year, month) of the month after *ref*."""
    if ref.month == 12:
        return ref.year + 1, 1
    return ref.year, ref.month + 1


def _quarter_of(d: date) -> int:
    """Return 1-based quarter for a date."""
    return (d.month - 1) // 3 + 1


def _first_month_of_next_quarter(ref: date) -> tuple[int, int]:
    """Return (year, first_month) of the quarter following *ref*."""
    q = _quarter_of(ref)
    if q == 4:
        return ref.year + 1, 1
    return ref.year, q * 3 + 1


def _quarter_label(due: date, prefix: str) -> str:
    """Build a Vietnamese label like 'Thuế khoán Q3/2025'.

    The deadline falls in the quarter *after* the reporting quarter,
    so the label refers to the quarter before the due date's quarter.
    """
    q = _quarter_of(due)
    # The reporting quarter is one before the deadline quarter
    if q == 1:
        return f"{prefix} Q4/{due.year - 1}"
    return f"{prefix} Q{q - 1}/{due.year}"


def _month_label(due: date, prefix: str) -> str:
    """Build a label like 'VAT T9/2025' (month before the deadline month)."""
    if due.month == 1:
        return f"{prefix} T12/{due.year - 1}"
    return f"{prefix} T{due.month - 1}/{due.year}"


class DeadlineCalculator:
    """Calculate upcoming tax deadlines for a user profile."""

    def get_deadlines_for_user(
        self,
        profile: dict[str, Any],
        reference_date: date,
    ) -> list[dict[str, Any]]:
        """Return deadlines within 60 days of *reference_date*, sorted by due_date.

        Parameters
        ----------
        profile : dict
            User profile from DB.  Expected keys:
            ``business_type``, ``tax_period``, ``industry``,
            ``has_employees``, ``latest_revenue`` (optional).
        reference_date : date
            "Today" for the calculation.

        Returns
        -------
        list[dict]
            Each dict has keys: due_date, type, label, urgency,
            estimated_amount, penalty_per_day.
        """
        business_type = (profile.get("business_type") or "").lower()
        tax_period = (profile.get("tax_period") or "").lower()

        if not tax_period and business_type != "individual":
            return []

        raw_deadlines = self._generate_deadlines(
            business_type, tax_period, reference_date,
        )

        cutoff = reference_date.toordinal() + LOOKAHEAD_DAYS
        result: list[dict[str, Any]] = []
        for dl in raw_deadlines:
            due = dl["due_date"]
            if due < reference_date:
                continue
            if due.toordinal() > cutoff:
                continue
            days_left = (due - reference_date).days
            dl["urgency"] = self._urgency(days_left)
            dl["estimated_amount"] = self._estimate_amount(
                profile, dl["type"],
            )
            dl["penalty_per_day"] = self._estimate_penalty(
                dl["estimated_amount"],
            )
            result.append(dl)

        result.sort(key=lambda d: d["due_date"])
        return result

    # ------------------------------------------------------------------
    # Internal: deadline generation per business type
    # ------------------------------------------------------------------

    def _generate_deadlines(
        self,
        business_type: str,
        tax_period: str,
        ref: date,
    ) -> list[dict[str, Any]]:
        generators = {
            "household": self._household_deadlines,
            "company": self._company_deadlines,
            "individual": self._individual_deadlines,
        }
        gen = generators.get(business_type)
        if gen is None:
            return []
        return gen(tax_period, ref)

    # ------------------------------------------------------------------
    # Monthly deadline generator: day 20 of month M+1 for period M
    # ------------------------------------------------------------------

    @staticmethod
    def _monthly_deadlines_day20(
        ref: date, dtype: str, prefix: str,
    ) -> list[dict[str, Any]]:
        """Generate monthly deadlines (day 20 of next month) over a wide window.

        Starts from the previous month's reporting period to ensure we
        capture deadlines that are still upcoming from *ref*.
        """
        results: list[dict[str, Any]] = []
        # Start from month before ref and go forward 4 months
        start_month = ref.month - 1 or 12
        start_year = ref.year if ref.month > 1 else ref.year - 1
        for i in range(5):
            # Reporting period
            total = start_month + i
            rp_year = start_year + (total - 1) // 12
            rp_month = (total - 1) % 12 + 1
            # Deadline = day 20 of the month after the reporting period
            dy, dm = _next_month(date(rp_year, rp_month, 1))
            due = _clamp_day(dy, dm, 20)
            results.append({
                "due_date": due,
                "type": dtype,
                "label": _month_label(due, prefix),
            })
        return results

    # ------------------------------------------------------------------
    # Quarterly deadline generator: day 30 of first month of next quarter
    # ------------------------------------------------------------------

    @staticmethod
    def _quarterly_deadlines_day30(
        ref: date, dtype: str, prefix: str,
    ) -> list[dict[str, Any]]:
        """Generate quarterly deadlines (day 30 of first month of Q+1).

        Starts from the quarter before *ref*'s quarter so we capture
        deadlines whose filing window is still open.
        """
        results: list[dict[str, Any]] = []
        q = _quarter_of(ref)
        # Start from previous quarter
        start_q = q - 1 if q > 1 else 4
        start_year = ref.year if q > 1 else ref.year - 1
        for i in range(4):
            rq = start_q + i
            ry = start_year + (rq - 1) // 4
            rq = (rq - 1) % 4 + 1
            # Deadline = day 30 of first month of the quarter after rq
            if rq == 4:
                dy, dm = ry + 1, 1
            else:
                dy, dm = ry, rq * 3 + 1
            due = _clamp_day(dy, dm, 30)
            results.append({
                "due_date": due,
                "type": dtype,
                "label": _quarter_label(due, prefix),
            })
        return results

    def _household_deadlines(
        self, tax_period: str, ref: date,
    ) -> list[dict[str, Any]]:
        if tax_period in ("quarterly", "flat_rate"):
            return self._quarterly_deadlines_day30(ref, "flat_tax", "Thuế khoán")
        if tax_period == "monthly":
            return self._monthly_deadlines_day20(ref, "vat", "Kê khai thuế")
        return []

    def _company_deadlines(
        self, tax_period: str, ref: date,
    ) -> list[dict[str, Any]]:
        deadlines: list[dict[str, Any]] = []
        if tax_period == "monthly":
            deadlines.extend(
                self._monthly_deadlines_day20(ref, "vat", "VAT"),
            )
            deadlines.extend(
                self._quarterly_deadlines_day30(ref, "cit", "CIT tạm tính"),
            )
        elif tax_period == "quarterly":
            deadlines.extend(
                self._quarterly_deadlines_day30(ref, "vat", "VAT"),
            )
            deadlines.extend(
                self._quarterly_deadlines_day30(ref, "cit", "CIT tạm tính"),
            )
        return deadlines

    def _individual_deadlines(
        self, tax_period: str, ref: date,
    ) -> list[dict[str, Any]]:
        deadlines = list(
            self._quarterly_deadlines_day30(ref, "pit", "PIT quý"),
        )
        # PIT annual: March 31 of next year
        pit_annual_due = date(ref.year + 1, 3, 31)
        deadlines.append({
            "due_date": pit_annual_due,
            "type": "pit_annual",
            "label": f"Quyết toán PIT {ref.year}",
        })
        return deadlines

    # ------------------------------------------------------------------
    # Urgency
    # ------------------------------------------------------------------

    @staticmethod
    def _urgency(days_left: int) -> str:
        if days_left <= URGENCY_CRITICAL:
            return "critical"
        if days_left <= URGENCY_URGENT:
            return "urgent"
        if days_left <= URGENCY_WARNING:
            return "warning"
        return "info"

    # ------------------------------------------------------------------
    # Tax estimation
    # ------------------------------------------------------------------

    def _estimate_amount(
        self, profile: dict[str, Any], deadline_type: str,
    ) -> int | None:
        revenue = profile.get("latest_revenue")
        if revenue is None or revenue <= 0:
            return None

        industry = (profile.get("industry") or "").lower()
        rates = INDUSTRY_TAX_RATES.get(industry)
        if rates is None:
            return None

        vat_rate, pit_rate = rates
        if deadline_type in ("vat", "flat_tax"):
            return int(revenue * vat_rate)
        if deadline_type in ("pit", "pit_annual"):
            return int(revenue * pit_rate)
        if deadline_type == "cit":
            # CIT for companies: use combined rate as rough proxy
            return int(revenue * (vat_rate + pit_rate))
        return None

    @staticmethod
    def _estimate_penalty(estimated_amount: int | None) -> int | None:
        if estimated_amount is None:
            return None
        return round(estimated_amount * LATE_PENALTY_RATE_PER_DAY)


def _shift_months(ref: date, months: int) -> date:
    """Shift *ref* forward by *months* months, clamping the day."""
    total_months = ref.month + months
    year = ref.year + (total_months - 1) // 12
    month = (total_months - 1) % 12 + 1
    return _clamp_day(year, month, ref.day)
