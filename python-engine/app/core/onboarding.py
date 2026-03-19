"""
Onboarding flow for new customers.

Handles the step-by-step collection of customer information when they first
interact with the bot, and presents the service menu.
"""

import logging
import re

logger = logging.getLogger(__name__)


def _get_greeting_name(customer: dict) -> str:
    """Return the best name to use when greeting this customer.

    Priority: first_name > display_name > username > empty string.
    """
    return (
        customer.get("first_name")
        or customer.get("display_name")
        or customer.get("username")
        or ""
    )


# Service menu shown to customers
SERVICE_MENU = (
    "Dịch vụ của chúng tôi:\n"
    "1. Tính thuế (GTGT, TNDN, TNCN, Môn bài)\n"
    "2. Hướng dẫn kê khai & quyết toán thuế\n"
    "3. Đăng ký mã số thuế\n"
    "4. Kiểm tra hóa đơn, chứng từ\n"
    "5. Dịch vụ tư vấn về thuế với các dẫn chứng từ văn bản pháp luật\n"
    "6. Tư vấn xử phạt & vi phạm thuế\n"
    "7. Hỗ trợ hoàn thuế GTGT\n"
    "8. Quyết toán thuế năm"
)

SERVICE_TYPE_MAP = {
    "1": "tax_calculation",
    "2": "tax_declaration",
    "3": "tax_registration",
    "4": "invoice_check",
    "5": "tax_consultation",
    "6": "penalty_consultation",
    "7": "tax_refund",
    "8": "annual_settlement",
}

SERVICE_TITLE_MAP = {
    "tax_calculation": "Tính thuế",
    "tax_declaration": "Kê khai & quyết toán thuế",
    "tax_registration": "Đăng ký mã số thuế",
    "invoice_check": "Kiểm tra hóa đơn, chứng từ",
    "tax_consultation": "Dịch vụ tư vấn về thuế với các dẫn chứng từ văn bản pháp luật",
    "penalty_consultation": "Tư vấn xử phạt & vi phạm thuế",
    "tax_refund": "Hoàn thuế GTGT",
    "annual_settlement": "Quyết toán thuế năm",
}

# Map user input to customer type
_CUSTOMER_TYPE_KEYWORDS = {
    "sme": ["sme", "doanh nghiệp", "dn", "công ty", "cty", "enterprise"],
    "household": ["hộ", "hộ kinh doanh", "hkd", "gia đình", "hogiadia"],
    "individual": ["cá nhân", "cá thể", "cathe", "individual"],
}


class OnboardingHandler:
    """Handles the multi-step onboarding flow for new customers."""

    def process_step(self, customer: dict, message: str) -> dict:
        """Process a message within the onboarding flow.

        Args:
            customer: Customer profile dict
            message: User's message text

        Returns:
            dict with keys:
                reply: str - Bot's response text
                actions: list - Quick reply suggestions
                update_fields: dict - Fields to update on the customer record
                onboarding_complete: bool - True if onboarding just finished
                next_step: str - The next onboarding_step value
        """
        step = customer.get("onboarding_step", "new")

        if step == "new":
            return self._step_welcome(customer)
        elif step == "collecting_type":
            return self._step_collect_type(message)
        elif step == "collecting_info":
            return self._step_collect_info(customer, message)
        else:
            # Already completed or unknown step
            return self._step_completed(customer)

    def _step_welcome(self, customer: dict) -> dict:
        """First interaction - welcome message + ask customer type."""
        name = _get_greeting_name(customer)
        greeting = f"Xin chào {name}! " if name else "Xin chào! "
        reply = (
            f"{greeting}Tôi là Trợ lý Thuế - hỗ trợ tư vấn thuế cho doanh nghiệp, "
            "hộ kinh doanh và cá nhân tại Việt Nam.\n\n"
            f"{SERVICE_MENU}\n\n"
            "Để phục vụ bạn tốt hơn, bạn thuộc nhóm nào?\n"
            "1. Doanh nghiệp (SME)\n"
            "2. Hộ kinh doanh\n"
            "3. Cá nhân kinh doanh"
        )
        return {
            "reply": reply,
            "actions": [
                {"label": "Doanh nghiệp", "action_type": "quick_reply", "payload": "Doanh nghiệp"},
                {"label": "Hộ kinh doanh", "action_type": "quick_reply", "payload": "Hộ kinh doanh"},
                {"label": "Cá nhân KD", "action_type": "quick_reply", "payload": "Cá nhân kinh doanh"},
            ],
            "update_fields": {"onboarding_step": "collecting_type"},
            "onboarding_complete": False,
            "next_step": "collecting_type",
        }

    def _step_collect_type(self, message: str) -> dict:
        """Parse customer type from user's response."""
        msg_lower = message.lower().strip()
        customer_type = None

        for ctype, keywords in _CUSTOMER_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in msg_lower:
                    customer_type = ctype
                    break
            if customer_type:
                break

        # Also check numbered responses: "1", "2", "3"
        if not customer_type:
            if msg_lower in ("1",):
                customer_type = "sme"
            elif msg_lower in ("2",):
                customer_type = "household"
            elif msg_lower in ("3",):
                customer_type = "individual"

        if not customer_type:
            return {
                "reply": (
                    "Xin lỗi, tôi chưa hiểu. Bạn thuộc nhóm nào?\n"
                    "1. Doanh nghiệp (SME)\n"
                    "2. Hộ kinh doanh\n"
                    "3. Cá nhân kinh doanh"
                ),
                "actions": [
                    {"label": "Doanh nghiệp", "action_type": "quick_reply", "payload": "Doanh nghiệp"},
                    {"label": "Hộ kinh doanh", "action_type": "quick_reply", "payload": "Hộ kinh doanh"},
                    {"label": "Cá nhân KD", "action_type": "quick_reply", "payload": "Cá nhân kinh doanh"},
                ],
                "update_fields": {},
                "onboarding_complete": False,
                "next_step": "collecting_type",
            }

        # Ask for additional info based on customer type
        type_labels = {
            "sme": "Doanh nghiệp vừa và nhỏ (SME)",
            "household": "Hộ kinh doanh",
            "individual": "Cá nhân kinh doanh",
        }
        label = type_labels[customer_type]

        if customer_type == "sme":
            follow_up = (
                f"Đã ghi nhận: {label}\n\n"
                "Để phục vụ tốt hơn, bạn vui lòng cho biết:\n"
                "- Tên doanh nghiệp?\n"
                "- Ngành nghề kinh doanh?\n"
                "- Đã có mã số thuế chưa?\n\n"
                "(Bạn có thể trả lời ngắn gọn hoặc gõ 'bỏ qua' để tiếp tục)"
            )
        elif customer_type == "household":
            follow_up = (
                f"Đã ghi nhận: {label}\n\n"
                "Để phục vụ tốt hơn, bạn vui lòng cho biết:\n"
                "- Bạn kinh doanh ngành gì?\n"
                "- Doanh thu ước tính hàng năm?\n\n"
                "(Bạn có thể trả lời ngắn gọn hoặc gõ 'bỏ qua' để tiếp tục)"
            )
        else:
            follow_up = (
                f"Đã ghi nhận: {label}\n\n"
                "Để phục vụ tốt hơn, bạn vui lòng cho biết:\n"
                "- Nguồn thu nhập chính (lương, kinh doanh, đầu tư...)?\n"
                "- Có người phụ thuộc không?\n\n"
                "(Bạn có thể trả lời ngắn gọn hoặc gõ 'bỏ qua' để tiếp tục)"
            )

        return {
            "reply": follow_up,
            "actions": [
                {"label": "Bỏ qua", "action_type": "quick_reply", "payload": "bỏ qua"},
            ],
            "update_fields": {"customer_type": customer_type, "onboarding_step": "collecting_info"},
            "onboarding_complete": False,
            "next_step": "collecting_info",
        }

    def _step_collect_info(self, customer: dict, message: str) -> dict:
        """Collect additional business info and complete onboarding."""
        msg_lower = message.lower().strip()
        update_fields: dict = {"onboarding_step": "completed"}
        extracted_info: list[str] = []

        if msg_lower not in ("bỏ qua", "bo qua", "skip", "không", "khong"):
            # Try to extract business name, industry, tax code from free text
            info = self._extract_business_info(message, customer.get("customer_type", "unknown"))
            if info.get("business_name"):
                update_fields["business_name"] = info["business_name"]
                extracted_info.append(f"Tên: {info['business_name']}")
            if info.get("industry"):
                update_fields["industry"] = info["industry"]
                extracted_info.append(f"Ngành: {info['industry']}")
            if info.get("tax_code"):
                update_fields["tax_code"] = info["tax_code"]
                extracted_info.append(f"MST: {info['tax_code']}")
            if info.get("revenue_range"):
                update_fields["annual_revenue_range"] = info["revenue_range"]

        type_label = {
            "sme": "Doanh nghiệp",
            "household": "Hộ kinh doanh",
            "individual": "Cá nhân KD",
        }.get(customer.get("customer_type", ""), "Khách hàng")

        info_str = ""
        if extracted_info:
            info_str = "Thông tin đã ghi nhận: " + ", ".join(extracted_info) + "\n\n"

        name = _get_greeting_name(customer)
        name_greeting = f" {name}" if name else ""
        reply = (
            f"Cảm ơn bạn{name_greeting}! {info_str}"
            f"Chào mừng {type_label}! Tôi đã sẵn sàng hỗ trợ bạn.\n\n"
            f"{SERVICE_MENU}\n\n"
            "Bạn muốn tôi hỗ trợ dịch vụ nào? (Gõ số hoặc tên dịch vụ)"
        )

        return {
            "reply": reply,
            "actions": [
                {"label": "Tính thuế", "action_type": "quick_reply", "payload": "tính thuế"},
                {"label": "Kê khai thuế", "action_type": "quick_reply", "payload": "kê khai thuế"},
                {"label": "Hạn nộp thuế", "action_type": "quick_reply", "payload": "hạn nộp thuế"},
                {"label": "Đăng ký MST", "action_type": "quick_reply", "payload": "đăng ký mã số thuế"},
            ],
            "update_fields": update_fields,
            "onboarding_complete": True,
            "next_step": "completed",
        }

    def _step_completed(self, customer: dict) -> dict:
        """Customer already onboarded - show service menu for returning customers."""
        # Prefer personal name (username/first_name), fall back to business_name
        name = _get_greeting_name(customer) or customer.get("business_name") or ""
        greeting = f"Chào {name}! " if name else "Chào bạn! "

        reply = (
            f"{greeting}Rất vui được hỗ trợ bạn tiếp.\n\n"
            f"{SERVICE_MENU}\n\n"
            "Bạn cần hỗ trợ dịch vụ nào?"
        )
        return {
            "reply": reply,
            "actions": [
                {"label": "Tính thuế", "action_type": "quick_reply", "payload": "tính thuế"},
                {"label": "Kê khai thuế", "action_type": "quick_reply", "payload": "kê khai thuế"},
                {"label": "Hạn nộp thuế", "action_type": "quick_reply", "payload": "hạn nộp thuế"},
                {"label": "Đăng ký MST", "action_type": "quick_reply", "payload": "đăng ký mã số thuế"},
            ],
            "update_fields": {},
            "onboarding_complete": False,
            "next_step": customer.get("onboarding_step", "completed"),
        }

    def _extract_business_info(self, text: str, customer_type: str) -> dict:
        """Best-effort extraction of business info from free-text response."""
        info: dict = {}

        # Extract tax code (MST): 10 or 13 digits, optionally with dash
        mst_match = re.search(r'\b(\d{10}(?:-\d{3})?)\b', text)
        if mst_match:
            info["tax_code"] = mst_match.group(1)

        # Extract revenue ranges from Vietnamese money amounts
        revenue_patterns = [
            (r'(\d+)\s*tỷ', lambda m: "over_10b" if int(m.group(1)) >= 10 else "1b_10b"),
            (r'(\d+)\s*triệu', lambda m: "under_100m" if int(m.group(1)) < 100 else "100m_1b"),
        ]
        for pattern, classifier in revenue_patterns:
            match = re.search(pattern, text.lower())
            if match:
                info["revenue_range"] = classifier(match)
                break

        # For SME: try to extract company name (e.g., "Công ty TNHH ABC")
        if customer_type == "sme":
            name_match = re.search(
                r'((?:công ty|cty|cong ty)\s+(?:tnhh|cp|cổ phần|tư nhân|hợp danh)?\s*[\w\s]{2,50})',
                text, re.IGNORECASE
            )
            if name_match:
                info["business_name"] = name_match.group(1).strip()

        # Try to detect industry keywords
        industry_keywords = {
            "thương mại": "Thương mại",
            "bán lẻ": "Bán lẻ",
            "dịch vụ": "Dịch vụ",
            "sản xuất": "Sản xuất",
            "xây dựng": "Xây dựng",
            "vận tải": "Vận tải",
            "công nghệ": "Công nghệ thông tin",
            "nhà hàng": "Nhà hàng / Ăn uống",
            "ăn uống": "Nhà hàng / Ăn uống",
            "giáo dục": "Giáo dục",
            "y tế": "Y tế",
            "nông nghiệp": "Nông nghiệp",
            "bất động sản": "Bất động sản",
        }
        text_lower = text.lower()
        for keyword, industry_name in industry_keywords.items():
            if keyword in text_lower:
                info["industry"] = industry_name
                break

        return info

    @staticmethod
    def parse_service_selection(message: str) -> str | None:
        """Try to parse a service selection from user message.

        Returns service_type string or None if not a service selection.
        """
        msg = message.strip()

        # Direct number selection
        if msg in SERVICE_TYPE_MAP:
            return SERVICE_TYPE_MAP[msg]

        # Keyword matching
        msg_lower = msg.lower()
        keyword_map = {
            "tính thuế": "tax_calculation",
            "kê khai": "tax_declaration",
            "quyết toán": "annual_settlement",
            "đăng ký": "tax_registration",
            "mã số thuế": "tax_registration",
            "tra cứu": "tax_consultation",
            "quy định": "tax_consultation",
            "hóa đơn": "invoice_check",
            "chứng từ": "invoice_check",
            "xử phạt": "penalty_consultation",
            "vi phạm": "penalty_consultation",
            "hoàn thuế": "tax_refund",
        }
        for keyword, stype in keyword_map.items():
            if keyword in msg_lower:
                return stype

        return None
