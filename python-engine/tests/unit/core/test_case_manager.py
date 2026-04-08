"""
Tests for the CaseManager and service step definitions.
"""

import pytest

from core.case_manager import CaseManager, SERVICE_STEPS
from core.onboarding import SERVICE_TITLE_MAP


class TestServiceSteps:
    def test_all_service_types_have_steps(self):
        """Every service type in SERVICE_TITLE_MAP should have steps defined."""
        for service_type in SERVICE_TITLE_MAP:
            assert service_type in SERVICE_STEPS, f"Missing steps for {service_type}"

    def test_all_steps_start_with_step_1(self):
        """Every service should start with step_1."""
        for service_type, steps in SERVICE_STEPS.items():
            step_keys = list(steps.keys())
            assert step_keys[0] == "step_1", f"{service_type} first step is {step_keys[0]}"

    def test_all_steps_have_name(self):
        """Every step should have a 'name' key."""
        for service_type, steps in SERVICE_STEPS.items():
            for step_key, step_info in steps.items():
                assert "name" in step_info, f"{service_type}/{step_key} missing 'name'"

    def test_all_steps_have_prompt_key(self):
        """Every step should have a 'prompt' key (can be None for auto steps)."""
        for service_type, steps in SERVICE_STEPS.items():
            for step_key, step_info in steps.items():
                assert "prompt" in step_info, f"{service_type}/{step_key} missing 'prompt'"

    @pytest.mark.parametrize("service_type,expected_step_count", [
        ("tax_calculation", 3),
        ("tax_declaration", 3),
        ("tax_registration", 3),
        ("tax_consultation", 2),
        ("invoice_check", 3),
        ("tax_refund", 3),
        ("penalty_consultation", 2),
        ("annual_settlement", 3),
    ])
    def test_step_counts(self, service_type, expected_step_count):
        assert len(SERVICE_STEPS[service_type]) == expected_step_count


class TestCaseManagerHelpers:
    def test_get_step_prompt(self):
        # We can test the static method without a real repo
        manager = CaseManager.__new__(CaseManager)
        prompt = manager.get_step_prompt("tax_calculation", "step_1")
        assert prompt is not None
        assert "loại thuế" in prompt.lower()

    def test_get_step_prompt_auto_step(self):
        manager = CaseManager.__new__(CaseManager)
        prompt = manager.get_step_prompt("tax_calculation", "step_3")
        assert prompt is None  # Auto step

    def test_get_step_name(self):
        manager = CaseManager.__new__(CaseManager)
        name = manager.get_step_name("tax_declaration", "step_1")
        assert name == "Xác định tờ khai"

    def test_build_case_status_message(self):
        manager = CaseManager.__new__(CaseManager)
        case = {
            "service_type": "tax_declaration",
            "current_step": "step_2",
            "status": "in_progress",
        }
        msg = manager.build_case_status_message(case)
        assert "Kê khai" in msg
        assert "Hướng dẫn điền" in msg
        assert "in_progress" in msg
