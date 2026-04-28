# Legal Changelog — TaxAssistant

> Lịch sử cập nhật văn bản pháp luật vào hệ thống TaxAssistant.
> Mỗi entry cần ghi rõ: ngày cập nhật, văn bản, hiệu lực, thay đổi
> code/knowledge base, người review.

Tài liệu này phục vụ yêu cầu Issue #71: thiết lập traceability cho mọi
quy tắc thuế trong system prompt và knowledge base.

---

## Quy trình review pháp luật định kỳ

**Tần suất:** Mỗi quý — tháng 1, 4, 7, 10 (review trước ngày 15).

**Checklist nguồn cần kiểm tra mỗi lần review:**
- Cổng thông tin pháp luật: https://vbpl.vn
- Thư viện pháp luật: https://thuvienphapluat.vn
- Cổng Tổng cục Thuế: https://gdt.gov.vn
- Công báo Chính phủ: https://congbao.chinhphu.vn

**Khi phát hiện văn bản mới:**
1. Mở issue trên GitHub gắn label `legal-update`.
2. Verify tác động (sắc thuế nào? mức thay đổi? hiệu lực ngày nào?).
3. Cập nhật:
   - `python-engine/app/ai/prompts.py` (block "QUY ĐỊNH THUẾ HIỆN HÀNH").
   - `python-engine/app/core/tax_rules/<sắc thuế>.py` (logic tính + legal_basis).
   - `python-engine/data/seed/<sắc thuế>_regulations.json` (RAG knowledge base).
   - `python-engine/data/tax_config.json` (nếu thay đổi tỷ lệ/mức).
4. Viết test case cho năm cũ + năm mới (đảm bảo backward-compat cho user
   hỏi nghĩa vụ kỳ ≤ năm hiện tại).
5. Thêm entry vào file này.
6. Sau khi merge, đẩy seed data mới vào ChromaDB.

**Ghi chú với người dùng:** Mọi câu trả lời về thuế nên kết bằng:
> *"Thông tin này dựa trên [Văn bản X] hiệu lực [ngày]. Vui lòng xác nhận
> với cơ quan thuế nếu có thay đổi pháp luật gần đây."*

---

## 2026-04-27 — Bãi bỏ Lệ phí môn bài & Thuế khoán từ 01/01/2026

**Lý do:** Issue #71 — bot đang nhắc về Lệ phí môn bài và Thuế khoán theo
văn bản cũ, trong khi cả hai đã chính thức bị bãi bỏ từ 01/01/2026.

**Văn bản pháp luật mới (hiện hành):**
- **Nghị quyết 198/2025/QH15** ngày 17/05/2025 (Quốc hội), Điều 10:
  - Bãi bỏ lệ phí môn bài từ 01/01/2026.
  - Bãi bỏ phương pháp khoán đối với hộ kinh doanh, cá nhân kinh doanh
    từ 01/01/2026 → chuyển sang phương pháp kê khai.
  - Hộ KD chỉ còn nộp 02 sắc thuế: GTGT + TNCN.
  - Nâng ngưỡng doanh thu không phải nộp thuế từ 100 triệu → 200 triệu/năm
    (cần theo dõi Luật Quản lý thuế sửa đổi để xác nhận mức cuối).
- **Nghị định 362/2025/NĐ-CP** ngày 31/12/2025 (Chính phủ): Quy định chi
  tiết Luật Phí và lệ phí, hiệu lực 01/01/2026 — bãi bỏ Nghị định
  139/2016/NĐ-CP và Nghị định 22/2020/NĐ-CP.
- **Công văn 645/CT-CS** (Tổng cục Thuế): Hướng dẫn không thu lệ phí môn
  bài và không nộp tờ khai từ 01/01/2026.
- **Quyết định 3389/QĐ-TCT** (Tổng cục Thuế): Quy trình chuyển hộ khoán
  sang kê khai.

**Văn bản hết hiệu lực (chỉ áp dụng kỳ ≤ 2025):**
- Nghị định 139/2016/NĐ-CP (lệ phí môn bài).
- Nghị định 22/2020/NĐ-CP (sửa đổi NĐ 139/2016).
- Thông tư 302/2016/TT-BTC (hướng dẫn thi hành NĐ 139/2016).
- Phương pháp khoán theo Thông tư 40/2021/TT-BTC (vẫn còn hiệu lực phần
  tỷ lệ % GTGT/TNCN trên doanh thu cho hộ kê khai, chỉ phương pháp khoán
  bị bỏ).

**Thay đổi trong code:**
- `python-engine/app/core/tax_rules/license_tax.py`:
  - Thêm `LICENSE_TAX_ABOLISHED_FROM_YEAR = 2026`.
  - `calculate()` nhận tax_year từ context → return TaxResult với
    amount=0 và explanation rõ ràng nếu year ≥ 2026.
  - Cho phép tính lại theo mức cũ (NĐ 139/2016) khi user query năm ≤ 2025
    để hoàn tất nghĩa vụ kỳ cũ.
  - Cập nhật `get_info()` và `get_consultation()` luôn nêu rõ tình trạng
    bãi bỏ.
- `python-engine/app/ai/prompts.py`:
  - SYSTEM_PROMPT bổ sung block "THAY ĐỔI PHÁP LUẬT QUAN TRỌNG TỪ
    01/01/2026" để LLM trả lời đúng theo Nghị quyết 198/2025.
- `python-engine/app/core/tax_engine.py`:
  - `_handle_procedure`, `_handle_declaration` cho hộ KD: thay nội dung
    "Khoán: ..." bằng "Phương pháp KÊ KHAI" + cảnh báo về bãi bỏ.
  - `_get_tax_overview`: bỏ mức môn bài, thêm cảnh báo bãi bỏ.
  - `_get_deadline_info`: bỏ hạn nộp môn bài, thêm ghi chú bãi bỏ.
- `python-engine/app/core/onboarding.py`:
  - Câu hỏi tax period: option "Thuế khoán" được đổi thành "Trước đây
    dùng thuế khoán" + cảnh báo phải chuyển sang kê khai.
- `python-engine/data/seed/license_tax_regulations.json`:
  - Thêm Nghị quyết 198/2025/QH15 và Nghị định 362/2025/NĐ-CP.
  - Đánh dấu Nghị định 139/2016 + 22/2020 với `expired_date: 2026-01-01`
    và `superseded_by: 362/2025/NĐ-CP`, prefix nội dung bằng cảnh báo
    "VĂN BẢN ĐÃ HẾT HIỆU LỰC".

**Test coverage:**
- `tests/unit/core/tax_rules/test_license_tax_rule.py`: thêm test
  `test_abolished_from_2026` và `test_historical_year_2025_still_works`.

**Người review:** Claude (automated, Issue #71 — 2026-04-27).
**Cần human review trước khi deploy production:** Có — đặc biệt mức ngưỡng
doanh thu mới (200tr vs 500tr) còn phụ thuộc văn bản hướng dẫn cuối cùng.
