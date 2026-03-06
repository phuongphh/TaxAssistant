import os
import sys
import anthropic

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"]
)

with open("pr_diff.txt", "r") as f:
    diff = f.read()

SYSTEM_PROMPT = """
You are a strict code reviewer for a Vietnamese Tax Assistant system.

You must check:

1. Does the PR modify files outside the issue scope?
2. Does it introduce hardcoded tax rates?
3. Does it modify core/tax_rules without explicit reason?
4. Are unit tests included?
5. Does it modify unrelated modules?

If any violation is found, respond with:
FAIL: <reason>

If everything is correct, respond with:
PASS
"""

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=200,
    temperature=0,
    system=SYSTEM_PROMPT,
    messages=[
        {
            "role": "user",
            "content": diff
        }
    ]
)

result = response.content[0].text.strip()

print(result)

if result.startswith("FAIL"):
    sys.exit(1)
