# CLAUDE BUILD RULES FOR TAX ASSISTANT

When implementing a GitHub Issue:

1. Strictly follow the Functional Requirements and Acceptance Criteria.
2. Do NOT add extra features.
3. Do NOT refactor unrelated modules.
4. Do NOT modify tax_rules unless explicitly required.
5. All tax calculations must live in /core/tax_rules.
6. Telegram logic must live in /services/telegram.
7. AI prompt logic must live in /services/ai.
8. No hardcoded tax rates.
9. Must include unit tests.
10. Must create feature branch: feature/issue-<ID>-<short-name>.
11. PR must include: "Closes #<ID>".

If Acceptance Criteria is unclear, STOP and ask.
