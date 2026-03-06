"""
Tests for the long-term memory context builder.
"""

import pytest

from core.memory import build_memory_context


class TestBuildMemoryContext:
    def test_empty_customer(self):
        assert build_memory_context(None) == ""

    def test_new_customer_returns_empty(self):
        customer = {"onboarding_step": "new"}
        assert build_memory_context(customer) == ""

    def test_basic_sme_profile(self):
        customer = {
            "customer_type": "sme",
            "business_name": "ABC Corp",
            "tax_code": "0123456789",
            "industry": "Thương mại",
            "province": "Hà Nội",
            "onboarding_step": "completed",
            "preferences": {},
            "tax_profile": {},
            "notes": [],
        }
        result = build_memory_context(customer)
        assert "THÔNG TIN KHÁCH HÀNG" in result
        assert "ABC Corp" in result
        assert "0123456789" in result
        assert "Thương mại" in result
        assert "Hà Nội" in result
        assert "SME" in result

    def test_household_profile(self):
        customer = {
            "customer_type": "household",
            "onboarding_step": "completed",
            "annual_revenue_range": "100m_1b",
            "preferences": {},
            "tax_profile": {},
            "notes": [],
        }
        result = build_memory_context(customer)
        assert "Hộ kinh doanh" in result
        assert "100 triệu - 1 tỷ" in result

    def test_with_tax_profile(self):
        customer = {
            "customer_type": "sme",
            "onboarding_step": "completed",
            "tax_profile": {
                "vat_method": "khấu trừ",
                "registered_taxes": ["vat", "cit"],
            },
            "notes": [],
        }
        result = build_memory_context(customer)
        assert "khấu trừ" in result
        assert "vat, cit" in result

    def test_with_notes(self):
        customer = {
            "customer_type": "sme",
            "onboarding_step": "completed",
            "tax_profile": {},
            "notes": [
                {"date": "2026-02-20T10:00:00", "note": "Cần hoàn thuế GTGT Q2"},
                {"date": "2026-02-25T14:00:00", "note": "Đã nộp tờ khai TNDN"},
            ],
        }
        result = build_memory_context(customer)
        assert "Cần hoàn thuế GTGT Q2" in result
        assert "Đã nộp tờ khai TNDN" in result

    def test_with_active_cases(self):
        customer = {
            "customer_type": "sme",
            "onboarding_step": "completed",
            "tax_profile": {},
            "notes": [],
        }
        cases = [
            {
                "service_type": "tax_declaration",
                "title": "Kê khai thuế GTGT Q1/2026",
                "status": "in_progress",
                "current_step": "step_2",
            },
        ]
        result = build_memory_context(customer, active_cases=cases)
        assert "HỖ TRỢ ĐANG TIẾN HÀNH" in result
        assert "Kê khai thuế GTGT Q1/2026" in result
        assert "in_progress" in result

    def test_with_summaries(self):
        customer = {
            "customer_type": "individual",
            "onboarding_step": "completed",
            "tax_profile": {},
            "notes": [],
        }
        summaries = ["KH hỏi về thuế TNCN lương 30 triệu, 2 người phụ thuộc"]
        result = build_memory_context(customer, recent_summaries=summaries)
        assert "TÓM TẮT CUỘC TRÒ CHUYỆN" in result
        assert "thuế TNCN" in result

    def test_full_context(self):
        customer = {
            "customer_type": "sme",
            "business_name": "DEF Corp",
            "onboarding_step": "completed",
            "annual_revenue_range": "1b_10b",
            "tax_profile": {"vat_method": "khấu trừ"},
            "notes": [{"date": "2026-03-01", "note": "Quyết toán năm 2025"}],
        }
        cases = [{"service_type": "annual_settlement", "title": "QT 2025",
                  "status": "in_progress", "current_step": "step_2"}]
        summaries = ["Đã tư vấn quyết toán thuế TNDN 2025"]
        result = build_memory_context(customer, cases, summaries)
        assert "DEF Corp" in result
        assert "1 - 10 tỷ" in result
        assert "QT 2025" in result
        assert "Đã tư vấn quyết toán" in result

    def test_display_name_in_context(self):
        customer = {
            "customer_type": "sme",
            "onboarding_step": "completed",
            "display_name": "Nguyen Van An",
            "username": "anvan",
            "tax_profile": {},
            "notes": [],
        }
        result = build_memory_context(customer)
        assert "Nguyen Van An" in result

    def test_first_name_in_context_when_no_display_name(self):
        customer = {
            "customer_type": "individual",
            "onboarding_step": "completed",
            "first_name": "Lan",
            "tax_profile": {},
            "notes": [],
        }
        result = build_memory_context(customer)
        assert "Lan" in result

    def test_username_displayed_in_context(self):
        customer = {
            "customer_type": "individual",
            "onboarding_step": "completed",
            "username": "lannguyen",
            "tax_profile": {},
            "notes": [],
        }
        result = build_memory_context(customer)
        assert "@lannguyen" in result
