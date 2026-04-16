"""
Notification Message Builder — Issue #54

Tạo nội dung tin nhắn Telegram từ kết quả DeadlineCalculator.
Cá nhân hóa theo profile và thay đổi tone theo urgency.

References:
- Thông tư 40/2021/TT-BTC
- Telegram message limit: 4096 characters
"""

from __future__ import annotations

from datetime import date
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TELEGRAM_MAX_LENGTH = 4096

# Urgency levels (match deadline_calculator.py)
URGENCY_CRITICAL = "critical"
URGENCY_URGENT = "urgent"
URGENCY_WARNING = "warning"
URGENCY_INFO = "info"

# ---------------------------------------------------------------------------
# VND formatting (per CLAUDE.md spec)
# ---------------------------------------------------------------------------


def format_vnd(amount: int) -> str:
    """Format VND amount for human-readable display.

    < 1,000,000       → "850.000 đồng"
    ≥ 1,000,000       → "8.5 triệu đồng"
    ≥ 1,000,000,000   → "1.2 tỷ đồng"
    """
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.1f} tỷ đồng"
    elif amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f} triệu đồng"
    else:
        return f"{amount:,} đồng".replace(",", ".")


# ---------------------------------------------------------------------------
# Templates — all display strings are defined here, not in logic
# ---------------------------------------------------------------------------

URGENCY_EMOJI = {
    URGENCY_CRITICAL: "\U0001f6a8",  # 🚨
    URGENCY_URGENT: "\u26a0\ufe0f",  # ⚠️
    URGENCY_WARNING: "\U0001f4cb",   # 📋
    URGENCY_INFO: "\U0001f4c5",      # 📅
}

URGENCY_HEADER = {
    URGENCY_CRITICAL: "KHẨN CẤP — Deadline trong {days} ngày!",
    URGENCY_URGENT: "Sắp đến hạn — còn {days} ngày",
    URGENCY_WARNING: "Nhắc nhở deadline — còn {days} ngày",
    URGENCY_INFO: "Thông báo deadline sắp tới",
}

TAX_HANDLER_ADVICE = {
    "self": "👉 *Hành động:* Bạn cần tự nộp tờ khai trên thuedientu.gdt.gov.vn trước hạn.",
    "accountant": "👉 *Hành động:* Hãy báo cho kế toán của bạn để chuẩn bị hồ sơ kịp thời.",
    "unknown": "👉 Bạn chưa rõ cần làm gì? Gõ /help để hỏi bot trợ giúp ngay.",
}

DEADLINE_LINE_TEMPLATE = "• *{label}* — {due_date}{amount_part}"
DEADLINE_AMOUNT_PART = " (~{amount})"
DEADLINE_PENALTY_PART = "\n  _Phạt chậm nộp: {penalty}/ngày_"
MORE_DEADLINES_TEMPLATE = "\n_...và {count} deadline khác trong 60 ngày tới._"

# Business-specific tips keyed by (business_type, industry)
# Falls back to business_type only, then generic.
BUSINESS_TIPS: dict[tuple[str, str] | str, list[str]] = {
    ("household", "service"): [
        "💡 *Tip:* Hộ KD dịch vụ nhớ kiểm tra Thông báo thuế khoán từ Chi cục thuế đầu năm.",
        "💡 *Tip:* Nếu doanh thu vượt 100 triệu/năm, bạn phải kê khai VAT riêng.",
    ],
    ("household", "trade"): [
        "💡 *Tip:* Hộ KD thương mại thuế suất chỉ 1% — nhưng phải giữ hóa đơn đầu vào cẩn thận.",
    ],
    ("household", "ecommerce"): [
        "💡 *Tip:* Bán online trên Shopee/TikTok Shop? Sàn TMĐT có thể đã trích thuế hộ — kiểm tra lại.",
        "💡 *Tip:* Doanh thu TMĐT tính cả phí ship và voucher do bạn tài trợ.",
    ],
    ("household", "manufacturing"): [
        "💡 *Tip:* Hộ SX gia công nên lưu giữ hợp đồng gia công và bảng kê nguyên vật liệu.",
    ],
    ("household", "consulting"): [
        "💡 *Tip:* Dịch vụ tư vấn thuế suất 7% — nhớ xuất hóa đơn cho mỗi hợp đồng.",
    ],
    ("company", "service"): [
        "💡 *Tip:* Công ty dịch vụ nhớ đối chiếu hóa đơn đầu vào để khấu trừ VAT.",
    ],
    ("company", "trade"): [
        "💡 *Tip:* Xuất nhập khẩu hàng hóa? Kiểm tra mã HS code để áp đúng thuế suất.",
    ],
    ("company", "ecommerce"): [
        "💡 *Tip:* Công ty TMĐT cần kê khai riêng doanh thu từ mỗi sàn.",
    ],
    ("company", "manufacturing"): [
        "💡 *Tip:* Doanh nghiệp sản xuất nên kiểm tra ưu đãi thuế theo địa bàn đầu tư.",
    ],
    ("company", "consulting"): [
        "💡 *Tip:* Hợp đồng tư vấn nước ngoài? Kiểm tra nghĩa vụ khấu trừ thuế nhà thầu.",
    ],
    "household": [
        "💡 *Tip:* Hộ kinh doanh nên lưu giữ sổ sách chi tiêu để đối chiếu khi cơ quan thuế kiểm tra.",
    ],
    "company": [
        "💡 *Tip:* Nhớ nộp báo cáo tài chính năm trước ngày 31/3 hàng năm.",
    ],
    "individual": [
        "💡 *Tip:* Cá nhân có thu nhập từ nhiều nguồn cần quyết toán thuế TNCN cuối năm.",
    ],
}

GENERIC_TIP = "💡 *Tip:* Nộp thuế đúng hạn để tránh phạt 0.03%/ngày trên số thuế chậm nộp."

# Weekly summary
WEEKLY_SUMMARY_HEADER = "📊 *Tổng hợp tuần — Deadline tháng {month}/{year}*\n"
WEEKLY_NO_DEADLINE = "✅ Không có deadline nào trong tháng này. Yên tâm kinh doanh!"

# Weekly rotating tips
WEEKLY_TIPS = [
    "💡 *Tip tuần này:* Kiểm tra lại hóa đơn đầu vào trước khi nộp tờ khai VAT.",
    "💡 *Tip tuần này:* Lưu giữ chứng từ thanh toán qua ngân hàng để hợp lệ hóa chi phí.",
    "💡 *Tip tuần này:* Doanh thu trên 1 tỷ/năm phải chuyển sang kê khai VAT khấu trừ.",
    "💡 *Tip tuần này:* Kiểm tra thông báo nợ thuế trên thuedientu.gdt.gov.vn định kỳ.",
    "💡 *Tip tuần này:* Nộp tờ khai trễ bị phạt từ 2-25 triệu đồng tùy mức vi phạm.",
    "💡 *Tip tuần này:* Hóa đơn điện tử bắt buộc — đảm bảo nhà cung cấp xuất đúng quy định.",
    "💡 *Tip tuần này:* Backup dữ liệu sổ sách mỗi tháng — phòng trường hợp thanh tra thuế.",
]

# Monthly calendar
MONTHLY_CALENDAR_HEADER = "📅 *Lịch thuế tháng {month}/{year}*\n"
MONTHLY_NO_DEADLINE = "✅ Không có deadline nào trong tháng này."
MONTHLY_CALENDAR_LINE = "📌 *{day}/{month}* — {label}{amount_part}"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class NotificationMessageBuilder:
    """Build personalized Telegram notification messages."""

    def build_deadline_reminder(
        self,
        user: dict[str, Any],
        deadlines: list[dict[str, Any]],
        today: date,
    ) -> str | None:
        """Build a deadline reminder message.

        Parameters
        ----------
        user : dict
            User profile. Expected keys: business_type, tax_handler,
            industry, display_name.
        deadlines : list[dict]
            Output from DeadlineCalculator.get_deadlines_for_user().
        today : date
            Reference date for calculating days remaining.

        Returns
        -------
        str | None
            Formatted Markdown string, or None if no deadlines.
        """
        if not deadlines:
            return None

        # Sort by due_date and pick the nearest for urgency/header
        sorted_dls = sorted(deadlines, key=lambda d: d["due_date"])
        nearest = sorted_dls[0]
        days_left = (nearest["due_date"] - today).days
        urgency = nearest.get("urgency", URGENCY_INFO)

        parts: list[str] = []

        # --- Header ---
        emoji = URGENCY_EMOJI.get(urgency, "")
        header_tmpl = URGENCY_HEADER.get(urgency, URGENCY_HEADER[URGENCY_INFO])
        header = f"{emoji} {header_tmpl.format(days=days_left)}"
        display_name = user.get("display_name") or user.get("first_name") or ""
        if display_name:
            parts.append(f"Chào *{display_name}*,\n{header}\n")
        else:
            parts.append(f"{header}\n")

        # --- Deadline list (max 3) ---
        shown = sorted_dls[:3]
        for dl in shown:
            amount_part = ""
            if dl.get("estimated_amount") is not None:
                amount_part = DEADLINE_AMOUNT_PART.format(
                    amount=format_vnd(dl["estimated_amount"]),
                )
            due_str = dl["due_date"].strftime("%d/%m/%Y")
            line = DEADLINE_LINE_TEMPLATE.format(
                label=dl["label"],
                due_date=due_str,
                amount_part=amount_part,
            )
            if dl.get("penalty_per_day") is not None and urgency in (
                URGENCY_CRITICAL, URGENCY_URGENT,
            ):
                line += DEADLINE_PENALTY_PART.format(
                    penalty=format_vnd(dl["penalty_per_day"]),
                )
            parts.append(line)

        remaining = len(sorted_dls) - 3
        if remaining > 0:
            parts.append(MORE_DEADLINES_TEMPLATE.format(count=remaining))

        # --- Tax handler advice ---
        tax_handler = (user.get("tax_handler") or "unknown").lower()
        advice = TAX_HANDLER_ADVICE.get(tax_handler, TAX_HANDLER_ADVICE["unknown"])
        parts.append(f"\n{advice}")

        # --- Business tip ---
        tip = self._pick_tip(user, today)
        parts.append(f"\n{tip}")

        message = "\n".join(parts)
        return self._truncate(message)

    def build_weekly_summary(
        self,
        user: dict[str, Any],
        deadlines_this_month: list[dict[str, Any]],
        today: date | None = None,
    ) -> str | None:
        """Build a weekly summary message (sent every Monday).

        Parameters
        ----------
        user : dict
            User profile.
        deadlines_this_month : list[dict]
            Deadlines remaining in the current month.
        today : date | None
            Reference date. Defaults to today if not provided.

        Returns
        -------
        str | None
            Formatted message, or None if no deadlines.
        """
        if today is None:
            from zoneinfo import ZoneInfo
            from datetime import datetime
            today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()

        parts: list[str] = []

        # Header
        display_name = user.get("display_name") or user.get("first_name") or ""
        header = WEEKLY_SUMMARY_HEADER.format(month=today.month, year=today.year)
        if display_name:
            parts.append(f"Chào *{display_name}*,\n{header}")
        else:
            parts.append(header)

        if not deadlines_this_month:
            parts.append(WEEKLY_NO_DEADLINE)
        else:
            # List all deadlines this month
            sorted_dls = sorted(deadlines_this_month, key=lambda d: d["due_date"])
            for dl in sorted_dls:
                emoji = URGENCY_EMOJI.get(dl.get("urgency", URGENCY_INFO), "📅")
                due_str = dl["due_date"].strftime("%d/%m")
                amount_part = ""
                if dl.get("estimated_amount") is not None:
                    amount_part = f" (~{format_vnd(dl['estimated_amount'])})"
                parts.append(f"{emoji} *{due_str}* — {dl['label']}{amount_part}")

        # Weekly rotating tip based on ISO week number
        tip_index = today.isocalendar()[1] % len(WEEKLY_TIPS)
        parts.append(f"\n{WEEKLY_TIPS[tip_index]}")

        message = "\n".join(parts)
        return self._truncate(message)

    def build_monthly_calendar(
        self,
        user: dict[str, Any],
        deadlines: list[dict[str, Any]],
        today: date | None = None,
    ) -> str | None:
        """Build a monthly calendar message (sent on the 1st of each month).

        Parameters
        ----------
        user : dict
            User profile.
        deadlines : list[dict]
            All deadlines for the current month.
        today : date | None
            Reference date for the calendar month.

        Returns
        -------
        str | None
            Formatted message, or None if no deadlines.
        """
        if today is None:
            from zoneinfo import ZoneInfo
            from datetime import datetime
            today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()

        if not deadlines:
            return None

        parts: list[str] = []

        display_name = user.get("display_name") or user.get("first_name") or ""
        header = MONTHLY_CALENDAR_HEADER.format(month=today.month, year=today.year)
        if display_name:
            parts.append(f"Chào *{display_name}*,\n{header}")
        else:
            parts.append(header)

        sorted_dls = sorted(deadlines, key=lambda d: d["due_date"])
        for dl in sorted_dls:
            due = dl["due_date"]
            amount_part = ""
            if dl.get("estimated_amount") is not None:
                amount_part = f" (~{format_vnd(dl['estimated_amount'])})"
            line = MONTHLY_CALENDAR_LINE.format(
                day=due.day,
                month=due.month,
                label=dl["label"],
                amount_part=amount_part,
            )
            parts.append(line)

        # Business tip
        tip = self._pick_tip(user, today)
        parts.append(f"\n{tip}")

        message = "\n".join(parts)
        return self._truncate(message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_tip(user: dict[str, Any], today: date) -> str:
        """Pick a contextual tip based on business_type + industry.

        Rotates daily within the available tips for the user's category.
        """
        btype = (user.get("business_type") or "").lower()
        industry = (user.get("industry") or "").lower()

        # Try specific (business_type, industry) first
        tips = BUSINESS_TIPS.get((btype, industry))
        if not tips:
            # Fallback to business_type only
            tips = BUSINESS_TIPS.get(btype)  # type: ignore[arg-type]
        if not tips:
            return GENERIC_TIP

        # Rotate by day of year
        index = today.timetuple().tm_yday % len(tips)
        return tips[index]

    @staticmethod
    def _truncate(message: str) -> str:
        """Ensure message does not exceed Telegram's 4096 char limit."""
        if len(message) <= TELEGRAM_MAX_LENGTH:
            return message
        return message[: TELEGRAM_MAX_LENGTH - 3] + "..."
