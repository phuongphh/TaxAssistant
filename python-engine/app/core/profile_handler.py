"""
User profile management handler.

Handles viewing and editing user profiles with dynamic fields
based on business type (individual, household, enterprise/SME).
"""

import re
import logging

logger = logging.getLogger(__name__)


# Dynamic profile fields per business type.
# Each entry: (field_key, display_label, required)
PROFILE_FIELDS = {
    "individual": [
        ("first_name", "Họ tên", True),
        ("email", "Email", False),
        ("phone", "Số điện thoại", False),
        ("address", "Địa chỉ", False),
        ("marital_status", "Tình trạng hôn nhân", False),
        ("occupation", "Nghề nghiệp", False),
        ("estimated_income", "Thu nhập ước tính", False),
    ],
    "household": [
        ("business_name", "Tên cửa hàng", True),
        ("first_name", "Chủ hộ", True),
        ("address", "Địa chỉ kinh doanh", False),
        ("industry", "Ngành nghề", False),
        ("founding_year", "Năm thành lập", False),
        ("employee_count_range", "Số nhân viên", False),
        ("annual_revenue_range", "Doanh thu ước tính", False),
    ],
    "sme": [
        ("business_name", "Tên công ty", True),
        ("tax_code", "Mã số thuế", True),
        ("address", "Địa chỉ trụ sở", False),
        ("industry", "Ngành nghề", False),
        ("founding_year", "Năm thành lập", False),
        ("employee_count_range", "Quy mô nhân sự", False),
        ("charter_capital", "Vốn điều lệ", False),
        ("business_structure", "Loại hình DN", False),
    ],
}

# Fields stored directly on Customer model vs in profile_data JSONB
_MODEL_FIELDS = {
    "first_name", "last_name", "business_name", "tax_code",
    "industry", "province", "annual_revenue_range", "employee_count_range",
    "email", "phone", "address", "customer_type",
}

# Synonym map: Vietnamese field names → canonical field key
_FIELD_SYNONYMS = {
    # Name
    "tên": "first_name",
    "họ tên": "first_name",
    "họ và tên": "first_name",
    "tên đầy đủ": "first_name",
    "name": "first_name",
    # Business name
    "tên công ty": "business_name",
    "tên cửa hàng": "business_name",
    "tên doanh nghiệp": "business_name",
    "công ty": "business_name",
    "cửa hàng": "business_name",
    # Tax code
    "mã số thuế": "tax_code",
    "mst": "tax_code",
    "tax code": "tax_code",
    # Email
    "email": "email",
    "mail": "email",
    # Phone
    "số điện thoại": "phone",
    "điện thoại": "phone",
    "sdt": "phone",
    "sđt": "phone",
    "phone": "phone",
    # Address
    "địa chỉ": "address",
    "địa chỉ trụ sở": "address",
    "địa chỉ kinh doanh": "address",
    "trụ sở": "address",
    # Industry
    "ngành nghề": "industry",
    "ngành": "industry",
    "lĩnh vực": "industry",
    # Province
    "tỉnh": "province",
    "tỉnh thành": "province",
    "thành phố": "province",
    # Revenue
    "doanh thu": "annual_revenue_range",
    "doanh thu ước tính": "annual_revenue_range",
    "thu nhập": "estimated_income",
    "thu nhập ước tính": "estimated_income",
    # Employee
    "số nhân viên": "employee_count_range",
    "nhân sự": "employee_count_range",
    "quy mô nhân sự": "employee_count_range",
    "quy mô": "employee_count_range",
    # Marital status
    "tình trạng hôn nhân": "marital_status",
    "hôn nhân": "marital_status",
    # Occupation
    "nghề nghiệp": "occupation",
    "nghề": "occupation",
    "công việc": "occupation",
    # Founding year
    "năm thành lập": "founding_year",
    "thành lập": "founding_year",
    # Charter capital
    "vốn điều lệ": "charter_capital",
    "vốn": "charter_capital",
    # Business structure
    "loại hình": "business_structure",
    "loại hình doanh nghiệp": "business_structure",
    "loại hình dn": "business_structure",
    # Customer type
    "loại khách hàng": "customer_type",
    "loại": "customer_type",
    # Owner (household)
    "chủ hộ": "first_name",
}

# Customer type labels
_TYPE_LABELS = {
    "sme": "Doanh nghiệp",
    "household": "Hộ kinh doanh",
    "individual": "Cá nhân kinh doanh",
    "unknown": "Chưa xác định",
}

# Edit command patterns: "đổi X thành Y", "cập nhật X là Y", "sửa X thành Y"
_EDIT_PATTERNS = [
    re.compile(r"(?:đổi|thay đổi)\s+(.+?)\s+(?:thành|sang|là)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:cập nhật|update)\s+(.+?)\s+(?:thành|sang|là)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:sửa|chỉnh sửa|edit)\s+(.+?)\s+(?:thành|sang|là)\s+(.+)", re.IGNORECASE),
]


class ProfileHandler:
    """Handles user profile viewing and editing."""

    def view_profile(self, customer: dict) -> dict:
        """Format and display user profile.

        Args:
            customer: Customer profile dict from repository.

        Returns:
            dict with keys: reply, actions, update_fields
        """
        customer_type = customer.get("customer_type", "unknown")
        type_label = _TYPE_LABELS.get(customer_type, "Chưa xác định")

        lines = [f"👤 **Thông tin của bạn**\n"]
        lines.append(f"Loại khách hàng: {type_label}")

        # Telegram info
        username = customer.get("username", "")
        if username:
            lines.append(f"Username: @{username}")

        # Dynamic fields based on customer type
        fields = PROFILE_FIELDS.get(customer_type, PROFILE_FIELDS.get("individual", []))
        filled = 0
        total = len(fields)

        for field_key, label, _required in fields:
            value = self._get_field_value(customer, field_key)
            if value:
                lines.append(f"{label}: {value}")
                filled += 1
            else:
                lines.append(f"{label}: —")

        # Completion tracking
        completion = (filled / total * 100) if total > 0 else 0
        lines.append(f"\n📊 Hoàn thiện: {filled}/{total} ({completion:.0f}%)")

        if completion < 100:
            lines.append(
                '\nĐể cập nhật, gõ: "sửa [trường] thành [giá trị]"'
                '\nVí dụ: "sửa email thành abc@gmail.com"'
            )

        reply = "\n".join(lines)

        actions = [
            {"label": "Sửa thông tin", "action_type": "quick_reply", "payload": "/profile edit"},
            {"label": "Quay lại menu", "action_type": "quick_reply", "payload": "/start"},
        ]

        return {
            "reply": reply,
            "actions": actions,
            "update_fields": {},
        }

    def edit_profile(self, customer: dict, message: str) -> dict:
        """Parse natural language edit command and return update.

        Args:
            customer: Customer profile dict.
            message: User's edit message.

        Returns:
            dict with keys: reply, actions, update_fields
        """
        field_name, value = self._parse_edit_command(message)

        if not field_name or not value:
            return self._prompt_edit_help(customer)

        customer_type = customer.get("customer_type", "unknown")
        canonical = self._resolve_field_name(field_name)

        if not canonical:
            return {
                "reply": (
                    f'Không nhận ra trường "{field_name}".\n'
                    "Các trường hợp lệ: " + self._list_editable_fields(customer_type)
                ),
                "actions": [
                    {"label": "Xem hồ sơ", "action_type": "quick_reply", "payload": "thông tin của tôi"},
                ],
                "update_fields": {},
            }

        # Handle customer_type change with data migration
        if canonical == "customer_type":
            return self._handle_type_change(customer, value)

        # Validate field value
        error = self._validate_field(canonical, value)
        if error:
            return {
                "reply": error,
                "actions": [
                    {"label": "Xem hồ sơ", "action_type": "quick_reply", "payload": "thông tin của tôi"},
                ],
                "update_fields": {},
            }

        # Build display label
        display_label = self._get_display_label(canonical, customer_type)

        # Determine where to store
        update_fields = self._build_update(customer, canonical, value)

        return {
            "reply": f'Đã cập nhật {display_label}: {value}',
            "actions": [
                {"label": "Xem hồ sơ", "action_type": "quick_reply", "payload": "thông tin của tôi"},
                {"label": "Quay lại menu", "action_type": "quick_reply", "payload": "/start"},
            ],
            "update_fields": update_fields,
        }

    def _parse_edit_command(self, message: str) -> tuple[str | None, str | None]:
        """Extract field name and value from a natural language edit command."""
        for pattern in _EDIT_PATTERNS:
            match = pattern.search(message)
            if match:
                return match.group(1).strip(), match.group(2).strip()
        return None, None

    def _resolve_field_name(self, raw_name: str) -> str | None:
        """Map user-provided field name to canonical field key."""
        normalized = raw_name.lower().strip()
        return _FIELD_SYNONYMS.get(normalized)

    def _validate_field(self, field: str, value: str) -> str | None:
        """Validate field value. Returns error message or None if valid."""
        if field == "email":
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
                return f'Email "{value}" không hợp lệ. Ví dụ: ten@email.com'

        if field == "phone":
            cleaned = re.sub(r"[\s\-\.]", "", value)
            if not re.match(r"^(\+84|0)\d{9,10}$", cleaned):
                return f'Số điện thoại "{value}" không hợp lệ. Ví dụ: 0901234567'

        if field == "tax_code":
            cleaned = value.replace("-", "").replace(" ", "")
            if not re.match(r"^\d{10}(\d{3})?$", cleaned):
                return f'Mã số thuế "{value}" không hợp lệ. MST gồm 10 hoặc 13 chữ số.'

        if field == "founding_year":
            if not re.match(r"^\d{4}$", value):
                return f'Năm thành lập "{value}" không hợp lệ. Ví dụ: 2020'

        return None

    def _get_field_value(self, customer: dict, field_key: str) -> str:
        """Get a field value from customer dict, checking both model fields and profile_data."""
        # Check model-level fields first
        value = customer.get(field_key, "")
        if value:
            return str(value)

        # Check profile_data JSONB
        profile_data = customer.get("profile_data") or {}
        return str(profile_data.get(field_key, ""))

    def _build_update(self, customer: dict, field: str, value: str) -> dict:
        """Build update_fields dict, routing to model field or profile_data."""
        if field in _MODEL_FIELDS:
            return {field: value}

        # Store in profile_data JSONB
        profile_data = dict(customer.get("profile_data") or {})
        profile_data[field] = value
        return {"profile_data": profile_data}

    def _get_display_label(self, field: str, customer_type: str) -> str:
        """Get Vietnamese display label for a field."""
        fields = PROFILE_FIELDS.get(customer_type, [])
        for key, label, _ in fields:
            if key == field:
                return label
        # Fallback: check all types
        for _type, type_fields in PROFILE_FIELDS.items():
            for key, label, _ in type_fields:
                if key == field:
                    return label
        return field

    def _list_editable_fields(self, customer_type: str) -> str:
        """List all editable field labels for a customer type."""
        fields = PROFILE_FIELDS.get(customer_type, PROFILE_FIELDS.get("individual", []))
        labels = [label for _, label, _ in fields]
        return ", ".join(labels)

    def _handle_type_change(self, customer: dict, new_type_raw: str) -> dict:
        """Handle business type change with compatible data migration."""
        type_map = {
            "doanh nghiệp": "sme", "sme": "sme", "dn": "sme",
            "công ty": "sme", "cty": "sme",
            "hộ kinh doanh": "household", "hộ": "household", "hkd": "household",
            "cá nhân": "individual", "cá thể": "individual",
        }
        new_type = type_map.get(new_type_raw.lower().strip())
        if not new_type:
            return {
                "reply": (
                    f'Loại khách hàng "{new_type_raw}" không hợp lệ.\n'
                    "Chọn: Doanh nghiệp, Hộ kinh doanh, hoặc Cá nhân"
                ),
                "actions": [
                    {"label": "Doanh nghiệp", "action_type": "quick_reply", "payload": "sửa loại thành doanh nghiệp"},
                    {"label": "Hộ kinh doanh", "action_type": "quick_reply", "payload": "sửa loại thành hộ kinh doanh"},
                    {"label": "Cá nhân", "action_type": "quick_reply", "payload": "sửa loại thành cá nhân"},
                ],
                "update_fields": {},
            }

        old_type = customer.get("customer_type", "unknown")
        new_label = _TYPE_LABELS.get(new_type, new_type)

        # Migrate compatible fields (fields that exist in both old and new type)
        old_fields = {k for k, _, _ in PROFILE_FIELDS.get(old_type, [])}
        new_fields = {k for k, _, _ in PROFILE_FIELDS.get(new_type, [])}
        kept = old_fields & new_fields
        lost = old_fields - new_fields

        reply_parts = [f"Đã chuyển loại khách hàng sang: {new_label}"]
        if kept:
            reply_parts.append(f"Giữ lại {len(kept)} trường tương thích.")
        if lost:
            lost_labels = []
            for k, label, _ in PROFILE_FIELDS.get(old_type, []):
                if k in lost:
                    lost_labels.append(label)
            reply_parts.append(f"Các trường không áp dụng: {', '.join(lost_labels)}")

        return {
            "reply": "\n".join(reply_parts),
            "actions": [
                {"label": "Xem hồ sơ", "action_type": "quick_reply", "payload": "thông tin của tôi"},
            ],
            "update_fields": {"customer_type": new_type},
        }

    def _prompt_edit_help(self, customer: dict) -> dict:
        """Show edit instructions when command is unclear."""
        customer_type = customer.get("customer_type", "unknown")
        fields = PROFILE_FIELDS.get(customer_type, PROFILE_FIELDS.get("individual", []))
        examples = []
        for key, label, _ in fields[:3]:
            examples.append(f'• "sửa {label.lower()} thành ..."')

        reply = (
            "Để cập nhật thông tin, hãy gõ:\n"
            + "\n".join(examples)
            + '\n• "sửa loại thành Doanh nghiệp/Hộ kinh doanh/Cá nhân"'
        )

        return {
            "reply": reply,
            "actions": [
                {"label": "Xem hồ sơ", "action_type": "quick_reply", "payload": "thông tin của tôi"},
            ],
            "update_fields": {},
        }
