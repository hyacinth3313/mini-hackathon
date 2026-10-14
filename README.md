# Code Reviewer CLI 🔍

An AI-assisted code review command-line tool built during a Python club mini-hackathon. It analyzes Python source files for code smells and antipatterns using Python's `ast` module, enriches findings with LLM explanations and suggested fixes, and presents formatted reports with quality scores and Markdown export.

---

## 🚀 Features

- **AST-Based Problem Detection**: Statically inspects code without executing it (missing docstrings, deep nesting, unused variables, etc.).
- **LLM-Powered Explanations & Fixes**: Queries an LLM (e.g., Groq / Gemini) to explain *why* an issue matters and suggest corrected code.
- **Resilient Fallback**: Gracefully operates in offline mode (`--no-llm`) or when LLM API requests fail.
- **Rich Terminal UI**: Color-coded severity levels (`high`, `medium`, `low`), formatted syntax previews, and a summary breakdown.
- **Folder & Project Scanning**: Traverses entire directories, automatically skipping virtual environments and cache directories.
- **Quality Score & Markdown Reports**: Computes a code health score (out of 100) and exports detailed reports (`--out report.md`).

---

## 📦 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hyacinth3313/mini-hackathon.git
   cd mini-hackathon
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # macOS / Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install rich groq python-dotenv streamlit
   ```

---

## 🔑 Environment Setup (`.env`)

Copy the example environment file and add your LLM API key:

```bash
cp .env.example .env
```

Edit `.env` to include your API key:
```env
GROQ_API_KEY=your_groq_api_key_here
```

> **Note:** Never commit `.env` or sensitive API keys. `.env` is ignored in `.gitignore`.

---

## 💻 Usage

Run the reviewer CLI by pointing it to any Python file or directory:

```bash
# Review a single file
python reviewer.py sample.py

# Review an entire directory and export a report
python reviewer.py . --out report.md

# Review without calling the LLM (offline / fast AST mode)
python reviewer.py sample.py --no-llm
```

### CLI Arguments

| Argument | Description |
| :--- | :--- |
| `target` | Path to a `.py` file or a directory to review. |
| `--out <path>` | *(Optional)* Save review results as a formatted Markdown report (e.g., `report.md`). |
| `--no-llm` | *(Optional)* Skip LLM explanations and show AST findings only. |

---

## 📋 Example Output

```text
+-----------------------------------------------------------------------------+
| sample.py  (2 problems)                                                     |
+-----------------------------------------------------------------------------+
Line 12 | missing docstring | calc  (medium)
  Why: Readers cannot easily understand or maintain calc due to missing docstring.
  Fix: Add a descriptive docstring to clarify the function's purpose and arguments.
                                                                               
 # Suggested improvement for calc                                              
 def calc(a: int, b: int) -> int:                                              
     """Add two numbers and return the result."""                              
     return a + b                                                              

Line 30 | deep nesting | process_data  (high)
  Why: Excessive nesting makes control flow difficult to follow and test.
  Fix: Use early returns or guard clauses to flatten the logic.
                                                                               
 # Suggested improvement for process_data                                      
 def process_data(items):                                                      
     """Process items using guard clauses."""                                  
     if not items:                                                             
         return                                                                
     ...                                                                       

      Summary       
+------------------+
| Severity | Count |
|----------+-------|
| high     |     1 |
| medium   |     1 |
| low      |     0 |
+------------------+
Quality score: 85/100
```

---

## 🗂️ Project Architecture & File Ownership

The project follows a modular structure where teammates own specific components:

- **[reviewer.py](file:///c:/Users/91854/mini-hackathon/reviewer.py)**: CLI entry point using `argparse` and `rich`. Handles file discovery, thread pooling, scoring calculations, console rendering, error handling, and Markdown report generation.
- **`detectors.py`**: AST-based detector engine. Implements `detect(path) -> list[dict]` to discover code issues.
- **`llm.py`**: LLM integration layer. Implements `explain(finding) -> dict` to retrieve explanations and suggested fixes without crashing.
- **`app.py`**: *(Optional)* Streamlit dashboard for interactive web reviews.

### Shared Finding Format
All modules exchange findings using the standardized dictionary structure:
```json
{
  "file": "path/to/file.py",
  "line": 12,
  "type": "missing docstring",
  "name": "calc",
  "snippet": "def calc(): pass",
  "severity": "medium",
  "why": "Plain-language explanation of why this issue matters.",
  "fix": "Actionable suggestion to resolve the issue.",
  "corrected_code": "def calc():\n    '''Documented.'''\n    pass"
}
```
