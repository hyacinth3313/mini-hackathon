import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def explain(finding: dict) -> dict:
    """
    Takes a finding dictionary, queries Groq, and enriches it with 
    plain-language explanations, fixes, severity, and corrected code.
    Never raises an exception; returns the original finding unchanged on failure.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return finding

    client = Groq(api_key=api_key)
    code_snippet = finding.get('code_snippet') or finding.get('snippet', '')

    prompt = f"""
    Analyze the following code issue found by static analysis:
    - Type: {finding.get('type')}
    - Name: {finding.get('name')}
    - Line: {finding.get('line')}
    - Snippet:
    {finding.get('code_snippet')}

    Provide your response in strict JSON format with exactly these four keys:
    - "why": Exactly one plain-language sentence explaining the problem.
    - "fix": Exactly one plain-language sentence suggesting a fix.
    - "severity": Must be strictly one of "high", "medium", or "low".
    - "corrected_code": The refactored code snippet resolving the issue.
    """

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are a precise code-review assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"},
                timeout=15
            )

            raw_text = response.choices[0].message.content.strip()

            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            parsed = json.loads(raw_text)

            severity = parsed.get("severity")
            if severity not in ["high", "medium", "low"]:
                severity = "medium"

            return {
                **finding,
                "why": parsed.get("why", "No explanation provided."),
                "fix": parsed.get("fix", "No fix provided."),
                "severity": severity,
                "corrected_code": parsed.get("corrected_code", finding.get('code_snippet'))
            }

        except Exception:
            if attempt == 1:
                return finding

    return finding

if __name__ == "__main__":
    test_finding = {
        "line": 12,
        "type": "missing docstring",
        "name": "calc",
        "code_snippet": "def calc(x, y):\n    return x + y"
    }
    print("Testing llm.py...")
    result = explain(test_finding)
    print(json.dumps(result, indent=2))