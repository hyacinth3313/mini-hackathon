import argparse, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from detectors import detect
from llm import explain

console = Console()
SKIP = {"venv", ".venv", "node_modules", "__pycache__", ".git"}
COLOR = {"high": "red", "medium": "yellow", "low": "cyan"}
PENALTY = {"high": 10, "medium": 5, "low": 2}


def collect_files(target):
    p = Path(target)
    if p.is_file():
        return [p] if p.suffix == ".py" else []
    return sorted(f for f in p.rglob("*.py") if not SKIP & set(f.parts))


def safe_explain(f):
    try:
        res = explain(f)
        return res if isinstance(res, dict) else f
    except Exception:
        return f  # basic finding still prints


def score(findings):
    return max(0, 100 - sum(PENALTY.get(str(f.get("severity", "low")).lower(), 2) for f in findings))


def print_file(file, findings):
    console.print(Panel(f"[bold]{escape(str(file))}[/]  ({len(findings)} problems)", style="blue"))
    if not findings:
        console.print("  [green]No problems found[/]\n")
        return
    for f in sorted(findings, key=lambda x: x.get("line") or 0):
        sev = str(f.get("severity", "low")).lower()
        c = COLOR.get(sev, "white")
        line = f.get("line", "?")
        ftype = f.get("type", "issue")
        name = f.get("name", "unknown")
        console.print(f"[bold]Line {line}[/] | [{c}]{escape(str(ftype))}[/] | "
                      f"{escape(str(name))}  [{c}]({sev})[/]")
        if f.get("snippet"):
            snip_lines = str(f.get("snippet")).splitlines()[:8]
            console.print(Syntax("\n".join(snip_lines), "python", theme="monokai", padding=1), style="dim")
        console.print(f"  [bold]Why:[/] {escape(str(f.get('why') or '(no explanation available)'))}")
        console.print(f"  [bold]Fix:[/] {escape(str(f.get('fix') or '(no suggestion available)'))}")
        if f.get("corrected_code"):
            console.print(Syntax(str(f["corrected_code"]), "python", theme="monokai", padding=1))
        console.print()


def print_summary(results):
    if isinstance(results, dict):
        all_findings = [f for fs in results.values() for f in fs]
        overall_score = round(sum(score(fs) for fs in results.values()) / len(results)) if results else 100
    else:
        all_findings = results
        overall_score = score(all_findings)

    t = Table(title="Summary")
    t.add_column("Severity"); t.add_column("Count", justify="right")
    for sev in ("high", "medium", "low"):
        n = sum(1 for f in all_findings if str(f.get("severity", "low")).lower() == sev)
        t.add_row(f"[{COLOR[sev]}]{sev}[/]", str(n))
    console.print(t)
    console.print(f"[bold]Quality score: {overall_score}/100[/]")


def write_report(path, results):
    allf = [f for fs in results.values() for f in fs]
    overall_score = round(sum(score(fs) for fs in results.values()) / len(results)) if results else 100
    out = ["# Code Review Report", f"**Score: {overall_score}/100**  |  Problems: {len(allf)}", ""]
    for file, fs in results.items():
        out.append(f"## {file}")
        if not fs:
            out += ["No problems found.", ""]
        for f in sorted(fs, key=lambda x: x.get("line") or 0):
            line = f.get("line", "?")
            ftype = f.get("type", "issue")
            name = f.get("name", "unknown")
            sev = str(f.get("severity", "low")).lower()
            out.append(f"### Line {line} | {ftype} | {name} ({sev})")
            if f.get("snippet"):
                out += ["```python", str(f.get("snippet")), "```"]
            out += [f"- **Why:** {f.get('why') or '-'}", f"- **Fix:** {f.get('fix') or '-'}"]
            if f.get("corrected_code"):
                out += ["```python", str(f["corrected_code"]), "```"]
            out.append("")
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="AI-assisted Python code reviewer")
    ap.add_argument("target", help="a .py file or a folder")
    ap.add_argument("--out", help="save a markdown report, e.g. report.md")
    ap.add_argument("--no-llm", action="store_true", help="skip LLM, basic findings only")
    args = ap.parse_args()

    target_path = Path(args.target)
    if not target_path.exists():
        console.print(f"[red]Path not found: {escape(args.target)}[/]")
        sys.exit(1)

    if target_path.is_file() and target_path.suffix != ".py":
        console.print(f"[red]Target must be a Python (.py) file or folder: {escape(args.target)}[/]")
        sys.exit(1)

    files = collect_files(args.target)
    if not files:
        console.print(f"[yellow]No Python files found in {escape(args.target)}[/]")
        sys.exit(0)

    results = {}
    for file in files:
        try:
            findings = detect(str(file))
        except SyntaxError as e:
            line_str = f"line {e.lineno}" if e.lineno is not None else "unknown line"
            console.print(f"[red]Skipping {escape(str(file))}: syntax error at {line_str}[/]")
            continue
        except (OSError, UnicodeDecodeError) as e:
            console.print(f"[red]Skipping {escape(str(file))}: {escape(str(e))}[/]")
            continue

        if findings and not args.no_llm:
            with ThreadPoolExecutor(max_workers=4) as ex:
                findings = list(ex.map(safe_explain, findings))
        results[str(file)] = findings
        print_file(str(file), findings)

    if not results:
        console.print("[yellow]No files could be analyzed[/]")
        sys.exit(1)

    print_summary(results)
    if args.out:
        write_report(args.out, results)
        console.print(f"[green]Report saved to {escape(args.out)}[/]")


if __name__ == "__main__":
    main()