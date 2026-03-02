"""
Support case lifecycle management.

Manages the creation, progression, and completion of support cases that track
multi-step service requests from customers.
"""

import logging
import uuid

from app.db.case_repository import CaseRepository
from app.core.onboarding import SERVICE_TITLE_MAP

logger = logging.getLogger(__name__)

# Step definitions for each service type
SERVICE_STEPS = {
    "tax_calculation": {
        "step_1": {"name": "Xác định loại thuế", "prompt": "Bạn muốn tính loại thuế nào? (GTGT, TNDN, TNCN, Môn bài)"},
        "step_2": {"name": "Thu thập số liệu", "prompt": "Vui lòng cung cấp số liệu cần thiết (doanh thu, chi phí, v.v.)"},
        "step_3": {"name": "Tính toán & kết quả", "prompt": None},  # Auto
    },
    "tax_declaration": {
        "step_1": {"name": "Xác định tờ khai", "prompt": "Bạn cần kê khai tờ khai nào? (GTGT, TNDN, TNCN, Môn bài)"},
        "step_2": {"name": "Hướng dẫn điền", "prompt": "Tôi sẽ hướng dẫn bạn điền tờ khai. Bạn đã có tờ khai mẫu chưa?"},
        "step_3": {"name": "Review & nộp", "prompt": "Vui lòng kiểm tra lại thông tin. Bạn muốn tôi review không?"},
    },
    "tax_registration": {
        "step_1": {"name": "Chuẩn bị hồ sơ", "prompt": "Tôi sẽ liệt kê các giấy tờ cần chuẩn bị cho đăng ký MST."},
        "step_2": {"name": "Hướng dẫn nộp", "prompt": "Bạn đã chuẩn bị đầy đủ hồ sơ chưa? Tôi sẽ hướng dẫn cách nộp."},
        "step_3": {"name": "Theo dõi kết quả", "prompt": "MST thường được cấp trong 3 ngày làm việc. Bạn đã nhận chưa?"},
    },
    "tax_consultation": {
        "step_1": {"name": "Tiếp nhận câu hỏi", "prompt": "Bạn muốn tìm hiểu quy định thuế nào?"},
        "step_2": {"name": "Tra cứu & trả lời", "prompt": None},  # Auto via RAG
    },
    "invoice_check": {
        "step_1": {"name": "Upload hóa đơn", "prompt": "Vui lòng gửi ảnh hóa đơn/chứng từ cần kiểm tra."},
        "step_2": {"name": "Xác minh", "prompt": None},  # Auto via OCR
        "step_3": {"name": "Kết quả", "prompt": None},
    },
    "tax_refund": {
        "step_1": {"name": "Xác định điều kiện", "prompt": "Để kiểm tra điều kiện hoàn thuế GTGT, bạn vui lòng cho biết doanh thu và thuế GTGT đầu vào?"},
        "step_2": {"name": "Chuẩn bị hồ sơ", "prompt": "Tôi sẽ liệt kê các giấy tờ cần chuẩn bị cho hồ sơ hoàn thuế."},
        "step_3": {"name": "Hướng dẫn nộp", "prompt": "Bạn đã chuẩn bị hồ sơ xong chưa?"},
    },
    "penalty_consultation": {
        "step_1": {"name": "Mô tả tình huống", "prompt": "Bạn gặp vấn đề gì liên quan đến thuế? (chậm nộp, khai sai, v.v.)"},
        "step_2": {"name": "Tra cứu & tư vấn", "prompt": None},  # Auto via RAG
    },
    "annual_settlement": {
        "step_1": {"name": "Xác định nghĩa vụ", "prompt": "Bạn cần quyết toán thuế nào? (TNDN, TNCN, hoặc cả hai)"},
        "step_2": {"name": "Checklist chuẩn bị", "prompt": "Tôi sẽ gửi checklist các bước quyết toán thuế năm."},
        "step_3": {"name": "Hướng dẫn thực hiện", "prompt": "Bạn đã hoàn thành checklist chưa? Tôi sẽ hướng dẫn bước tiếp theo."},
    },
}


class CaseManager:
    """Manages support case lifecycle."""

    def __init__(self, case_repo: CaseRepository) -> None:
        self.repo = case_repo

    async def get_active_cases(self, customer_id: uuid.UUID) -> list[dict]:
        cases = await self.repo.get_active_cases(customer_id)
        return [self.repo.to_dict(c) for c in cases]

    async def create_case(
        self,
        customer_id: uuid.UUID,
        service_type: str,
        context: dict | None = None,
    ) -> dict:
        """Create a new support case and return the first step prompt."""
        title = SERVICE_TITLE_MAP.get(service_type, service_type)
        case = await self.repo.create(
            customer_id=customer_id,
            service_type=service_type,
            title=title,
            context=context,
        )
        return self.repo.to_dict(case)

    async def advance_step(
        self,
        case_id: uuid.UUID,
        step_data: dict | None = None,
    ) -> dict | None:
        """Advance case to the next step."""
        case = await self.repo.get_by_id(case_id)
        if not case:
            return None

        steps = SERVICE_STEPS.get(case.service_type, {})
        step_keys = list(steps.keys())
        current_idx = step_keys.index(case.current_step) if case.current_step in step_keys else -1

        if current_idx < 0 or current_idx >= len(step_keys) - 1:
            # Last step or unknown - complete the case
            updated = await self.repo.update_step(
                case.id, current_step="done", step_data=step_data, status="completed"
            )
        else:
            next_step = step_keys[current_idx + 1]
            updated = await self.repo.update_step(
                case.id, current_step=next_step, step_data=step_data, status="in_progress"
            )

        return self.repo.to_dict(updated) if updated else None

    def get_step_prompt(self, service_type: str, step: str) -> str | None:
        """Get the prompt for a given step in a service workflow."""
        steps = SERVICE_STEPS.get(service_type, {})
        step_info = steps.get(step)
        return step_info["prompt"] if step_info else None

    def get_step_name(self, service_type: str, step: str) -> str:
        """Get the human-readable name of a step."""
        steps = SERVICE_STEPS.get(service_type, {})
        step_info = steps.get(step)
        return step_info["name"] if step_info else step

    def build_case_status_message(self, case: dict) -> str:
        """Build a status message for an active case."""
        service_label = SERVICE_TITLE_MAP.get(case.get("service_type", ""), "Dịch vụ")
        step_name = self.get_step_name(case.get("service_type", ""), case.get("current_step", ""))
        return f"{service_label} - Bước hiện tại: {step_name} ({case.get('status', '')})"
