# CLAUDE BUILD RULES FOR TAX ASSISTANT
This document is the authoritative source of development rules for this repository.
All implementation must follow these rules.
If any instruction conflicts with this document, this document takes precedence.

When implementing a GitHub Issue:

1. Strictly follow the Functional Requirements and Acceptance Criteria. If Acceptance Criteria is unclear, STOP and ask.
2. Do NOT add extra features.
3. Do NOT refactor unrelated modules.
4. Do NOT modify tax_rules unless explicitly required.
5. All tax calculations must live in /core/tax_rules.
6. Telegram logic must live in /services/telegram.
7. AI prompt logic must live in /services/ai.
8. No hardcoded tax rates.
9. Must include unit tests.
10. Must create feature branch: feature/issue-<ID>-<short-name>.
11. Generate implementation plan in bullet points.
12. Wait for approval before writing code.
13. PR must include: "Closes #<ID>".




