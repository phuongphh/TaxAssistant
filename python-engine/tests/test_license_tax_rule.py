"""
Unit tests for License Tax (Lệ phí Môn Bài) rules.

Issue #71: Lệ phí môn bài đã bãi bỏ từ 01/01/2026 (Nghị quyết 198/2025/QH15
+ Nghị định 362/2025/NĐ-CP). Các test cũ kiểm tra biểu mức theo Nghị định
139/2016/NĐ-CP nay phải explicit set ``year=2025`` (hoặc nhỏ hơn) để
chứng tỏ đó là chế độ kế thừa cho người dùng hoàn tất nghĩa vụ kỳ ≤ 2025.

Test cho hành vi 2026+ (bãi bỏ) sống ở ``test_license_tax_abolition.py``.
"""

import pytest

from app.core.tax_rules.base import CustomerType, TaxCategory, TaxContext
from app.core.tax_rules.license_tax import LicenseTaxRule

# Năm dùng cho mọi test biểu mức cũ — vẫn là chế độ NĐ 139/2016 hợp lệ.
HISTORICAL_YEAR = 2025


def _ctx(**kwargs) -> TaxContext:
    """Helper tạo TaxContext với year=2025 mặc định để test biểu mức cũ."""
    kwargs.setdefault("year", HISTORICAL_YEAR)
    return TaxContext(**kwargs)


@pytest.fixture
def license_rule():
    return LicenseTaxRule()


class TestLicenseTaxCategory:
    def test_category_is_license(self, license_rule: LicenseTaxRule):
        assert license_rule.category == TaxCategory.LICENSE


class TestLicenseTaxEnterprise:
    """Biểu mức cho doanh nghiệp (theo vốn điều lệ) — kỳ ≤ 2025."""

    def test_capital_above_10_billion(self, license_rule: LicenseTaxRule):
        """Vốn > 10 tỷ → 3 triệu/năm."""
        ctx = _ctx(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 15_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert result.amount == 3_000_000

    def test_capital_below_10_billion(self, license_rule: LicenseTaxRule):
        """Vốn ≤ 10 tỷ → 2 triệu/năm."""
        ctx = _ctx(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 5_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert result.amount == 2_000_000

    def test_capital_exactly_10_billion(self, license_rule: LicenseTaxRule):
        """Vốn = 10 tỷ (not greater) → 2 triệu."""
        ctx = _ctx(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 10_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert result.amount == 2_000_000

    def test_zero_capital_defaults(self, license_rule: LicenseTaxRule):
        ctx = _ctx(customer_type=CustomerType.SME, extra={"charter_capital": 0})
        result = license_rule.calculate(ctx)

        assert result.amount == 2_000_000

    def test_no_capital_in_context(self, license_rule: LicenseTaxRule):
        """No charter_capital → defaults to 0 → mức tối thiểu 2 triệu."""
        ctx = _ctx(customer_type=CustomerType.SME)
        result = license_rule.calculate(ctx)

        assert result.amount == 2_000_000

    def test_enterprise_legal_basis(self, license_rule: LicenseTaxRule):
        ctx = _ctx(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 5_000_000_000},
        )
        result = license_rule.calculate(ctx)

        # Văn bản lịch sử vẫn được trích dẫn cho kỳ ≤ 2025.
        assert any("139/2016" in ref for ref in result.legal_basis)

    def test_explanation_mentions_new_enterprise_exemption(self, license_rule: LicenseTaxRule):
        ctx = _ctx(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 5_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert "miễn" in result.explanation.lower()


class TestLicenseTaxHousehold:
    """Biểu mức cho hộ kinh doanh (theo doanh thu) — kỳ ≤ 2025."""

    def test_revenue_above_500m(self, license_rule: LicenseTaxRule):
        """DT > 500 triệu → 1 triệu/năm."""
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=600_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 1_000_000

    def test_revenue_300m_to_500m(self, license_rule: LicenseTaxRule):
        """DT 300-500 triệu → 500k/năm."""
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=400_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 500_000

    def test_revenue_100m_to_300m(self, license_rule: LicenseTaxRule):
        """DT 100-300 triệu → 300k/năm."""
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=200_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 300_000

    def test_revenue_exactly_300m(self, license_rule: LicenseTaxRule):
        """DT = 300 triệu (not greater) → 300k/năm."""
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=300_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 300_000

    def test_revenue_exactly_500m(self, license_rule: LicenseTaxRule):
        """DT = 500 triệu (not greater) → 500k/năm."""
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=500_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 500_000

    def test_revenue_below_100m_exempt(self, license_rule: LicenseTaxRule):
        """DT ≤ 100 triệu → miễn (0)."""
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=80_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 0

    def test_revenue_exactly_100m_exempt(self, license_rule: LicenseTaxRule):
        """DT = 100 triệu → miễn."""
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=100_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 0

    def test_zero_revenue(self, license_rule: LicenseTaxRule):
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=0)
        result = license_rule.calculate(ctx)

        assert result.amount == 0

    def test_individual_same_as_household(self, license_rule: LicenseTaxRule):
        """INDIVIDUAL uses same household method."""
        ctx_h = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=400_000_000)
        ctx_i = _ctx(customer_type=CustomerType.INDIVIDUAL, revenue=400_000_000)

        assert license_rule.calculate(ctx_h).amount == license_rule.calculate(ctx_i).amount


class TestLicenseTaxHouseholdWarnings:
    """Cảnh báo cho hộ KD — kỳ ≤ 2025 phải có warning miễn dưới 100tr +
    warning thông báo đã bãi bỏ kể từ 2026."""

    def test_warning_below_100m(self, license_rule: LicenseTaxRule):
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=80_000_000)
        result = license_rule.calculate(ctx)

        # Issue #71: ngoài warning miễn còn có warning về việc bãi bỏ từ
        # 2026, nên giờ có 2 warning.
        assert len(result.warnings) == 2
        assert any("miễn" in w.lower() for w in result.warnings)

    def test_warning_at_100m(self, license_rule: LicenseTaxRule):
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=100_000_000)
        result = license_rule.calculate(ctx)

        # 2 warnings: miễn + bãi bỏ từ 2026
        assert len(result.warnings) == 2

    def test_no_warning_above_100m(self, license_rule: LicenseTaxRule):
        ctx = _ctx(customer_type=CustomerType.HOUSEHOLD, revenue=200_000_000)
        result = license_rule.calculate(ctx)

        # Chỉ còn 1 warning về việc bãi bỏ từ 2026 (miễn không áp dụng).
        assert len(result.warnings) == 1
        assert "2026" in result.warnings[0]


class TestLicenseTaxGetInfo:
    """get_info phải LUÔN nêu rõ tình trạng bãi bỏ + biểu mức cũ tham khảo."""

    def test_sme_info(self, license_rule: LicenseTaxRule):
        info = license_rule.get_info(CustomerType.SME)
        # Tình trạng bãi bỏ phải xuất hiện
        assert "bãi bỏ" in info.lower()
        # Biểu mức cũ vẫn được nêu để tham khảo
        assert "10 tỷ" in info
        assert "3.000.000" in info
        assert "2.000.000" in info

    def test_household_info(self, license_rule: LicenseTaxRule):
        info = license_rule.get_info(CustomerType.HOUSEHOLD)
        assert "bãi bỏ" in info.lower()
        assert "500 triệu" in info
        assert "1.000.000" in info
        assert "Miễn" in info
