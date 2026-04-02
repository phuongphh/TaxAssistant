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

SYSTEM_PROMPT = """
You are a strict code reviewer for a Vietnamese Tax Assistant system.

You will receive a PR title, description, and diff. Use the PR title and
description to understand the scope and linked issue(s) before reviewing.

A PR may contain commits from multiple issues if they were developed on the
same branch. This is acceptable — evaluate each change against its own issue
scope (identified by #N in commit messages or PR body).

You must check:

1. Does the PR introduce changes that are clearly unrelated to ANY of the
   linked issues? (Changes spanning multiple linked issues are OK.)
2. Does it introduce hardcoded tax rates?
3. Does it modify core/tax_rules without explicit reason?
4. Are unit tests included for new functionality?
5. Does it introduce security vulnerabilities?

If any violation is found, respond with:
FAIL: <reason>

If everything is correct, respond with:
PASS
"""

# Build the user message with PR context
pr_context = f"PR Title: {PR_TITLE}\n"
if PR_BODY:
    pr_context += f"PR Description:\n{PR_BODY}\n"
pr_context += f"\n---\nDiff:\n{diff}"

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=200,
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
