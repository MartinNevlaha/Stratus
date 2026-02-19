"""Tests for stratus.self_debug.analyzer — static analysis via stdlib ast."""

from __future__ import annotations

from pathlib import Path

# These imports will fail until the production module is created (expected RED state).
# pyright: reportMissingImports=false
from stratus.self_debug.analyzer import analyze_directory, analyze_file  # type: ignore[import]
from stratus.self_debug.models import Issue, IssueType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _analyze(source: str, file_path: str = "test_module.py") -> list[Issue]:
    return analyze_file(source, file_path)


# ---------------------------------------------------------------------------
# TestDetectBareExcepts
# ---------------------------------------------------------------------------


class TestDetectBareExcepts:
    def test_detects_bare_except(self) -> None:
        source = """\
try:
    risky()
except:
    pass
"""
        issues = _analyze(source)
        bare = [i for i in issues if i.type == IssueType.BARE_EXCEPT]
        assert len(bare) == 1

    def test_bare_except_correct_line_number(self) -> None:
        source = """\
try:
    risky()
except:
    pass
"""
        issues = _analyze(source)
        bare = [i for i in issues if i.type == IssueType.BARE_EXCEPT]
        assert bare[0].line_start == 3

    def test_bare_except_returns_correct_type(self) -> None:
        source = "try:\n    x()\nexcept:\n    pass\n"
        issues = _analyze(source)
        bare = [i for i in issues if i.type == IssueType.BARE_EXCEPT]
        assert bare[0].type == IssueType.BARE_EXCEPT

    def test_bare_except_suggestion_mentions_exception(self) -> None:
        source = "try:\n    x()\nexcept:\n    pass\n"
        issues = _analyze(source)
        bare = [i for i in issues if i.type == IssueType.BARE_EXCEPT]
        assert "except Exception:" in bare[0].suggestion

    def test_does_not_flag_except_exception(self) -> None:
        source = """\
try:
    risky()
except Exception:
    pass
"""
        issues = _analyze(source)
        bare = [i for i in issues if i.type == IssueType.BARE_EXCEPT]
        assert len(bare) == 0

    def test_does_not_flag_except_valueerror(self) -> None:
        source = """\
try:
    risky()
except ValueError:
    pass
"""
        issues = _analyze(source)
        bare = [i for i in issues if i.type == IssueType.BARE_EXCEPT]
        assert len(bare) == 0

    def test_multiple_bare_excepts(self) -> None:
        source = """\
try:
    a()
except:
    pass

try:
    b()
except:
    pass
"""
        issues = _analyze(source)
        bare = [i for i in issues if i.type == IssueType.BARE_EXCEPT]
        assert len(bare) == 2


# ---------------------------------------------------------------------------
# TestDetectUnusedImports
# ---------------------------------------------------------------------------


class TestDetectUnusedImports:
    def test_detects_unused_import(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source)
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert len(unused) == 1

    def test_detects_unused_from_import(self) -> None:
        source = "from pathlib import Path\n\nx = 1\n"
        issues = _analyze(source)
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert len(unused) == 1

    def test_does_not_flag_used_import(self) -> None:
        source = "import os\n\nx = os.getcwd()\n"
        issues = _analyze(source)
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert len(unused) == 0

    def test_does_not_flag_used_from_import(self) -> None:
        source = "from pathlib import Path\n\np = Path('.')\n"
        issues = _analyze(source)
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert len(unused) == 0

    def test_skips_init_py(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source, file_path="__init__.py")
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert len(unused) == 0

    def test_skips_init_py_nested_path(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source, file_path="stratus/memory/__init__.py")
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert len(unused) == 0

    def test_skips_type_checking_imports(self) -> None:
        source = """\
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import os
    from pathlib import Path

x = 1
"""
        issues = _analyze(source)
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert len(unused) == 0

    def test_skips_future_annotations(self) -> None:
        source = "from __future__ import annotations\n\nx = 1\n"
        issues = _analyze(source)
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert len(unused) == 0

    def test_returns_unused_import_type(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source)
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert unused[0].type == IssueType.UNUSED_IMPORT

    def test_unused_import_has_correct_file_path(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source, file_path="mymodule.py")
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert unused[0].file_path == "mymodule.py"


# ---------------------------------------------------------------------------
# TestDetectMissingReturnTypes
# ---------------------------------------------------------------------------


class TestDetectMissingReturnTypes:
    def test_detects_public_function_missing_return_type(self) -> None:
        source = "def foo(x):\n    return x\n"
        issues = _analyze(source)
        hints = [i for i in issues if i.type == IssueType.MISSING_TYPE_HINT]
        assert len(hints) == 1

    def test_does_not_flag_private_function(self) -> None:
        source = "def _foo(x):\n    return x\n"
        issues = _analyze(source)
        hints = [i for i in issues if i.type == IssueType.MISSING_TYPE_HINT]
        assert len(hints) == 0

    def test_does_not_flag_function_with_return_annotation(self) -> None:
        source = "def foo(x) -> int:\n    return x\n"
        issues = _analyze(source)
        hints = [i for i in issues if i.type == IssueType.MISSING_TYPE_HINT]
        assert len(hints) == 0

    def test_does_not_flag_dunder_init(self) -> None:
        source = "class A:\n    def __init__(self):\n        pass\n"
        issues = _analyze(source)
        hints = [i for i in issues if i.type == IssueType.MISSING_TYPE_HINT]
        assert len(hints) == 0

    def test_does_not_flag_dunder_str(self) -> None:
        source = "class A:\n    def __str__(self):\n        return ''\n"
        issues = _analyze(source)
        hints = [i for i in issues if i.type == IssueType.MISSING_TYPE_HINT]
        assert len(hints) == 0

    def test_suggestion_mentions_report_only(self) -> None:
        source = "def foo():\n    pass\n"
        issues = _analyze(source)
        hints = [i for i in issues if i.type == IssueType.MISSING_TYPE_HINT]
        suggestion_lower = hints[0].suggestion.lower()
        assert "report" in suggestion_lower

    def test_detects_async_public_function(self) -> None:
        source = "async def fetch():\n    pass\n"
        issues = _analyze(source)
        hints = [i for i in issues if i.type == IssueType.MISSING_TYPE_HINT]
        assert len(hints) == 1

    def test_does_not_flag_async_function_with_return_type(self) -> None:
        source = "async def fetch() -> None:\n    pass\n"
        issues = _analyze(source)
        hints = [i for i in issues if i.type == IssueType.MISSING_TYPE_HINT]
        assert len(hints) == 0


# ---------------------------------------------------------------------------
# TestAnalyzeFile
# ---------------------------------------------------------------------------


class TestAnalyzeFile:
    def test_empty_source_returns_empty(self) -> None:
        issues = _analyze("")
        assert issues == []

    def test_whitespace_only_returns_empty(self) -> None:
        issues = _analyze("   \n\n   ")
        assert issues == []

    def test_syntax_error_returns_empty(self) -> None:
        issues = _analyze("def (broken syntax")
        assert issues == []

    def test_combines_all_detectors(self) -> None:
        source = """\
import os

def foo():
    try:
        pass
    except:
        pass
"""
        issues = _analyze(source)
        types = {i.type for i in issues}
        assert IssueType.UNUSED_IMPORT in types
        assert IssueType.BARE_EXCEPT in types
        assert IssueType.MISSING_TYPE_HINT in types

    def test_issue_has_correct_file_path(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source, file_path="src/mymod.py")
        assert all(i.file_path == "src/mymod.py" for i in issues)

    def test_issue_id_format(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source, file_path="mod.py")
        unused = [i for i in issues if i.type == IssueType.UNUSED_IMPORT]
        assert unused[0].id == f"mod.py:1:{IssueType.UNUSED_IMPORT.value}"

    def test_issue_has_description(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source)
        assert all(i.description for i in issues)

    def test_issue_has_suggestion(self) -> None:
        source = "import os\n\nx = 1\n"
        issues = _analyze(source)
        assert all(i.suggestion for i in issues)


# ---------------------------------------------------------------------------
# TestAnalyzeDirectory
# ---------------------------------------------------------------------------


class TestAnalyzeDirectory:
    def test_walks_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text("import os\n\nx = 1\n")
        issues, analyzed, skipped = analyze_directory(
            tmp_path,
            allowed_prefixes=frozenset(),
            denied_prefixes=frozenset(),
        )
        assert analyzed == 1
        assert len(issues) >= 1

    def test_skips_non_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "data.json").write_text("{}")
        _issues, analyzed, _skipped = analyze_directory(
            tmp_path,
            allowed_prefixes=frozenset(),
            denied_prefixes=frozenset(),
        )
        assert analyzed == 0

    def test_respects_allowed_prefixes(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("import os\n\nx = 1\n")
        (tmp_path / "other.py").write_text("import os\n\nx = 1\n")

        _issues, analyzed, skipped = analyze_directory(
            tmp_path,
            allowed_prefixes=frozenset(["src/"]),
            denied_prefixes=frozenset(),
        )
        assert analyzed == 1
        assert skipped >= 1

    def test_respects_denied_prefixes(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").write_text("import os\n\nx = 1\n")
        (tmp_path / "main.py").write_text("import os\n\nx = 1\n")

        _issues, analyzed, skipped = analyze_directory(
            tmp_path,
            allowed_prefixes=frozenset(),
            denied_prefixes=frozenset(["tests/"]),
        )
        assert analyzed == 1
        assert skipped >= 1

    def test_returns_tuple_of_three(self, tmp_path: Path) -> None:
        result = analyze_directory(
            tmp_path,
            allowed_prefixes=frozenset(),
            denied_prefixes=frozenset(),
        )
        assert len(result) == 3

    def test_nonexistent_directory_returns_empty(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        issues, analyzed, skipped = analyze_directory(
            missing,
            allowed_prefixes=frozenset(),
            denied_prefixes=frozenset(),
        )
        assert issues == []
        assert analyzed == 0
        assert skipped == 0

    def test_nested_directories_walked(self, tmp_path: Path) -> None:
        subdir = tmp_path / "a" / "b"
        subdir.mkdir(parents=True)
        (subdir / "deep.py").write_text("import os\n\nx = 1\n")

        _issues, analyzed, _skipped = analyze_directory(
            tmp_path,
            allowed_prefixes=frozenset(),
            denied_prefixes=frozenset(),
        )
        assert analyzed == 1
