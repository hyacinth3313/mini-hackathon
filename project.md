PROJECT CONTEXT (remember this for all later prompts)

We are in a 60-90 minute Python club mini hackathon. Team of 3. We're building a
"Code Reviewer CLI": a command-line tool that reads a Python file, finds code
problems and explains them in plain language.

Usage: python reviewer.py sample.py

MUST HAVE
- Parse the file with Python's ast module
- Detect at least 3 kinds of problems (missing docstring, deep nesting, unused variable)
- Report the line number of each problem
- Send each problem to an LLM (Groq or Gemini) for a plain explanation and suggested fix, returned as JSON
- Print a clean, readable report
- If the LLM fails, still print the basic finding

EXAMPLE OUTPUT
Line 12 | missing docstring | calc()
  Why: readers cannot tell what calc() does.
  Fix: add a one-line docstring.

BONUS (we want all of these)
- Severity levels (high / medium / low)
- Show corrected code
- Review a whole folder
- Summary score and a report file (--out report.md)

FILE OWNERSHIP
- detectors.py: teammate A. detect(path) -> list of finding dicts
- llm.py: teammate B. explain(finding) -> finding dict, never raises
- reviewer.py: mine (CLI with argparse and rich, report, folder scan, score, report file)
- app.py: optional Streamlit page, mine, only if time is left

FINDING FORMAT (shared by all files)
{"file","line","type","name","snippet","severity","why","fix","corrected_code"}

RULES
- Don't edit detectors.py or llm.py unless I say so (they belong to teammates)
- Never commit API keys; keep them in .env
- Don't commit or push unless I ask
- Ask before big changes

Reply with a short summary of what we're building and which files you'll touch.