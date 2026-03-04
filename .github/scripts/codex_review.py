import os
import sys
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

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

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": diff}
    ],
    temperature=0
)

result = response.choices[0].message.content.strip()

print(result)

if result.startswith("FAIL"):
    sys.exit(1)
