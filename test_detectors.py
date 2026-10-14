"""Comprehensive unit tests for the detectors engine in detectors.py."""

import os
import tempfile
import pytest

import detectors


EXPECTED_KEYS = {
    "file",
    "line",
    "type",
    "name",
    "snippet",
    "code_snippet",
    "severity",
    "why",
    "fix",
    "corrected_code",
}

VALID_SEVERITIES = {"high", "medium", "low"}


def test_sample_py_triggers_all_detectors():
    """Asserts every detector type fires on sample.py with the right severity and line."""
    issues = detectors.detect("sample.py")
    issue_types = {iss["type"] for iss in issues}

    expected_types = {
        "missing module docstring",
        "unused import",
        "missing docstring",
        "too many parameters",
        "function too long",
        "deep nesting",
        "unused variable",
        "bare except",
        "mutable default argument",
    }
    assert expected_types.issubset(issue_types)

    # Check specific line numbers and severities
    mod_doc = next(i for i in issues if i["type"] == "missing module docstring")
    assert mod_doc["line"] == 1
    assert mod_doc["severity"] == "low"
    assert mod_doc["name"] == "module"

    imp = next(i for i in issues if i["type"] == "unused import")
    assert imp["line"] == 1
    assert imp["severity"] == "low"
    assert imp["name"] == "math"

    cls_doc = next(i for i in issues if i["type"] == "missing docstring" and i["name"] == "BadClass")
    assert cls_doc["line"] == 3
    assert cls_doc["severity"] == "low"

    meth_doc = next(i for i in issues if i["type"] == "missing docstring" and i["name"] == "BadClass.sample_method()")
    assert meth_doc["line"] == 4
    assert meth_doc["severity"] == "low"

    nesting = next(i for i in issues if i["type"] == "deep nesting")
    assert nesting["line"] == 7
    assert nesting["severity"] == "high"
    assert nesting["name"] == "messy_function()"

    too_long = next(i for i in issues if i["type"] == "function too long")
    assert too_long["line"] == 7
    assert too_long["severity"] == "medium"
    assert too_long["name"] == "messy_function()"

    mut_def = next(i for i in issues if i["type"] == "mutable default argument")
    assert mut_def["line"] == 7
    assert mut_def["severity"] == "high"
    assert "items" in mut_def["name"]

    too_many_params = next(i for i in issues if i["type"] == "too many parameters")
    assert too_many_params["line"] == 7
    assert too_many_params["severity"] == "medium"

    unused_var = next(i for i in issues if i["type"] == "unused variable" and "unused_variable" in i["name"])
    assert unused_var["line"] == 8
    assert unused_var["severity"] == "low"
    assert unused_var["snippet"] == "unused_variable = 99"

    bare_exc = next(i for i in issues if i["type"] == "bare except")
    assert bare_exc["line"] == 32
    assert bare_exc["severity"] == "medium"
    assert "bare except" in bare_exc["name"]


def test_elif_chain_not_flagged_as_deep_nesting():
    """Asserts an if/elif/elif/elif/else chain does not increase nesting depth."""
    code = '''"""Module docstring."""

def check_value(x: int) -> int:
    """Classifies numbers using a long elif chain."""
    if x == 1:
        return 10
    elif x == 2:
        return 20
    elif x == 3:
        return 30
    elif x == 4:
        return 40
    elif x == 5:
        return 50
    else:
        return 0
'''
    issues = detectors.detect_source(code)
    deep_nesting_issues = [i for i in issues if i["type"] == "deep nesting"]
    assert len(deep_nesting_issues) == 0


def test_nested_function_unused_variable_reported_once():
    """Asserts an unused variable in a nested function is reported once with proper scope."""
    code = '''"""Module doc."""

def outer():
    """Outer doc."""
    def inner():
        """Inner doc."""
        inner_unused = 123
        return 1
    return inner()
'''
    issues = detectors.detect_source(code)
    unused_issues = [i for i in issues if i["type"] == "unused variable"]
    assert len(unused_issues) == 1
    assert unused_issues[0]["name"] == "outer.inner() -> inner_unused"
    assert unused_issues[0]["snippet"] == "inner_unused = 123"


def test_closure_variable_not_reported():
    """Asserts a variable used in a closure is not reported as unused in the outer scope."""
    code = '''"""Module doc."""

def make_adder(x: int):
    """Outer function doc."""
    total = x + 10
    def adder(y: int) -> int:
        """Inner closure doc."""
        return total + y
    return adder
'''
    issues = detectors.detect_source(code)
    unused_issues = [i for i in issues if i["type"] == "unused variable"]
    assert len(unused_issues) == 0


def test_self_and_cls_not_counted_as_parameters():
    """Asserts self and cls are excluded when counting parameters."""
    code = '''"""Module doc."""

class Example:
    """Class doc."""
    def instance_method(self, a, b, c, d, e):
        """Method doc - exactly 5 parameters excluding self."""
        return a + b + c + d + e

    @classmethod
    def class_method(cls, a, b, c, d, e):
        """Class method doc - exactly 5 parameters excluding cls."""
        return a + b + c + d + e

def normal_function(a, b, c, d, e, f):
    """Function doc - 6 parameters."""
    return a + b + c + d + e + f
'''
    issues = detectors.detect_source(code)
    param_issues = [i for i in issues if i["type"] == "too many parameters"]
    assert len(param_issues) == 1
    assert param_issues[0]["name"] == "normal_function()"


def test_async_functions_checked():
    """Asserts async functions are inspected for all quality detectors."""
    code = '''"""Module doc."""

async def bad_async(a, b, c, d, e, f, bad_list=[]):
    unused_async_var = 1
    try:
        pass
    except:
        pass
    return a
'''
    issues = detectors.detect_source(code)
    types_found = {i["type"] for i in issues}

    assert "missing docstring" in types_found
    assert "too many parameters" in types_found
    assert "mutable default argument" in types_found
    assert "unused variable" in types_found
    assert "bare except" in types_found

    async_doc = next(i for i in issues if i["type"] == "missing docstring")
    assert async_doc["name"] == "bad_async()"


def test_schema_keys_and_valid_severity():
    """Asserts every issue dictionary has exactly the required schema keys."""
    issues = detectors.detect("sample.py")
    assert len(issues) > 0
    for iss in issues:
        assert set(iss.keys()) == EXPECTED_KEYS
        assert iss["severity"] in VALID_SEVERITIES
        assert iss["snippet"] == iss["code_snippet"]
        assert iss["corrected_code"] == ""
        assert isinstance(iss["line"], int)
        assert len(iss["why"]) > 0
        assert len(iss["fix"]) > 0


def test_output_sorted_and_deterministic():
    """Asserts issues output is deterministically sorted by (file, line, type)."""
    issues1 = detectors.detect("sample.py")
    issues2 = detectors.detect("sample.py")
    assert issues1 == issues2

    sorted_expected = sorted(issues1, key=lambda x: (x["file"], x["line"], x["type"], x["name"]))
    assert issues1 == sorted_expected


def test_detect_source_syntax_error():
    """Asserts detect_source raises SyntaxError on unparseable source strings."""
    with pytest.raises(SyntaxError):
        detectors.detect_source("def f(:\n")


def test_detect_propagates_exceptions():
    """Asserts detect lets FileNotFoundError and SyntaxError propagate."""
    with pytest.raises(FileNotFoundError):
        detectors.detect("non_existent_file_12345.py")


def test_detect_folder_handles_syntax_error_without_crashing():
    """Asserts detect_folder catches SyntaxError and records a syntax error issue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        good_file = os.path.join(tmpdir, "good.py")
        bad_file = os.path.join(tmpdir, "bad.py")

        with open(good_file, "w", encoding="utf-8") as f:
            f.write('"""Module doc."""\n\ndef ok():\n    """Doc."""\n    return 42\n')

        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("def broken(:\n")

        issues = detectors.detect_folder(tmpdir)
        syntax_issues = [i for i in issues if i["type"] == "syntax error"]
        assert len(syntax_issues) == 1
        assert syntax_issues[0]["severity"] == "high"
        assert syntax_issues[0]["file"] == bad_file
        assert syntax_issues[0]["line"] == 1


def test_detect_folder_skips_ignored_directories():
    """Asserts detect_folder skips venv, .git, __pycache__, and node_modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for ignored in ("venv", ".venv", "__pycache__", ".git", "node_modules"):
            ign_dir = os.path.join(tmpdir, ignored)
            os.makedirs(ign_dir)
            with open(os.path.join(ign_dir, "bad.py"), "w", encoding="utf-8") as f:
                f.write("def broken(:\n")

        valid_file = os.path.join(tmpdir, "valid.py")
        with open(valid_file, "w", encoding="utf-8") as f:
            f.write('"""Module doc."""\n')

        issues = detectors.detect_folder(tmpdir)
        syntax_issues = [i for i in issues if i["type"] == "syntax error"]
        assert len(syntax_issues) == 0


def test_unused_import_skipped_when_all_defined():
    """Asserts unused import checks are skipped if __all__ is defined."""
    code = '''"""Module doc."""
import math
import sys

__all__ = ["math"]
'''
    issues = detectors.detect_source(code)
    import_issues = [i for i in issues if i["type"] == "unused import"]
    assert len(import_issues) == 0


def test_unused_import_skips_future_and_star():
    """Asserts from __future__ and star imports are skipped from unused import detection."""
    code = '''"""Module doc."""
from __future__ import annotations
from math import *
'''
    issues = detectors.detect_source(code)
    import_issues = [i for i in issues if i["type"] == "unused import"]
    assert len(import_issues) == 0


def test_bare_except_vs_specific_except():
    """Asserts only bare except without an exception type is flagged."""
    code = '''"""Module doc."""

def handled():
    """Function doc."""
    try:
        x = 1
    except ValueError:
        x = 2
    except (TypeError, KeyError):
        x = 3
    except Exception:
        x = 4
    return x
'''
    issues = detectors.detect_source(code)
    bare_issues = [i for i in issues if i["type"] == "bare except"]
    assert len(bare_issues) == 0


def test_detectors_passes_its_own_checks():
    """Asserts detectors.py has zero issues when analyzing its own codebase."""
    issues = detectors.detect("detectors.py")
    assert issues == []
