# Issue #52

[Backend] Deadline Calculator Engine

## Context

Tạo module Python mới trong `python-engine` để tính toán deadline thuế cho từng user dựa trên profile của họ. Đây là business logic thuần — không có side effects, dễ test.

**Depends on:** #51

---

## File Location

```
python-engine/
  app/
    services/
      deadline_calculator.py   ← file mới
  tests/
    test_deadline_calculator.py ← bắt buộc
```

---

## Requirements

### Class `DeadlineCalculator`

#### Method: `get_deadlines_for_user(profile, reference_date)`

- **Input:** `dict` profile từ DB, `date` hôm nay
- **Output:** `list` các deadline dict trong 60 ngày tới, sort theo `due_date` tăng dần

#### Shape của mỗi deadline dict:

```python
{
  'due_date':          date,
  'type':              str,       # 'flat_tax' | 'vat' | 'cit' | 'pit' | 'pit_annual'
  'label':             str,       # vd: "Thuế khoán Q3/2025"
  'urgency':           str,       # 'critical' | 'urgent' | 'warning' | 'info'
  'estimated_amount':  int | None, # VND, None nếu không tính được
  'penalty_per_day':   int | None  # VND phạt/ngày nếu trễ
}
```

---

## Business Logic

### Deadline rules theo loại hình:

| business_type | tax_period  | Deadline rule |
|---------------|-------------|---------------|
| household     | quarterly   | Thuế khoán: ngày 30 tháng đầu quý sau |
| household     | monthly     | Kê khai: ngày 20 tháng sau |
| company       | monthly     | VAT: ngày 20 tháng sau; CIT tạm tính: ngày 30 tháng đầu quý sau |
| company       | quarterly   | VAT: ngày 30 tháng đầu quý sau; CIT: như trên |
| individual    | —           | PIT quý: ngày 30 tháng đầu quý sau; PIT annual: 31/3 năm sau |

### Urgency rules:

| Urgency    | Điều kiện        |
|------------|------------------|
| critical   | ≤ 3 ngày         |
| urgent     | 4–7 ngày         |
| warning    | 8–14 ngày        |
| info       | 15–60 ngày       |

### Ước tính thuế:
- Dùng tỷ lệ theo **Thông tư 40/2021/TT-BTC**
- Chỉ tính được khi có `revenue_snapshots` gần nhất
- Return `None` nếu không đủ dữ liệu — **không được guess**

---

## Test Cases Bắt Buộc

```python
# Ít nhất phải cover:
- Hộ KD ngành dịch vụ, quarterly → đúng 4 deadline/năm
- Công ty kê khai tháng → VAT ngày 20, CIT ngày 30
- Deadline rơi vào cuối tháng 2 (ngày 28/29) → không crash
- Ngày reference là ngày 31 tháng 12 → năm sau handle đúng
- Profile thiếu tax_period → return list rỗng, không raise exception
```

---

## Acceptance Criteria

- [ ] 100% test cases pass
- [ ] Không import từ Telegram/Node layer (pure business logic)
- [ ] Xử lý được edge case tháng có 28/29/30/31 ngày
