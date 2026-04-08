"""
Tests for DeadlineCalculator — Issue #52.
"""

from datetime import date

import pytest

from app.services.deadline_calculator import DeadlineCalculator


@pytest.fixture
def calc() -> DeadlineCalculator:
    return DeadlineCalculator()


# ---------------------------------------------------------------------------
# Helper to build profile dicts
# ---------------------------------------------------------------------------

def _profile(
    business_type: str = "household",
    tax_period: str = "quarterly",
    industry: str = "service",
    has_employees: bool = False,
    latest_revenue: int | None = None,
) -> dict:
    return {
        "business_type": business_type,
        "tax_period": tax_period,
        "industry": industry,
        "has_employees": has_employees,
        "latest_revenue": latest_revenue,
    }


# ---------------------------------------------------------------------------
# Household tests
# ---------------------------------------------------------------------------

class TestHouseholdQuarterly:
    """Hộ KD kê khai theo quý → thuế khoán, deadline ngày 30 tháng đầu quý sau."""

    def test_household_quarterly_has_deadlines(self, calc: DeadlineCalculator):
        """Test over a full year — each quarter should produce a flat_tax deadline."""
        all_deadlines: list[dict] = []
        for month in (1, 4, 7, 10):
            ref = date(2025, month, 1)
            dls = calc.get_deadlines_for_user(
                _profile("household", "quarterly"), ref,
            )
            all_deadlines.extend(
                d for d in dls if d["type"] == "flat_tax"
            )

        # Each reference should find at least one flat_tax deadline
        assert len(all_deadlines) >= 4

    def test_household_flat_rate_treated_as_quarterly(self, calc: DeadlineCalculator):
        """flat_rate period should produce the same deadlines as quarterly."""
        ref = date(2025, 10, 1)
        q_dls = calc.get_deadlines_for_user(
            _profile("household", "quarterly"), ref,
        )
        f_dls = calc.get_deadlines_for_user(
            _profile("household", "flat_rate"), ref,
        )
        assert len(q_dls) == len(f_dls)
        for q, f in zip(q_dls, f_dls):
            assert q["due_date"] == f["due_date"]
            assert q["type"] == f["type"]


class TestHouseholdMonthly:
    """Hộ KD kê khai tháng → deadline ngày 20 tháng sau."""

    def test_monthly_deadline_is_day_20(self, calc: DeadlineCalculator):
        ref = date(2025, 9, 15)
        dls = calc.get_deadlines_for_user(
            _profile("household", "monthly"), ref,
        )
        assert len(dls) > 0
        # First deadline is Sep 20 (filing for Aug) — 5 days away
        first = dls[0]
        assert first["type"] == "vat"
        assert first["due_date"] == date(2025, 9, 20)
        assert first["due_date"].day == 20


# ---------------------------------------------------------------------------
# Company tests
# ---------------------------------------------------------------------------

class TestCompanyMonthly:
    """Công ty kê khai tháng → VAT ngày 20, CIT ngày 30 tháng đầu quý sau."""

    def test_company_monthly_vat_deadline_is_day_20(self, calc: DeadlineCalculator):
        ref = date(2025, 9, 1)
        dls = calc.get_deadlines_for_user(
            _profile("company", "monthly"), ref,
        )
        vat_dls = [d for d in dls if d["type"] == "vat"]
        assert len(vat_dls) > 0
        assert vat_dls[0]["due_date"].day == 20

    def test_company_monthly_cit_deadline_is_day_30(self, calc: DeadlineCalculator):
        ref = date(2025, 9, 1)
        dls = calc.get_deadlines_for_user(
            _profile("company", "monthly"), ref,
        )
        cit_dls = [d for d in dls if d["type"] == "cit"]
        assert len(cit_dls) > 0
        assert cit_dls[0]["due_date"].day == 30


class TestCompanyQuarterly:
    """Công ty kê khai quý → VAT + CIT cùng ngày 30 tháng đầu quý sau."""

    def test_company_quarterly_cit_deadline_is_day_30(self, calc: DeadlineCalculator):
        ref = date(2025, 9, 1)
        dls = calc.get_deadlines_for_user(
            _profile("company", "quarterly"), ref,
        )
        cit_dls = [d for d in dls if d["type"] == "cit"]
        assert len(cit_dls) > 0
        assert cit_dls[0]["due_date"].day == 30

    def test_vat_and_cit_same_due_date(self, calc: DeadlineCalculator):
        ref = date(2025, 9, 1)
        dls = calc.get_deadlines_for_user(
            _profile("company", "quarterly"), ref,
        )
        vat_dates = {d["due_date"] for d in dls if d["type"] == "vat"}
        cit_dates = {d["due_date"] for d in dls if d["type"] == "cit"}
        assert vat_dates & cit_dates  # at least one shared date


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

class TestIndividual:
    """Cá nhân → PIT quý + PIT quyết toán 31/3."""

    def test_individual_pit_quarterly(self, calc: DeadlineCalculator):
        ref = date(2025, 9, 1)
        dls = calc.get_deadlines_for_user(
            _profile("individual", ""), ref,
        )
        pit_dls = [d for d in dls if d["type"] == "pit"]
        assert len(pit_dls) > 0
        assert pit_dls[0]["due_date"].day == 30

    def test_individual_does_not_require_tax_period(self, calc: DeadlineCalculator):
        """Individual deadlines should work even without tax_period."""
        ref = date(2025, 6, 1)
        dls = calc.get_deadlines_for_user(
            _profile("individual", ""), ref,
        )
        assert len(dls) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_february_edge_case_no_crash(self, calc: DeadlineCalculator):
        """Deadline clamped to Feb 28/29 — no crash."""
        ref = date(2025, 1, 15)
        dls = calc.get_deadlines_for_user(
            _profile("household", "monthly"), ref,
        )
        feb_dls = [d for d in dls if d["due_date"].month == 2]
        for d in feb_dls:
            assert d["due_date"].day <= 28  # 2025 is not a leap year

    def test_february_leap_year(self, calc: DeadlineCalculator):
        """Leap year Feb should clamp to 29."""
        ref = date(2024, 1, 15)
        dls = calc.get_deadlines_for_user(
            _profile("household", "monthly"), ref,
        )
        feb_dls = [d for d in dls if d["due_date"].month == 2]
        for d in feb_dls:
            assert d["due_date"].day <= 29

    def test_december_31_next_year_handled(self, calc: DeadlineCalculator):
        """Reference date Dec 31 → deadlines should roll into next year."""
        ref = date(2025, 12, 31)
        dls = calc.get_deadlines_for_user(
            _profile("company", "monthly"), ref,
        )
        assert len(dls) > 0
        assert all(d["due_date"] >= ref for d in dls)
        assert any(d["due_date"].year == 2026 for d in dls)

    def test_missing_tax_period_returns_empty_list(self, calc: DeadlineCalculator):
        """Profile without tax_period (non-individual) → empty list."""
        ref = date(2025, 10, 1)
        dls = calc.get_deadlines_for_user(
            _profile("household", ""), ref,
        )
        assert dls == []

    def test_missing_tax_period_none(self, calc: DeadlineCalculator):
        prof = {"business_type": "company", "tax_period": None}
        dls = calc.get_deadlines_for_user(prof, date(2025, 10, 1))
        assert dls == []

    def test_unknown_business_type_returns_empty(self, calc: DeadlineCalculator):
        prof = {"business_type": "nonprofit", "tax_period": "monthly"}
        dls = calc.get_deadlines_for_user(prof, date(2025, 10, 1))
        assert dls == []

    def test_deadlines_sorted_by_due_date(self, calc: DeadlineCalculator):
        ref = date(2025, 9, 1)
        dls = calc.get_deadlines_for_user(
            _profile("company", "monthly"), ref,
        )
        dates = [d["due_date"] for d in dls]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# Urgency tests
# ---------------------------------------------------------------------------

class TestUrgency:
    def test_urgency_critical_when_3_days_left(self, calc: DeadlineCalculator):
        ref = date(2025, 10, 17)
        dls = calc.get_deadlines_for_user(
            _profile("household", "monthly"), ref,
        )
        # Next deadline is Oct 20 → 3 days left
        oct_dl = [d for d in dls if d["due_date"] == date(2025, 10, 20)]
        assert len(oct_dl) == 1
        assert oct_dl[0]["urgency"] == "critical"

    def test_urgency_urgent_when_5_days_left(self, calc: DeadlineCalculator):
        ref = date(2025, 10, 15)
        dls = calc.get_deadlines_for_user(
            _profile("household", "monthly"), ref,
        )
        oct_dl = [d for d in dls if d["due_date"] == date(2025, 10, 20)]
        assert len(oct_dl) == 1
        assert oct_dl[0]["urgency"] == "urgent"

    def test_urgency_warning_when_10_days_left(self, calc: DeadlineCalculator):
        ref = date(2025, 10, 10)
        dls = calc.get_deadlines_for_user(
            _profile("household", "monthly"), ref,
        )
        oct_dl = [d for d in dls if d["due_date"] == date(2025, 10, 20)]
        assert len(oct_dl) == 1
        assert oct_dl[0]["urgency"] == "warning"

    def test_urgency_info_when_30_days_left(self, calc: DeadlineCalculator):
        ref = date(2025, 9, 20)
        dls = calc.get_deadlines_for_user(
            _profile("household", "monthly"), ref,
        )
        oct_dl = [d for d in dls if d["due_date"] == date(2025, 10, 20)]
        assert len(oct_dl) == 1
        assert oct_dl[0]["urgency"] == "info"


# ---------------------------------------------------------------------------
# Estimation tests
# ---------------------------------------------------------------------------

class TestEstimation:
    def test_estimated_amount_none_when_no_revenue_data(self, calc: DeadlineCalculator):
        ref = date(2025, 10, 1)
        dls = calc.get_deadlines_for_user(
            _profile("household", "quarterly", latest_revenue=None), ref,
        )
        for d in dls:
            assert d["estimated_amount"] is None
            assert d["penalty_per_day"] is None

    def test_estimated_amount_calculated_with_revenue(self, calc: DeadlineCalculator):
        ref = date(2025, 10, 1)
        dls = calc.get_deadlines_for_user(
            _profile(
                "household", "quarterly",
                industry="service",
                latest_revenue=100_000_000,
            ),
            ref,
        )
        assert len(dls) > 0
        # service VAT rate = 5% → 5,000,000
        flat_tax = [d for d in dls if d["type"] == "flat_tax"]
        assert flat_tax[0]["estimated_amount"] == 5_000_000

    def test_penalty_calculated_from_amount(self, calc: DeadlineCalculator):
        ref = date(2025, 10, 1)
        dls = calc.get_deadlines_for_user(
            _profile(
                "household", "quarterly",
                industry="service",
                latest_revenue=100_000_000,
            ),
            ref,
        )
        flat_tax = [d for d in dls if d["type"] == "flat_tax"]
        # 5,000,000 * 0.0003 = 1,500
        assert flat_tax[0]["penalty_per_day"] == 1500

    def test_unknown_industry_returns_none_estimate(self, calc: DeadlineCalculator):
        ref = date(2025, 10, 1)
        dls = calc.get_deadlines_for_user(
            _profile(
                "household", "quarterly",
                industry="agriculture",
                latest_revenue=100_000_000,
            ),
            ref,
        )
        for d in dls:
            assert d["estimated_amount"] is None


# ---------------------------------------------------------------------------
# Output shape tests
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_deadline_dict_has_required_keys(self, calc: DeadlineCalculator):
        ref = date(2025, 10, 1)
        dls = calc.get_deadlines_for_user(
            _profile("household", "quarterly"), ref,
        )
        required_keys = {
            "due_date", "type", "label", "urgency",
            "estimated_amount", "penalty_per_day",
        }
        for d in dls:
            assert required_keys.issubset(d.keys())

    def test_type_values_are_valid(self, calc: DeadlineCalculator):
        valid_types = {"flat_tax", "vat", "cit", "pit", "pit_annual"}
        for btype, period in [
            ("household", "quarterly"),
            ("household", "monthly"),
            ("company", "monthly"),
            ("company", "quarterly"),
            ("individual", ""),
        ]:
            ref = date(2025, 6, 1)
            dls = calc.get_deadlines_for_user(
                _profile(btype, period), ref,
            )
            for d in dls:
                assert d["type"] in valid_types, (
                    f"Invalid type '{d['type']}' for {btype}/{period}"
                )
