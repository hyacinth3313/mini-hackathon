import json
from llm import explain

def test_both_key_formats():
    print("--- Testing Case 1: Using 'code_snippet' ---")
    finding_1 = {
        "line": 10,
        "type": "missing docstring",
        "name": "foo",
        "code_snippet": "def foo():\n    pass"
    }
    result_1 = explain(finding_1)
    print(json.dumps(result_1, indent=2))

    print("\n--- Testing Case 2: Using 'snippet' (Teammate's format) ---")
    finding_2 = {
        "line": 20,
        "type": "unused variable",
        "name": "bar",
        "snippet": "x = 10"
    }
    result_2 = explain(finding_2)
    print(json.dumps(result_2, indent=2))

if __name__ == "__main__":
    test_both_key_formats()