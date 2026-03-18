"""
CIT (Thuế Thu Nhập Doanh Nghiệp - TNDN) rules.

Key references:
- Luật Thuế TNDN số 14/2008/QH12 (sửa đổi, bổ sung)
- Nghị định 218/2013/NĐ-CP
- Thông tư 78/2014/TT-BTC
- Thông tư 96/2015/TT-BTC
"""

from .base import CustomerType, TaxCategory, TaxContext, TaxResult, TaxRule

# --- Load CIT parameters from config (with hardcoded fallbacks) ---
try:
    from data.tax_config_loader import tax_config as _cfg
    CIT_RATE_STANDARD: float = _cfg.cit_rate_standard
    CIT_RATE_SMALL: float = _cfg.cit_rate_small
except Exception:
    CIT_RATE_STANDARD = 0.20
    CIT_RATE_SMALL = 0.17

# Revenue threshold for percentage-based method (simplified)
CIT_REVENUE_THRESHOLD_SIMPLIFIED = 100_000_000  # 100 triệu VND


class CITRule(TaxRule):
    @property
    def category(self) -> TaxCategory:
        return TaxCategory.CIT

    def calculate(self, context: TaxContext) -> TaxResult:
        """Calculate CIT based on customer type."""
        if context.customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return self._calculate_household(context)
        return self._calculate_enterprise(context)

    def _calculate_enterprise(self, context: TaxContext) -> TaxResult:
        """Thuế TNDN cho doanh nghiệp."""
        income = context.income or 0
        rate = CIT_RATE_STANDARD
        tax_amount = income * rate

        return TaxResult(
            category=TaxCategory.CIT,
            amount=tax_amount,
            rate=rate,
            explanation=(
                f"Thuế TNDN:\n"
                f"• Thu nhập chịu thuế: {income:,.0f} VND\n"
                f"• Thuế suất: {rate * 100:.0f}%\n"
                f"• Thuế TNDN = Thu nhập chịu thuế × {rate * 100:.0f}% = {tax_amount:,.0f} VND\n\n"
                f"Lưu ý: Thu nhập chịu thuế = Doanh thu - Chi phí được trừ - Thu nhập miễn thuế"
            ),
            legal_basis=[
                "Luật Thuế TNDN số 14/2008/QH12",
                "Thông tư 78/2014/TT-BTC",
                "Thông tư 96/2015/TT-BTC",
            ],
        )

    def _calculate_household(self, context: TaxContext) -> TaxResult:
        """
        Thuế TNCN cho hộ kinh doanh (tính theo tỷ lệ trên doanh thu).
        Hộ kinh doanh nộp thuế TNCN, không nộp thuế TNDN.
        """
        revenue = context.revenue or 0

        # Tỷ lệ thuế TNCN cho hộ kinh doanh theo ngành nghề
        rate_on_revenue = self._get_household_rate(context.industry_code)
        tax_amount = revenue * rate_on_revenue

        return TaxResult(
            category=TaxCategory.CIT,
            amount=tax_amount,
            rate=rate_on_revenue,
            explanation=(
                f"Thuế TNCN cho hộ kinh doanh (tính trên doanh thu):\n"
                f"• Doanh thu: {revenue:,.0f} VND\n"
                f"• Tỷ lệ thuế TNCN: {rate_on_revenue * 100:.1f}%\n"
                f"• Thuế TNCN: {tax_amount:,.0f} VND"
            ),
            legal_basis=[
                "Thông tư 40/2021/TT-BTC",
            ],
            warnings=self._get_household_warnings(context),
        )

    def _get_household_rate(self, industry_code: str | None) -> float:
        """Tỷ lệ thuế TNCN trên doanh thu cho hộ kinh doanh (Thông tư 40/2021)."""
        rates = {
            "distribution": 0.005,  # Phân phối, cung cấp hàng hóa: 0.5%
            "services": 0.02,  # Dịch vụ: 2%
            "manufacturing": 0.015,  # Sản xuất, vận tải: 1.5%
            "other": 0.01,  # Khác: 1%
        }
        return rates.get(industry_code or "other", 0.01)

    def _get_household_warnings(self, context: TaxContext) -> list[str]:
        warnings = []
        if context.revenue and context.revenue < CIT_REVENUE_THRESHOLD_SIMPLIFIED:
            warnings.append(
                "Doanh thu dưới 100 triệu VND/năm: "
                "Hộ kinh doanh không phải nộp thuế TNCN (Thông tư 40/2021/TT-BTC)"
            )
        return warnings

    def get_info(self, customer_type: CustomerType) -> str:
        if customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return (
                "Hộ kinh doanh / Cá thể nộp thuế TNCN (không phải TNDN):\n"
                "• Ngưỡng: Doanh thu > 100 triệu VND/năm\n"
                "• Tỷ lệ: 0.5% - 2% trên doanh thu tùy ngành\n"
                "• Kê khai: Hàng năm hoặc theo từng lần phát sinh"
            )
        return (
            "Thuế TNDN cho SME:\n"
            "• Thuế suất phổ thông: 20%\n"
            "• Công thức: Thu nhập chịu thuế × 20%\n"
            "• Thu nhập chịu thuế = Doanh thu - Chi phí được trừ\n"
            "• Kê khai tạm tính: Hàng quý\n"
            "• Quyết toán: Hàng năm (trong 90 ngày kể từ kết thúc năm tài chính)"
        )

    def get_consultation(
        self, customer_type: CustomerType, entities: dict | None = None,
    ) -> str:
        is_household = customer_type in (
            CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL,
        )

        lines = ["Tư vấn Thuế Thu nhập doanh nghiệp (TNDN):\n"]

        if is_household:
            lines.append("⚠ Lưu ý: Hộ kinh doanh / cá thể KHÔNG nộp thuế TNDN.")
            lines.append("Hộ kinh doanh nộp thuế TNCN trên doanh thu.\n")

            lines.append("1. Thuế TNCN cho hộ kinh doanh:")
            lines.append(f"   • Ngưỡng doanh thu: > {CIT_REVENUE_THRESHOLD_SIMPLIFIED / 1e6:.0f} triệu/năm")
            lines.append("   • Tỷ lệ thuế trên doanh thu theo ngành:")
            lines.append("     - Phân phối, bán hàng: 0.5%")
            lines.append("     - Sản xuất, vận tải: 1.5%")
            lines.append("     - Dịch vụ: 2%")
            lines.append("     - Hoạt động khác: 1%")
            lines.append(
                f"\n   • Doanh thu ≤ {CIT_REVENUE_THRESHOLD_SIMPLIFIED / 1e6:.0f} triệu/năm: "
                "Không phải nộp"
            )

            lines.append("\n2. Kê khai:")
            lines.append("   • Hàng năm hoặc theo từng lần phát sinh")

            lines.append("\n3. Căn cứ pháp lý:")
            lines.append("   • Thông tư 40/2021/TT-BTC")
        else:
            lines.append("1. Cách tính thuế:")
            lines.append(
                f"   • Thuế TNDN = Thu nhập chịu thuế × {CIT_RATE_STANDARD * 100:.0f}%"
            )
            lines.append("   • Thu nhập chịu thuế = Doanh thu - Chi phí được trừ - Thu nhập miễn thuế")
            if CIT_RATE_SMALL != CIT_RATE_STANDARD:
                lines.append(
                    f"   • DN nhỏ và siêu nhỏ: thuế suất ưu đãi {CIT_RATE_SMALL * 100:.0f}%"
                )

            lines.append("\n2. Chi phí được trừ (điều kiện):")
            lines.append("   • Liên quan đến hoạt động sản xuất kinh doanh")
            lines.append("   • Có đủ hóa đơn, chứng từ hợp lệ")
            lines.append("   • Thanh toán qua ngân hàng nếu ≥ 20 triệu VND")

            lines.append("\n3. Ưu đãi thuế TNDN:")
            lines.append("   • DN mới thành lập tại địa bàn khó khăn: miễn 2 năm, giảm 50% trong 4 năm")
            lines.append("   • DN công nghệ cao, phần mềm: thuế suất 10% trong 15 năm")
            lines.append("   • DN nhỏ và siêu nhỏ: thuế suất ưu đãi theo quy định")

            lines.append("\n4. Kê khai & Quyết toán:")
            lines.append("   • Tạm tính: Hàng quý (hạn ngày 30 tháng đầu quý sau)")
            lines.append("   • Quyết toán: Trong 90 ngày kể từ kết thúc năm tài chính")

            lines.append("\n5. Căn cứ pháp lý:")
            lines.append("   • Luật Thuế TNDN số 14/2008/QH12")
            lines.append("   • Thông tư 78/2014/TT-BTC")
            lines.append("   • Thông tư 96/2015/TT-BTC")

        lines.append(
            "\n💡 Để tính thuế cụ thể, bạn có thể cung cấp thu nhập/doanh thu. "
            "VD: \"tính thuế TNDN thu nhập 1 tỷ\""
        )
        return "\n".join(lines)
