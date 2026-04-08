"""
VAT (Thuế Giá Trị Gia Tăng - GTGT) rules.

Key references:
- Luật Thuế GTGT số 13/2008/QH12 (sửa đổi, bổ sung)
- Nghị định 123/2020/NĐ-CP về hóa đơn, chứng từ
- Thông tư 219/2013/TT-BTC hướng dẫn thuế GTGT
"""

from .base import CustomerType, TaxCategory, TaxContext, TaxResult, TaxRule

# --- Load VAT parameters from config (with hardcoded fallbacks) ---
try:
    from data.tax_config_loader import tax_config as _cfg
    VAT_RATE_STANDARD: float = _cfg.vat_rate_standard
    VAT_RATE_REDUCED: float = _cfg.vat_rate_reduced
    VAT_RATE_SPECIAL_REDUCED: float = _cfg.vat_rate_special_reduced
    VAT_REGISTRATION_THRESHOLD: int = _cfg.vat_registration_threshold
except Exception:
    VAT_RATE_STANDARD = 0.10
    VAT_RATE_REDUCED = 0.05
    VAT_RATE_SPECIAL_REDUCED = 0.08
    VAT_REGISTRATION_THRESHOLD = 100_000_000

VAT_RATE_ZERO = 0.0  # 0% - Hàng xuất khẩu (always zero)


class VATRule(TaxRule):
    @property
    def category(self) -> TaxCategory:
        return TaxCategory.VAT

    def calculate(self, context: TaxContext) -> TaxResult:
        """
        Calculate VAT based on customer type and context.

        Methods:
        - Khấu trừ (deduction): For SMEs with proper bookkeeping
        - Trực tiếp (direct): For households/individuals or SMEs without full bookkeeping
        """
        if context.customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return self._calculate_direct_method(context)
        return self._calculate_deduction_method(context)

    def _calculate_deduction_method(self, context: TaxContext) -> TaxResult:
        """Phương pháp khấu trừ - cho doanh nghiệp có hóa đơn GTGT."""
        revenue = context.revenue or 0
        rate = self._get_applicable_rate(context)
        vat_amount = revenue * rate

        return TaxResult(
            category=TaxCategory.VAT,
            amount=vat_amount,
            rate=rate,
            explanation=(
                f"Thuế GTGT theo phương pháp khấu trừ:\n"
                f"• Doanh thu: {revenue:,.0f} VND\n"
                f"• Thuế suất: {rate * 100:.0f}%\n"
                f"• Thuế GTGT đầu ra: {vat_amount:,.0f} VND\n"
                f"• Thuế GTGT phải nộp = Thuế đầu ra - Thuế đầu vào được khấu trừ"
            ),
            legal_basis=[
                "Luật Thuế GTGT số 13/2008/QH12",
                "Thông tư 219/2013/TT-BTC",
            ],
        )

    def _calculate_direct_method(self, context: TaxContext) -> TaxResult:
        """Phương pháp trực tiếp - cho hộ kinh doanh, cá thể."""
        revenue = context.revenue or 0

        # Tỷ lệ % GTGT trên doanh thu theo ngành nghề
        rate_on_revenue = self._get_direct_rate(context.industry_code)
        vat_amount = revenue * rate_on_revenue

        return TaxResult(
            category=TaxCategory.VAT,
            amount=vat_amount,
            rate=rate_on_revenue,
            explanation=(
                f"Thuế GTGT theo phương pháp trực tiếp:\n"
                f"• Doanh thu: {revenue:,.0f} VND\n"
                f"• Tỷ lệ GTGT: {rate_on_revenue * 100:.0f}%\n"
                f"• Thuế GTGT: {vat_amount:,.0f} VND"
            ),
            legal_basis=[
                "Thông tư 219/2013/TT-BTC - Điều 13",
            ],
            warnings=self._get_warnings(context),
        )

    def _get_applicable_rate(self, context: TaxContext) -> float:
        """Get the applicable VAT rate based on context."""
        # Simplified: return standard rate. Full implementation would check
        # goods/services category against Appendix of Thông tư 219.
        return VAT_RATE_STANDARD

    def _get_direct_rate(self, industry_code: str | None) -> float:
        """
        Tỷ lệ % GTGT trên doanh thu (phương pháp trực tiếp).
        Theo Thông tư 219/2013/TT-BTC.
        """
        # Simplified rate table by industry
        rates = {
            "distribution": 0.01,  # Phân phối, cung cấp hàng hóa: 1%
            "services": 0.05,  # Dịch vụ, xây dựng: 5%
            "manufacturing": 0.03,  # Sản xuất, vận tải, chế biến: 3%
            "other": 0.02,  # Hoạt động khác: 2%
        }
        return rates.get(industry_code or "other", 0.02)

    def _get_warnings(self, context: TaxContext) -> list[str]:
        warnings = []
        if context.revenue and context.revenue < VAT_REGISTRATION_THRESHOLD:
            warnings.append(
                "Doanh thu dưới 100 triệu VND/năm: Có thể không phải nộp thuế GTGT "
                "(theo Điều 1, Thông tư 92/2015/TT-BTC)"
            )
        return warnings

    def get_info(self, customer_type: CustomerType) -> str:
        if customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return (
                "Thuế GTGT cho hộ kinh doanh / cá thể:\n"
                "• Phương pháp: Trực tiếp trên doanh thu\n"
                "• Ngưỡng: Doanh thu > 100 triệu VND/năm mới phải nộp\n"
                "• Tỷ lệ: 1-5% tùy ngành nghề\n"
                "• Kê khai: Hàng quý hoặc theo từng lần phát sinh"
            )
        return (
            "Thuế GTGT cho doanh nghiệp (SME):\n"
            "• Phương pháp khấu trừ: Thuế phải nộp = Thuế đầu ra - Thuế đầu vào\n"
            "• Thuế suất phổ thông: 10%\n"
            "• Thuế suất ưu đãi: 5% (một số hàng hóa, dịch vụ)\n"
            "• Kê khai: Hàng tháng (doanh thu > 50 tỷ) hoặc hàng quý"
        )

    def get_consultation(
        self, customer_type: CustomerType, entities: dict | None = None,
    ) -> str:
        is_household = customer_type in (
            CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL,
        )

        lines = ["Tư vấn Thuế Giá trị gia tăng (GTGT):\n"]

        # --- 1. Phương pháp tính ---
        lines.append("1. Phương pháp tính thuế:")
        if is_household:
            lines.append("   • Phương pháp trực tiếp trên doanh thu")
            lines.append("   • Thuế GTGT = Doanh thu × Tỷ lệ GTGT")
            lines.append("   • Tỷ lệ theo ngành:")
            lines.append("     - Phân phối, bán hàng: 1%")
            lines.append("     - Sản xuất, vận tải: 3%")
            lines.append("     - Dịch vụ, xây dựng: 5%")
            lines.append("     - Hoạt động khác: 2%")
        else:
            lines.append("   • Phương pháp khấu trừ:")
            lines.append("     Thuế GTGT phải nộp = Thuế đầu ra - Thuế đầu vào")
            lines.append(f"   • Thuế suất phổ thông: {VAT_RATE_STANDARD * 100:.0f}%")
            lines.append(f"   • Thuế suất ưu đãi: {VAT_RATE_REDUCED * 100:.0f}% "
                         "(lương thực, nước sạch, thiết bị y tế, giáo dục...)")
            lines.append("   • Thuế suất 0%: Hàng xuất khẩu, vận tải quốc tế")

        # --- 2. Ngưỡng & điều kiện ---
        lines.append("\n2. Ngưỡng & Điều kiện:")
        if is_household:
            lines.append(
                f"   • Doanh thu ≤ {VAT_REGISTRATION_THRESHOLD / 1e6:.0f} triệu/năm: "
                "Không phải nộp thuế GTGT"
            )
            lines.append(
                f"   • Doanh thu > {VAT_REGISTRATION_THRESHOLD / 1e6:.0f} triệu/năm: "
                "Phải kê khai và nộp thuế GTGT"
            )
        else:
            lines.append("   • DN mới thành lập: đăng ký phương pháp khấu trừ hoặc trực tiếp")
            lines.append("   • Điều kiện khấu trừ: có hóa đơn GTGT hợp lệ, thanh toán qua NH"
                         " (≥ 20 triệu)")

        # --- 3. Kê khai ---
        lines.append("\n3. Kê khai:")
        if is_household:
            lines.append("   • Hàng quý hoặc theo từng lần phát sinh")
            lines.append("   • Hạn nộp: Ngày cuối tháng đầu quý sau")
        else:
            lines.append("   • Doanh thu > 50 tỷ/năm: Kê khai hàng tháng (hạn ngày 20 tháng sau)")
            lines.append("   • Doanh thu ≤ 50 tỷ/năm: Kê khai hàng quý (hạn ngày cuối tháng đầu quý sau)")

        # --- 4. Căn cứ pháp lý ---
        lines.append("\n4. Căn cứ pháp lý:")
        lines.append("   • Luật Thuế GTGT số 13/2008/QH12 (sửa đổi, bổ sung)")
        lines.append("   • Thông tư 219/2013/TT-BTC")
        lines.append("   • Nghị định 123/2020/NĐ-CP (hóa đơn, chứng từ)")

        lines.append(
            "\n💡 Để tính thuế cụ thể, bạn có thể cung cấp doanh thu. "
            "VD: \"thuế GTGT doanh thu 500 triệu\""
        )
        return "\n".join(lines)
