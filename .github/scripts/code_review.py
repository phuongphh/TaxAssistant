import os
import sys
import anthropic
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
PR_NUMBER = os.environ.get("PR_NUMBER")
PR_TITLE = os.environ.get("PR_TITLE", "")
PR_BODY = os.environ.get("PR_BODY", "")
REPO = os.environ.get("REPO")

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY secret is not set.")
    sys.exit(1)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

try:
    with open("pr_diff.txt", "r") as f:
        diff = f.read().strip()
except FileNotFoundError:
    print("ERROR: pr_diff.txt not found. Diff step may have failed.")
    sys.exit(1)

if not diff:
    print("No diff found. Skipping review.")
    sys.exit(0)

# ---------------------------------------------------------------
# Filter out files that should not be code-reviewed:
#   - .github/ (CI/CD config, workflows, scripts, templates)
#   - docs/    (documentation, issue exports)
# ---------------------------------------------------------------
def filter_diff(raw_diff: str) -> str:
    """Remove diff hunks for files under .github/ and docs/."""
    filtered_lines: list[str] = []
    skip = False
    for line in raw_diff.split("\n"):
        if line.startswith("diff --git"):
            # e.g. "diff --git a/.github/scripts/code_review.py b/..."
            path = line.split(" b/")[-1] if " b/" in line else ""
            skip = path.startswith(".github/") or path.startswith("docs/")
        if not skip:
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


filtered_diff = filter_diff(diff)

if not filtered_diff.strip():
    print("PASS (only CI/docs changes, no application code to review)")
    sys.exit(0)

SYSTEM_PROMPT = """
You are a pragmatic code reviewer for a Vietnamese Tax Assistant system.

You will receive a PR title, description, and the diff of application code
changes. CI/CD and documentation files are already excluded from the diff.

A PR may address multiple issues (identified by #N in commit messages).
This is normal for branches that accumulate work — do NOT flag this as a
scope violation.

Review the code changes for these specific problems ONLY:

1. HARDCODED TAX RATES — Tax rates, thresholds, or legal values embedded
   directly in application code (outside of configuration or tax_rules).
2. MISSING TESTS — New features or bug fixes without any corresponding
   unit tests in the PR.
3. SECURITY — Obvious vulnerabilities: SQL injection, XSS, command
   injection, leaked secrets, etc.
4. CORE TAX RULES — Modifications to files under core/tax_rules/ that
   are not justified by the PR description or commit messages.

Do NOT flag:
- Refactoring or cleanup in files touched by the PR
- Changes to multiple modules when they serve the same feature
- Formatting, style, or naming preferences
- Adding or removing utility functions

Respond with EXACTLY one of:
- PASS — if no problems found
- FAIL: <one-line reason> — only if a clear violation of rules 1-4 exists
"""

# Build the user message with PR context
pr_context = f"PR: {PR_TITLE}\n"
if PR_BODY:
    pr_context += f"Description: {PR_BODY}\n"
pr_context += f"\n---\n{filtered_diff}"

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=300,
    temperature=0,
    system=SYSTEM_PROMPT,
    messages=[
        {
            "role": "user",
            "content": pr_context
        }
    ]
)

result = response.content[0].text.strip()

print(result)

# Post comment to PR if GitHub token and PR number are available
if GITHUB_TOKEN and PR_NUMBER and REPO:
    comment_body = f"## Code Review Result\n\n```\n{result}\n```"
    try:
        requests.post(
            f"https://api.github.com/repos/{REPO}/issues/{PR_NUMBER}/comments",
            json={"body": comment_body},
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
            },
        )
    except Exception as e:
        print(f"Warning: Could not post PR comment: {e}")

if result.startswith("FAIL"):
    sys.exit(1)
