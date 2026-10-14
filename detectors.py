import ast
import sys

def detect(path: str) -> list[dict]:
    """
    Parses a Python file using AST and returns a list of detected problems
    matching the team's agreed schema.
    """
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    # Let SyntaxError propagate as requested
    tree = ast.parse(source)
    issues = []

    def get_snippet(node):
        """Extracts source segment capped at ~30 lines."""
        seg = ast.get_source_segment(source, node)
        if seg:
            lines = seg.splitlines()
            if len(lines) > 30:
                return "\n".join(lines[:30]) + "\n... (truncated)"
            return seg
        return ""

    # 1. Module-level docstring check
    if not ast.get_docstring(tree):
        first_line = source.splitlines()[0] if source.splitlines() else ""
        issues.append({
            "file": path,
            "line": 1,
            "type": "missing module docstring",
            "name": "module",
            "snippet": first_line,
            "severity": "low",
            "why": "",
            "fix": "",
            "corrected_code": ""
        })

    class DetectorVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            if not ast.get_docstring(node):
                issues.append({
                    "file": path,
                    "line": node.lineno,
                    "type": "missing docstring",
                    "name": f"class {node.name}",
                    "snippet": get_snippet(node),
                    "severity": "low",
                    "why": "",
                    "fix": "",
                    "corrected_code": ""
                })
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            # Missing docstring check
            if not ast.get_docstring(node):
                issues.append({
                    "file": path,
                    "line": node.lineno,
                    "type": "missing docstring",
                    "name": f"{node.name}()",
                    "snippet": get_snippet(node),
                    "severity": "low",
                    "why": "",
                    "fix": "",
                    "corrected_code": ""
                })

            # Too many parameters (>5)
            if len(node.args.args) > 5:
                issues.append({
                    "file": path,
                    "line": node.lineno,
                    "type": "too many parameters",
                    "name": f"{node.name}()",
                    "snippet": get_snippet(node),
                    "severity": "medium",
                    "why": "",
                    "fix": "",
                    "corrected_code": ""
                })

            # Function too long (>30 lines) - includes +1 to count start line accurately
            if hasattr(node, "end_lineno") and node.end_lineno:
                length = node.end_lineno - node.lineno + 1
                if length > 30:
                    issues.append({
                        "file": path,
                        "line": node.lineno,
                        "type": "function too long",
                        "name": f"{node.name}() ({length} lines)",
                        "snippet": get_snippet(node),
                        "severity": "medium",
                        "why": "",
                        "fix": "",
                        "corrected_code": ""
                    })

            # Deep nesting check (>3 levels)
            self.check_nesting(node)

            # Unused variable check
            self.check_unused_vars(node)

            self.generic_visit(node)

        def check_nesting(self, node):
            max_depth = 0
            def recurse(n, depth):
                nonlocal max_depth
                max_depth = max(max_depth, depth)
                for child in ast.iter_child_nodes(n):
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                        recurse(child, depth + 1)
                    else:
                        recurse(child, depth)

            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                    recurse(child, 1)

            if max_depth > 3:
                issues.append({
                    "file": path,
                    "line": node.lineno,
                    "type": "deep nesting",
                    "name": f"{node.name}()",
                    "snippet": get_snippet(node),
                    "severity": "high",
                    "why": "",
                    "fix": "",
                    "corrected_code": ""
                })

        def check_unused_vars(self, node):
            assigned = set()
            loaded = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for t in child.targets:
                        if isinstance(t, ast.Name):
                            assigned.add((t.id, t.lineno))
                elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    loaded.add(child.id)

            for var_name, lineno in assigned:
                if var_name not in loaded and not var_name.startswith("_"):
                    issues.append({
                        "file": path,
                        "line": lineno,
                        "type": "unused variable",
                        "name": f"{node.name}() -> {var_name}",
                        "snippet": f"unused variable: {var_name}",
                        "severity": "low",
                        "why": "",
                        "fix": "",
                        "corrected_code": ""
                    })

    DetectorVisitor().visit(tree)
    return issues

if __name__ == "__main__":
    import json
    test_target = sys.argv[1] if len(sys.argv) > 1 else "sample.py"
    try:
        results = detect(test_target)
        print(json.dumps(results, indent=2))
    except Exception as err:
        print(f"Error parsing file: {err}")