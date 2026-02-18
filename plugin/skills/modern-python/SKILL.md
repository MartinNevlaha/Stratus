---
name: modern-python
description: Apply modern Python tooling and best practices. Use when setting up a Python project, auditing tooling, or ensuring uv/ruff/basedpyright/pytest are correctly configured.
context: fork
agent: implementation-expert
---

# Modern Python Tooling

Standards for Python 3.12+ projects. No legacy tooling.

## Package Management: uv ONLY

```bash
# Install dependency
uv add package-name

# Run script
uv run python script.py

# Run tests
uv run pytest

# Never use pip directly
```

### `pyproject.toml` Structure

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["httpx>=0.27", "pydantic>=2"]

[tool.uv]
dev-dependencies = ["pytest>=8", "ruff>=0.8", "basedpyright>=1.18"]
```

## Linting & Formatting: ruff

```bash
uv run ruff check src/ tests/        # lint
uv run ruff check src/ tests/ --fix  # auto-fix
uv run ruff format src/ tests/       # format
```

### `pyproject.toml` config

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]
```

## Type Checking: basedpyright

```bash
uv run basedpyright src/
```

```toml
[tool.basedpyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
```

### Type Hints (Modern Syntax)

```python
# Python 3.12+ syntax
def process(items: list[str], config: dict[str, int] | None = None) -> bool: ...

# Legacy (pre-3.10) — avoid
from typing import List, Optional, Dict
def process(items: List[str], config: Optional[Dict[str, int]] = None) -> bool: ...
```

## Testing: pytest

```bash
uv run pytest -q                              # run all
uv run pytest --cov=src --cov-fail-under=80  # with coverage
uv run pytest tests/test_foo.py::TestBar -q  # specific test
```

### Test Patterns

```python
from unittest.mock import MagicMock, patch

class TestMyModule:
    def test_success_case(self) -> None:
        with patch("my_module.subprocess.run", return_value=MagicMock(returncode=0)):
            result = my_function()
        assert result is True

    def test_failure_case(self, tmp_path: Path) -> None:
        # Use tmp_path fixture for file operations
        (tmp_path / "config.json").write_text('{"key": "value"}')
        result = load_config(str(tmp_path / "config.json"))
        assert result["key"] == "value"
```

## Checklist

- [ ] `uv` used for all package operations
- [ ] `ruff check` passes with no errors
- [ ] `basedpyright` passes with no errors
- [ ] All public functions have type hints
- [ ] No `Optional[X]` (use `X | None`)
- [ ] No `List[X]` (use `list[X]`)
- [ ] Coverage >= 80%
- [ ] No bare `except` clauses
