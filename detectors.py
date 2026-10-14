"""AST-based code problem detector engine for Python source code.

This module inspects Python code using the standard library `ast` module to
identify quality, style, and bug risks without executing the analyzed code.
"""

import ast
import json
import os
import sys

DEFAULTS = {
    "missing module docstring": {
        "severity": "low",
        "why": "Readers cannot tell what this file is for.",
        "fix": "Add a short docstring at the top of the file.",
    },
    "missing docstring": {
        "severity": "low",
        "why": "Readers cannot tell what this does without reading the whole body.",
        "fix": "Add a one-line docstring.",
    },
    "too many parameters": {
        "severity": "medium",
        "why": "Functions with many parameters are hard to call and test.",
        "fix": "Group related parameters into an object or dict, or split the function.",
    },
    "function too long": {
        "severity": "medium",
        "why": "Long functions are hard to read, test and debug.",
        "fix": "Split it into smaller helper functions.",
    },
    "deep nesting": {
        "severity": "high",
        "why": "Deeply nested code is hard to follow and error-prone.",
        "fix": "Use early returns or extract inner blocks into helper functions.",
    },
    "unused variable": {
        "severity": "low",
        "why": "The value is assigned but never used, which is clutter or a bug.",
        "fix": "Remove the variable or use it.",
    },
    "bare except": {
        "severity": "medium",
        "why": "A bare except hides real errors, even KeyboardInterrupt.",
        "fix": "Catch specific exceptions, e.g. `except ValueError:`.",
    },
    "mutable default argument": {
        "severity": "high",
        "why": "The default object is shared between calls and can cause surprising bugs.",
        "fix": "Use None as the default and create the object inside the function.",
    },
    "unused import": {
        "severity": "low",
        "why": "Unused imports add clutter and slow startup.",
        "fix": "Remove the import.",
    },
    "syntax error": {
        "severity": "high",
        "why": "The file cannot be parsed, so no further analysis is possible.",
        "fix": "Fix the syntax error at the reported line.",
    },
}


def make_issue(file: str, line: int, issue_type: str, name: str, snippet: str) -> dict:
    """Builds a standardized issue dictionary matching the team schema."""
    default_info = DEFAULTS.get(issue_type, {})
    severity = default_info.get("severity", "low")
    why = default_info.get("why", "")
    fix = default_info.get("fix", "")
    return {
        "file": file,
        "line": line,
        "type": issue_type,
        "name": name,
        "snippet": snippet,
        "code_snippet": snippet,
        "severity": severity,
        "why": why,
        "fix": fix,
        "corrected_code": "",
    }


def get_snippet(source: str, node: ast.AST) -> str:
    """Extracts source segment capped at 30 lines with truncation notice."""
    seg = ast.get_source_segment(source, node)
    if not seg:
        return ""
    lines = seg.splitlines()
    if len(lines) > 30:
        return "\n".join(lines[:30]) + "\n... (truncated)"
    return seg


def _scan_nesting(node: ast.AST, depth: int, compound_types: tuple) -> int:
    """Traverses AST child nodes to evaluate statement nesting depth."""
    best = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(child, compound_types):
            is_elif = (
                isinstance(node, ast.If)
                and isinstance(child, ast.If)
                and node.orelse == [child]
            )
            d = depth if is_elif else depth + 1
            best = max(best, d, _scan_nesting(child, d, compound_types))
        else:
            best = max(best, _scan_nesting(child, depth, compound_types))
    return best


def max_nesting(func: ast.AST) -> int:
    """Calculates maximum statement nesting depth in a function."""
    compound_types = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
    )
    if hasattr(ast, "TryStar"):
        compound_types = compound_types + (ast.TryStar,)
    return _scan_nesting(func, 0, compound_types)


def _is_mutable_default(def_node: ast.AST) -> bool:
    """Returns True if default argument is a mutable collection or call."""
    if isinstance(def_node, (ast.List, ast.Dict, ast.Set)):
        return True
    if isinstance(def_node, ast.Call) and isinstance(def_node.func, ast.Name):
        return def_node.func.id in ("list", "dict", "set")
    return False


def _extract_assigned_names(target_node: ast.AST) -> list[tuple[str, int]]:
    """Recursively collects variable names and lines from assignment targets."""
    names = []
    if isinstance(target_node, ast.Name):
        names.append((target_node.id, target_node.lineno))
    elif isinstance(target_node, (ast.Tuple, ast.List)):
        for elt in target_node.elts:
            names.extend(_extract_assigned_names(elt))
    elif isinstance(target_node, ast.Starred):
        names.extend(_extract_assigned_names(target_node.value))
    return names


def _collect_targets_from_assign(stmt: ast.Assign) -> list[tuple[str, int]]:
    """Extracts assigned target names from an ast.Assign statement."""
    names = []
    for t in stmt.targets:
        names.extend(_extract_assigned_names(t))
    return names


def _iter_own_scope(node: ast.AST):
    """Yields statement nodes in node's own scope without descending into defs."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield child
        yield from _iter_own_scope(child)


def _collect_assigned_in_scope(func_node: ast.AST) -> tuple[list[tuple[str, int, ast.AST]], set[str]]:
    """Gathers assigned variables and ignored declarations in the local scope."""
    assigned: list[tuple[str, int, ast.AST]] = []
    ignored: set[str] = set()
    for child in _iter_own_scope(func_node):
        if isinstance(child, (ast.Global, ast.Nonlocal)):
            ignored.update(child.names)
        elif isinstance(child, ast.Assign):
            for name, line in _collect_targets_from_assign(child):
                assigned.append((name, line, child))
        elif isinstance(child, ast.AnnAssign) and child.value is not None:
            for name, line in _extract_assigned_names(child.target):
                assigned.append((name, line, child))
    return assigned, ignored


def _find_unused_variables(func_node: ast.AST, source: str) -> list[tuple[str, int, str]]:
    """Detects assigned local variables in func_node that are never loaded."""
    assigned, ignored = _collect_assigned_in_scope(func_node)
    loaded = {
        n.id
        for n in ast.walk(func_node)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }

    results: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int]] = set()
    source_lines = source.splitlines()

    for var_name, line, stmt in assigned:
        if var_name.startswith("_") or var_name in ignored or var_name in loaded:
            continue
        if (var_name, line) in seen:
            continue
        seen.add((var_name, line))
        snippet = get_snippet(source, stmt)
        if not snippet and 0 <= line - 1 < len(source_lines):
            snippet = source_lines[line - 1].strip()
        results.append((var_name, line, snippet))
    return results


def _has_all_defined(tree: ast.Module) -> bool:
    """Checks whether the module defines an __all__ variable."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                return True
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                return True
    return False


def _collect_used_names(tree: ast.Module) -> set[str]:
    """Collects loaded names and base attribute identifiers across the AST."""
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used.add(base.id)
    return used


def _handle_import_stmt(stmt: ast.Import, used_names: set[str], source: str, filename: str) -> list[dict]:
    """Checks an ast.Import statement for unused imported names."""
    issues = []
    for alias in stmt.names:
        bound = alias.asname or alias.name.split(".")[0]
        if bound not in used_names:
            line = getattr(alias, "lineno", stmt.lineno)
            issues.append(
                make_issue(filename, line, "unused import", bound, get_snippet(source, stmt))
            )
    return issues


def _handle_import_from_stmt(stmt: ast.ImportFrom, used_names: set[str], source: str, filename: str) -> list[dict]:
    """Checks an ast.ImportFrom statement for unused imported names."""
    if stmt.module == "__future__":
        return []
    issues = []
    for alias in stmt.names:
        if alias.name == "*":
            continue
        bound = alias.asname or alias.name
        if bound not in used_names:
            line = getattr(alias, "lineno", stmt.lineno)
            issues.append(
                make_issue(filename, line, "unused import", bound, get_snippet(source, stmt))
            )
    return issues


def _check_unused_imports(tree: ast.Module, source: str, filename: str) -> list[dict]:
    """Detects unused module-level imports when __all__ is not defined."""
    if _has_all_defined(tree):
        return []

    used_names = _collect_used_names(tree)
    issues = []

    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            issues.extend(_handle_import_stmt(stmt, used_names, source, filename))
        elif isinstance(stmt, ast.ImportFrom):
            issues.extend(_handle_import_from_stmt(stmt, used_names, source, filename))
    return issues


def _check_mutable_defaults(node: ast.AST, source: str, filename: str, qualname: str) -> list[dict]:
    """Checks for mutable default arguments in positional and keyword arguments."""
    issues = []
    args_obj = getattr(node, "args", None)
    if not args_obj:
        return issues

    pos_args = args_obj.posonlyargs + args_obj.args
    offset = len(pos_args) - len(args_obj.defaults)
    for idx, def_node in enumerate(args_obj.defaults):
        if _is_mutable_default(def_node):
            param = pos_args[offset + idx]
            name = f"{qualname}() -> {param.arg}"
            issues.append(
                make_issue(filename, def_node.lineno, "mutable default argument", name, get_snippet(source, node))
            )

    for param, def_node in zip(args_obj.kwonlyargs, args_obj.kw_defaults):
        if def_node is not None and _is_mutable_default(def_node):
            name = f"{qualname}() -> {param.arg}"
            issues.append(
                make_issue(filename, def_node.lineno, "mutable default argument", name, get_snippet(source, node))
            )
    return issues


def _check_param_count(node: ast.AST, source: str, filename: str, func_name: str) -> list[dict]:
    """Flags functions exceeding the 5 parameter limit, excluding self and cls."""
    args_obj = getattr(node, "args", None)
    if not args_obj:
        return []

    all_args = [a.arg for a in args_obj.posonlyargs + args_obj.args + args_obj.kwonlyargs]
    if args_obj.vararg:
        all_args.append(args_obj.vararg.arg)
    if args_obj.kwarg:
        all_args.append(args_obj.kwarg.arg)

    counted = [p for p in all_args if p not in ("self", "cls")]
    if len(counted) > 5:
        issue = make_issue(filename, node.lineno, "too many parameters", func_name, get_snippet(source, node))
        issue["why"] = f"Function has {len(counted)} parameters (limit 5). {issue['why']}"
        return [issue]
    return []


def _check_func_length_and_nesting(node: ast.AST, source: str, filename: str, func_name: str) -> list[dict]:
    """Flags functions exceeding 30 lines or 3 levels of statement nesting."""
    issues = []
    if getattr(node, "end_lineno", None) is not None:
        length = node.end_lineno - node.lineno + 1
        if length > 30:
            issue = make_issue(filename, node.lineno, "function too long", func_name, get_snippet(source, node))
            issue["why"] = f"Function is {length} lines long (limit 30). {issue['why']}"
            issues.append(issue)

    depth = max_nesting(node)
    if depth > 3:
        issue = make_issue(filename, node.lineno, "deep nesting", func_name, get_snippet(source, node))
        issue["why"] = f"Nesting level is {depth} (limit 3). {issue['why']}"
        issues.append(issue)

    return issues


class _DetectorVisitor(ast.NodeVisitor):
    """AST visitor traversing functions, classes, and statements to gather issues."""

    def __init__(self, source: str, filename: str):
        """Initializes visitor state with source text and file path."""
        self.source = source
        self.filename = filename
        self.issues: list[dict] = []
        self.scope_stack: list[str] = []
        self.func_scope_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        """Checks class docstrings and traverses class body."""
        self.scope_stack.append(node.name)
        qualname = ".".join(self.scope_stack)
        if not ast.get_docstring(node):
            self.issues.append(
                make_issue(self.filename, node.lineno, "missing docstring", qualname, get_snippet(self.source, node))
            )
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Analyzes sync and async functions for docstrings, size, and bad practices."""
        self.scope_stack.append(node.name)
        self.func_scope_stack.append(node.name)
        qualname = ".".join(self.scope_stack)
        func_name = f"{qualname}()"

        if not ast.get_docstring(node):
            self.issues.append(
                make_issue(self.filename, node.lineno, "missing docstring", func_name, get_snippet(self.source, node))
            )

        self.issues.extend(_check_param_count(node, self.source, self.filename, func_name))
        self.issues.extend(_check_func_length_and_nesting(node, self.source, self.filename, func_name))
        self.issues.extend(_check_mutable_defaults(node, self.source, self.filename, qualname))

        for var_name, line, snippet in _find_unused_variables(node, self.source):
            var_target = f"{qualname}() -> {var_name}"
            self.issues.append(
                make_issue(self.filename, line, "unused variable", var_target, snippet)
            )

        self.generic_visit(node)
        self.func_scope_stack.pop()
        self.scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        """Flags bare except handlers and records the enclosing function."""
        if node.type is None:
            if self.func_scope_stack:
                qualname = ".".join(self.scope_stack)
                name = f"{qualname}() -> bare except"
            else:
                name = "bare except"
            self.issues.append(
                make_issue(self.filename, node.lineno, "bare except", name, get_snippet(self.source, node))
            )
        self.generic_visit(node)


def detect_source(source: str, filename: str = "<string>") -> list[dict]:
    """Analyzes a Python source string and returns detected code issues."""
    tree = ast.parse(source, filename=filename)
    issues: list[dict] = []

    if not ast.get_docstring(tree):
        lines = source.splitlines()
        first_line = lines[0] if lines else ""
        issues.append(
            make_issue(filename, 1, "missing module docstring", "module", first_line)
        )

    issues.extend(_check_unused_imports(tree, source, filename))

    visitor = _DetectorVisitor(source, filename)
    visitor.visit(tree)
    issues.extend(visitor.issues)

    issues.sort(key=lambda x: (x["file"], x["line"], x["type"], x["name"]))
    return issues


def detect(path: str) -> list[dict]:
    """Reads a file as UTF-8 and returns detected code problems."""
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    return detect_source(source, filename=path)


def _scan_py_file(file_path: str) -> list[dict]:
    """Scans a single Python file, returning detected issues or syntax error."""
    try:
        return detect(file_path)
    except SyntaxError as err:
        snippet = err.text.strip() if err.text else ""
        return [
            make_issue(
                file_path,
                err.lineno or 1,
                "syntax error",
                "syntax error",
                snippet,
            )
        ]


def detect_folder(folder: str) -> list[dict]:
    """Recursively finds .py files in folder and detects issues without crashing."""
    skip_dirs = {"venv", ".venv", "__pycache__", ".git", "node_modules"}
    all_issues: list[dict] = []

    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        py_files = [f for f in files if f.endswith(".py")]
        for file in py_files:
            file_path = os.path.join(root, file)
            all_issues.extend(_scan_py_file(file_path))

    all_issues.sort(key=lambda x: (x["file"], x["line"], x["type"], x["name"]))
    return all_issues


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sample.py"
    try:
        if os.path.isdir(target):
            results = detect_folder(target)
        else:
            results = detect(target)
        print(json.dumps(results, indent=2))
    except FileNotFoundError:
        print(f"Error: Target '{target}' not found.", file=sys.stderr)
        sys.exit(1)
    except SyntaxError as exc:
        print(f"Syntax error in '{target}' at line {exc.lineno}: {exc.msg}", file=sys.stderr)
        sys.exit(1)
    except UnicodeDecodeError as exc:
        print(f"Encoding error reading '{target}': {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error analyzing '{target}': {exc}", file=sys.stderr)
        sys.exit(1)