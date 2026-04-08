"""
Unit tests for the user profile management handler.
"""

import pytest

from app.core.profile_handler import ProfileHandler, PROFILE_FIELDS


@pytest.fixture
def handler():
    return ProfileHandler()


def _make_customer(customer_type="individual", **overrides):
    """Helper to create a customer dict for testing."""
    base = {
        "customer_id": "test-uuid",
        "customer_type": customer_type,
        "username": "testuser",
        "first_name": "",
        "last_name": "",
        "display_name": "",
        "business_name": "",
        "tax_code": "",
        "industry": "",
        "province": "",
        "annual_revenue_range": "",
        "employee_count_range": "",
        "email": "",
        "phone": "",
        "address": "",
        "profile_data": {},
        "onboarding_step": "completed",
    }
    base.update(overrides)
    return base


class TestViewProfile:
    def test_view_individual_profile(self, handler):
        customer = _make_customer("individual", first_name="Nguyễn Văn A")
        result = handler.view_profile(customer)

        assert "Thông tin của bạn" in result["reply"]
        assert "Cá nhân kinh doanh" in result["reply"]
        assert "Nguyễn Văn A" in result["reply"]
        assert len(result["actions"]) > 0

    def test_view_sme_profile(self, handler):
        customer = _make_customer("sme", business_name="Công ty ABC", tax_code="0123456789")
        result = handler.view_profile(customer)

        assert "Doanh nghiệp" in result["reply"]
        assert "Công ty ABC" in result["reply"]
        assert "0123456789" in result["reply"]

    def test_view_household_profile(self, handler):
        customer = _make_customer("household", business_name="Cửa hàng XYZ", first_name="Trần B")
        result = handler.view_profile(customer)

        assert "Hộ kinh doanh" in result["reply"]
        assert "Cửa hàng XYZ" in result["reply"]
        assert "Trần B" in result["reply"]

    def test_view_unknown_type_defaults_to_individual(self, handler):
        customer = _make_customer("unknown")
        result = handler.view_profile(customer)

        assert "Chưa xác định" in result["reply"]
        assert "actions" in result

    def test_completion_tracking_empty(self, handler):
        customer = _make_customer("individual")
        result = handler.view_profile(customer)

        assert "0%" in result["reply"] or "0/" in result["reply"]

    def test_completion_tracking_partial(self, handler):
        customer = _make_customer("individual", first_name="Test", email="test@test.com")
        result = handler.view_profile(customer)

        # 2 out of 7 fields filled
        assert "2/7" in result["reply"]

    def test_completion_tracking_full(self, handler):
        customer = _make_customer(
            "individual",
            first_name="Test",
            email="t@t.com",
            phone="0901234567",
            address="HCM",
            profile_data={
                "marital_status": "Độc thân",
                "occupation": "Kỹ sư",
                "estimated_income": "30 triệu",
            },
        )
        result = handler.view_profile(customer)

        assert "7/7" in result["reply"]
        assert "100%" in result["reply"]

    def test_username_displayed(self, handler):
        customer = _make_customer("individual", username="john_doe")
        result = handler.view_profile(customer)

        assert "@john_doe" in result["reply"]

    def test_profile_data_jsonb_fields(self, handler):
        customer = _make_customer(
            "individual",
            profile_data={"occupation": "Kế toán"},
        )
        result = handler.view_profile(customer)

        assert "Kế toán" in result["reply"]


class TestEditProfile:
    def test_edit_email(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "sửa email thành abc@gmail.com")

        assert "Đã cập nhật" in result["reply"]
        assert "abc@gmail.com" in result["reply"]
        assert result["update_fields"]["email"] == "abc@gmail.com"

    def test_edit_phone(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "đổi số điện thoại thành 0901234567")

        assert "Đã cập nhật" in result["reply"]
        assert result["update_fields"]["phone"] == "0901234567"

    def test_edit_business_name(self, handler):
        customer = _make_customer("sme")
        result = handler.edit_profile(customer, "cập nhật tên công ty là Công ty ABC")

        assert "Đã cập nhật" in result["reply"]
        assert result["update_fields"]["business_name"] == "Công ty ABC"

    def test_edit_tax_code(self, handler):
        customer = _make_customer("sme")
        result = handler.edit_profile(customer, "sửa mã số thuế thành 0123456789")

        assert "Đã cập nhật" in result["reply"]
        assert result["update_fields"]["tax_code"] == "0123456789"

    def test_edit_address(self, handler):
        customer = _make_customer("household")
        result = handler.edit_profile(customer, "đổi địa chỉ thành 123 Lê Lợi, Q1, HCM")

        assert "Đã cập nhật" in result["reply"]
        assert result["update_fields"]["address"] == "123 Lê Lợi, Q1, HCM"

    def test_edit_profile_data_field(self, handler):
        """Fields not in _MODEL_FIELDS should be stored in profile_data."""
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "sửa nghề nghiệp thành Kế toán")

        assert "Đã cập nhật" in result["reply"]
        assert "profile_data" in result["update_fields"]
        assert result["update_fields"]["profile_data"]["occupation"] == "Kế toán"

    def test_edit_unknown_field(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "sửa xyz thành abc")

        assert "Không nhận ra" in result["reply"]
        assert result["update_fields"] == {}

    def test_edit_no_pattern_match(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "tôi muốn thay đổi thông tin")

        # Should show edit help
        assert "Để cập nhật" in result["reply"]
        assert result["update_fields"] == {}


class TestFieldSynonymRecognition:
    def test_synonym_ten(self, handler):
        assert handler._resolve_field_name("tên") == "first_name"

    def test_synonym_mst(self, handler):
        assert handler._resolve_field_name("MST") == "tax_code"

    def test_synonym_sdt(self, handler):
        assert handler._resolve_field_name("sdt") == "phone"

    def test_synonym_email(self, handler):
        assert handler._resolve_field_name("email") == "email"

    def test_synonym_dia_chi(self, handler):
        assert handler._resolve_field_name("địa chỉ") == "address"

    def test_synonym_nganh_nghe(self, handler):
        assert handler._resolve_field_name("ngành nghề") == "industry"

    def test_synonym_von_dieu_le(self, handler):
        assert handler._resolve_field_name("vốn điều lệ") == "charter_capital"

    def test_synonym_loai_hinh(self, handler):
        assert handler._resolve_field_name("loại hình") == "business_structure"

    def test_unknown_synonym(self, handler):
        assert handler._resolve_field_name("abcdef") is None


class TestInputValidation:
    def test_valid_email(self, handler):
        assert handler._validate_field("email", "test@example.com") is None

    def test_invalid_email(self, handler):
        error = handler._validate_field("email", "not-an-email")
        assert error is not None
        assert "không hợp lệ" in error

    def test_valid_phone(self, handler):
        assert handler._validate_field("phone", "0901234567") is None

    def test_valid_phone_with_country_code(self, handler):
        assert handler._validate_field("phone", "+84901234567") is None

    def test_invalid_phone(self, handler):
        error = handler._validate_field("phone", "123")
        assert error is not None
        assert "không hợp lệ" in error

    def test_valid_tax_code_10_digits(self, handler):
        assert handler._validate_field("tax_code", "0123456789") is None

    def test_valid_tax_code_13_digits(self, handler):
        assert handler._validate_field("tax_code", "0123456789-001") is None

    def test_invalid_tax_code(self, handler):
        error = handler._validate_field("tax_code", "12345")
        assert error is not None
        assert "không hợp lệ" in error

    def test_valid_founding_year(self, handler):
        assert handler._validate_field("founding_year", "2020") is None

    def test_invalid_founding_year(self, handler):
        error = handler._validate_field("founding_year", "20")
        assert error is not None
        assert "không hợp lệ" in error

    def test_no_validation_for_general_field(self, handler):
        """Fields without specific validation should pass."""
        assert handler._validate_field("industry", "Thương mại") is None
        assert handler._validate_field("address", "123 ABC") is None


class TestBusinessTypeChange:
    def test_change_to_sme(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "sửa loại thành doanh nghiệp")

        assert "Doanh nghiệp" in result["reply"]
        assert result["update_fields"]["customer_type"] == "sme"

    def test_change_to_household(self, handler):
        customer = _make_customer("sme")
        result = handler.edit_profile(customer, "đổi loại thành hộ kinh doanh")

        assert "Hộ kinh doanh" in result["reply"]
        assert result["update_fields"]["customer_type"] == "household"

    def test_change_to_individual(self, handler):
        customer = _make_customer("sme")
        result = handler.edit_profile(customer, "cập nhật loại là cá nhân")

        assert "Cá nhân" in result["reply"]
        assert result["update_fields"]["customer_type"] == "individual"

    def test_invalid_type_change(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "sửa loại thành xyz")

        assert "không hợp lệ" in result["reply"]
        assert result["update_fields"] == {}

    def test_data_migration_reports_kept_fields(self, handler):
        """Common fields between types should be reported as kept."""
        customer = _make_customer("sme", business_name="Test", industry="IT")
        result = handler.edit_profile(customer, "sửa loại thành hộ kinh doanh")

        assert "tương thích" in result["reply"]


class TestEditPatterns:
    """Test various Vietnamese edit command patterns."""

    def test_doi_pattern(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "đổi email thành test@test.com")
        assert result["update_fields"].get("email") == "test@test.com"

    def test_cap_nhat_pattern(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "cập nhật email là test@test.com")
        assert result["update_fields"].get("email") == "test@test.com"

    def test_sua_pattern(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "sửa email thành test@test.com")
        assert result["update_fields"].get("email") == "test@test.com"

    def test_thay_doi_pattern(self, handler):
        customer = _make_customer("individual")
        result = handler.edit_profile(customer, "thay đổi email thành test@test.com")
        assert result["update_fields"].get("email") == "test@test.com"


class TestProfileFields:
    def test_individual_has_required_fields(self):
        fields = PROFILE_FIELDS["individual"]
        field_keys = [k for k, _, _ in fields]
        assert "first_name" in field_keys
        assert "email" in field_keys
        assert "phone" in field_keys

    def test_household_has_required_fields(self):
        fields = PROFILE_FIELDS["household"]
        field_keys = [k for k, _, _ in fields]
        assert "business_name" in field_keys
        assert "first_name" in field_keys
        assert "industry" in field_keys

    def test_sme_has_required_fields(self):
        fields = PROFILE_FIELDS["sme"]
        field_keys = [k for k, _, _ in fields]
        assert "business_name" in field_keys
        assert "tax_code" in field_keys
        assert "charter_capital" in field_keys
        assert "business_structure" in field_keys


class TestBackwardCompatibility:
    def test_customer_without_new_fields(self, handler):
        """Existing customers without email/phone/profile_data should work."""
        customer = {
            "customer_id": "old-uuid",
            "customer_type": "sme",
            "username": "old_user",
            "first_name": "Old",
            "business_name": "Old Corp",
            "tax_code": "0123456789",
            "onboarding_step": "completed",
            # Missing: email, phone, address, profile_data
        }
        result = handler.view_profile(customer)

        assert "Old Corp" in result["reply"]
        assert "0123456789" in result["reply"]
        assert "actions" in result

    def test_edit_works_without_profile_data(self, handler):
        """Edit should work even if customer has no profile_data field."""
        customer = {
            "customer_id": "old-uuid",
            "customer_type": "individual",
            "onboarding_step": "completed",
        }
        result = handler.edit_profile(customer, "sửa nghề nghiệp thành Kế toán")

        assert "Đã cập nhật" in result["reply"]
        assert "profile_data" in result["update_fields"]
