"""
Tests for the onboarding flow.
"""

import pytest

from core.onboarding import OnboardingHandler, SERVICE_TYPE_MAP


@pytest.fixture
def handler():
    return OnboardingHandler()


# ---- Welcome step (new customer) ----

class TestWelcomeStep:
    def test_new_customer_gets_welcome(self, handler):
        customer = {"onboarding_step": "new"}
        result = handler.process_step(customer, "xin chào")
        assert "Xin chào" in result["reply"]
        assert "Dịch vụ của chúng tôi" in result["reply"]
        assert result["next_step"] == "collecting_type"
        assert not result["onboarding_complete"]

    def test_welcome_has_quick_replies(self, handler):
        customer = {"onboarding_step": "new"}
        result = handler.process_step(customer, "hi")
        assert len(result["actions"]) == 3
        labels = {a["label"] for a in result["actions"]}
        assert "Doanh nghiệp" in labels
        assert "Hộ kinh doanh" in labels


# ---- Collecting type step ----

class TestCollectTypeStep:
    def test_sme_selection(self, handler):
        customer = {"onboarding_step": "collecting_type"}
        result = handler.process_step(customer, "Doanh nghiệp")
        assert result["update_fields"]["customer_type"] == "sme"
        assert result["next_step"] == "collecting_info"

    def test_household_selection(self, handler):
        customer = {"onboarding_step": "collecting_type"}
        result = handler.process_step(customer, "Hộ kinh doanh")
        assert result["update_fields"]["customer_type"] == "household"

    def test_individual_selection(self, handler):
        customer = {"onboarding_step": "collecting_type"}
        result = handler.process_step(customer, "cá nhân")
        assert result["update_fields"]["customer_type"] == "individual"

    def test_number_selection_1(self, handler):
        customer = {"onboarding_step": "collecting_type"}
        result = handler.process_step(customer, "1")
        assert result["update_fields"]["customer_type"] == "sme"

    def test_number_selection_2(self, handler):
        customer = {"onboarding_step": "collecting_type"}
        result = handler.process_step(customer, "2")
        assert result["update_fields"]["customer_type"] == "household"

    def test_number_selection_3(self, handler):
        customer = {"onboarding_step": "collecting_type"}
        result = handler.process_step(customer, "3")
        assert result["update_fields"]["customer_type"] == "individual"

    def test_invalid_input_retries(self, handler):
        customer = {"onboarding_step": "collecting_type"}
        result = handler.process_step(customer, "xin chào tôi muốn hỏi")
        assert result["next_step"] == "collecting_type"
        assert "chưa hiểu" in result["reply"]

    def test_cty_keyword(self, handler):
        customer = {"onboarding_step": "collecting_type"}
        result = handler.process_step(customer, "cty")
        assert result["update_fields"]["customer_type"] == "sme"


# ---- Collecting info step ----

class TestCollectInfoStep:
    def test_skip_info(self, handler):
        customer = {"onboarding_step": "collecting_info", "customer_type": "sme"}
        result = handler.process_step(customer, "bỏ qua")
        assert result["onboarding_complete"]
        assert result["update_fields"]["onboarding_step"] == "completed"
        assert "Dịch vụ của chúng tôi" in result["reply"]

    def test_extract_tax_code(self, handler):
        customer = {"onboarding_step": "collecting_info", "customer_type": "sme"}
        result = handler.process_step(customer, "MST của tôi là 0123456789")
        assert result["update_fields"].get("tax_code") == "0123456789"
        assert result["onboarding_complete"]

    def test_extract_company_name(self, handler):
        customer = {"onboarding_step": "collecting_info", "customer_type": "sme"}
        result = handler.process_step(customer, "Công ty TNHH ABC Việt Nam")
        assert "Công ty TNHH ABC Việt Nam" in result["update_fields"].get("business_name", "")
        assert result["onboarding_complete"]

    def test_extract_industry(self, handler):
        customer = {"onboarding_step": "collecting_info", "customer_type": "household"}
        result = handler.process_step(customer, "Tôi kinh doanh nhà hàng ăn uống")
        assert "Nhà hàng" in result["update_fields"].get("industry", "")

    def test_extract_revenue_range(self, handler):
        customer = {"onboarding_step": "collecting_info", "customer_type": "household"}
        result = handler.process_step(customer, "doanh thu khoảng 500 triệu")
        assert result["update_fields"].get("annual_revenue_range") == "100m_1b"


# ---- Completed step (returning customer) ----

class TestCompletedStep:
    def test_returning_customer_gets_service_menu(self, handler):
        customer = {"onboarding_step": "completed", "business_name": "ABC Corp"}
        result = handler.process_step(customer, "xin chào")
        assert "ABC Corp" in result["reply"]
        assert "Dịch vụ của chúng tôi" in result["reply"]
        assert not result["onboarding_complete"]


# ---- Service selection parsing ----

class TestServiceSelection:
    @pytest.mark.parametrize("input_text,expected", [
        ("1", "tax_calculation"),
        ("2", "tax_declaration"),
        ("3", "tax_registration"),
        ("4", "tax_consultation"),
        ("5", "invoice_check"),
        ("6", "penalty_consultation"),
        ("7", "tax_refund"),
        ("8", "annual_settlement"),
    ])
    def test_number_selections(self, input_text, expected):
        result = OnboardingHandler.parse_service_selection(input_text)
        assert result == expected

    def test_keyword_selection(self):
        assert OnboardingHandler.parse_service_selection("tính thuế") == "tax_calculation"
        assert OnboardingHandler.parse_service_selection("kê khai") == "tax_declaration"
        assert OnboardingHandler.parse_service_selection("hoàn thuế") == "tax_refund"

    def test_no_match(self):
        assert OnboardingHandler.parse_service_selection("xin chào") is None
