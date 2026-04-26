# TaxAssistant — Documentation

> **Vision:** Telegram bot trợ lý thuế tự động (proactive, personalized) cho SME, hộ kinh doanh và freelancer Việt Nam.

---

## 🎯 Current Focus

**🚀 Phase 1 — Notification System (Retention Foundation)**

Biến thuế từ "reactive" (chỉ nhớ khi sắp bị phạt) thành "proactive" — hệ thống nhắc deadline cá nhân hóa theo từng loại hình kinh doanh.

- 📖 Strategy: [`strategy/retention-strategy.md`](strategy/retention-strategy.md)
- 📋 Active issues: [`issues/active/INDEX.md`](issues/active/INDEX.md)
- ✅ Completed: [`issues/closed/INDEX.md`](issues/closed/INDEX.md)

---

## 📚 Navigation

### Strategy
- 📜 [Retention Strategy](strategy/retention-strategy.md) — chiến lược retention đầy đủ + spec 6 issues của notification system
- 📐 [Build Rules](CLAUDE_BUILD_RULES.md) — quy ước build tổng quát
- 🤖 [CLAUDE.md](../CLAUDE.md) — technical spec cho AI agents

### Implementation Guides

| Phase | Status | Detailed Doc | Issues |
|-------|--------|--------------|--------|
| Phase 1 — Notification System | ✅ Completed | [strategy/retention-strategy.md](strategy/retention-strategy.md) | [closed/by-phase/phase-1/](issues/closed/by-phase/phase-1/) |
| (Legacy / pre-phase work) | ✅ Completed | — | [closed/by-phase/unknown/](issues/closed/by-phase/unknown/) |

### Issues
- 🟢 [Active Issues](issues/active/INDEX.md)
- 🗄️ [Closed Issues](issues/closed/INDEX.md)
- 📘 [Issues README](issues/README.md) — workflow và conventions

### Archive
- _Trống — chưa có pivot lớn._ Khi project pivot, tạo `archive/MIGRATION_NOTES_VX_VY.md` và move legacy docs vào `archive/vX-name/`.

---

## 🗂️ Folder Structure

```
docs/
├── README.md                        ← navigation hub (file này)
├── CLAUDE_BUILD_RULES.md            ← build conventions
├── workflow-template.md             ← spec cho docs+issue workflow này
│
├── current/                         ← phase-specific docs (in progress)
│   └── (phase-X-detailed.md, phase-X-issues.md khi cần)
│
├── strategy/
│   └── retention-strategy.md        ← chiến lược + spec issues phase 1
│
├── archive/                         ← legacy docs từ pivot trước
│
└── issues/
    ├── README.md                    ← issue workflow guide
    ├── active/
    │   ├── INDEX.md                 ← auto-generated
    │   └── issue-N.md               ← một file / open issue
    └── closed/
        ├── INDEX.md                 ← auto-generated
        └── by-phase/
            ├── phase-1/             ← notification system (#51-60)
            └── unknown/             ← legacy, no phase label
```

---

## 🛠️ How to Use

### Khi bắt đầu development trên một phase mới
1. Đọc [`strategy/retention-strategy.md`](strategy/retention-strategy.md) — vision + retention positioning
2. Đọc [`../CLAUDE.md`](../CLAUDE.md) — technical conventions, architecture
3. Mở `current/phase-X-detailed.md` (nếu có) — hướng dẫn implementation chi tiết
4. Pick issue trong `issues/active/` → trigger AI implementation

### Khi trigger AI implement một issue
```
"Implement issue #N theo spec trong docs/issues/active/issue-N.md"
```
AI sẽ đọc:
1. `docs/issues/active/issue-N.md` (primary context)
2. `docs/current/phase-Y-detailed.md` (architecture, nếu có)
3. `CLAUDE.md` (technical spec)

### Khi project pivot
1. Tạo `archive/MIGRATION_NOTES_VX_VY.md` mô tả lý do pivot và mapping
2. Move outdated docs vào `archive/vX-name/`
3. Update file này (Current Focus, table phase)
4. **Không xóa file** — preserve history qua git và folder archive

---

## 🔄 Issue Lifecycle (tự động hóa)

```
GitHub issue created/edited
       │
       ▼
Action `issue-lifecycle.yml` chạy
       │
       ▼
Tạo/update `docs/issues/active/issue-N.md`
       │
       ▼
PR đóng issue (closes #N)
       │
       ▼
Action move file → `docs/issues/closed/by-phase/phase-X/`
       │
       ▼
Regenerate `INDEX.md` (qua `scripts/generate-issues-index.py`)
```

Phase được detect từ label `phase-X` trên GitHub issue. Nếu không có label → `unknown`.

---

*Cập nhật mỗi khi thêm phase mới hoặc thay đổi cấu trúc.*
