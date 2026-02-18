"""Python AST + TypeScript regex pattern extraction for code analysis."""

from __future__ import annotations

import ast
import re
from collections import Counter

from stratus.learning.models import Detection, DetectionType


def extract_python_patterns(source: str) -> dict:
    """Extract structural patterns from Python source using stdlib ast."""
    result: dict = {
        "functions": [],
        "classes": [],
        "imports": [],
        "error_handlers": [],
    }
    if not source.strip():
        return result

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [arg.arg for arg in node.args.args if arg.arg != "self"]
            return_type = None
            if node.returns:
                return_type = _unparse_safe(node.returns)
            decorators = [_unparse_safe(d) for d in node.decorator_list]
            result["functions"].append({
                "name": node.name,
                "params": params,
                "return_type": return_type,
                "decorators": decorators,
            })

        elif isinstance(node, ast.ClassDef):
            bases = [_unparse_safe(b) for b in node.bases]
            result["classes"].append({
                "name": node.name,
                "bases": bases,
            })

        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append({
                    "type": "import",
                    "module": alias.name,
                })

        elif isinstance(node, ast.ImportFrom):
            result["imports"].append({
                "type": "from",
                "module": node.module or "",
                "names": [alias.name for alias in node.names],
            })

        elif isinstance(node, ast.ExceptHandler):
            exceptions: list[str] = []
            if node.type:
                if isinstance(node.type, ast.Tuple):
                    exceptions = [_unparse_safe(e) for e in node.type.elts]
                else:
                    exceptions = [_unparse_safe(node.type)]
            result["error_handlers"].append({
                "exceptions": exceptions,
                "handler_type": "except",
            })

    return result


def _unparse_safe(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except (ValueError, TypeError):
        return ""


# --- TypeScript regex extraction ---

_TS_FUNC_RE = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(",
)
_TS_ARROW_RE = re.compile(
    r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(",
)
_TS_METHOD_RE = re.compile(
    r"(?:public|private|protected|async|static|\s)+(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?",
)
_TS_CLASS_RE = re.compile(
    r"class\s+(\w+)(?:\s+extends\s+(\w+))?",
)
_TS_IMPORT_RE = re.compile(
    r"import\s+.+?\s+from\s+['\"]([^'\"]+)['\"]",
)


def extract_typescript_patterns(source: str) -> dict:
    """Extract structural patterns from TypeScript source using regex."""
    result: dict = {
        "functions": [],
        "classes": [],
        "imports": [],
    }
    if not source.strip():
        return result

    for m in _TS_FUNC_RE.finditer(source):
        result["functions"].append({"name": m.group(1), "type": "function"})

    for m in _TS_ARROW_RE.finditer(source):
        result["functions"].append({"name": m.group(1), "type": "arrow"})

    for m in _TS_METHOD_RE.finditer(source):
        name = m.group(1)
        # Skip keywords that look like methods
        if name not in {"if", "for", "while", "switch", "return", "class", "function"}:
            result["functions"].append({"name": name, "type": "method"})

    for m in _TS_CLASS_RE.finditer(source):
        result["classes"].append({
            "name": m.group(1),
            "extends": m.group(2) or "",
        })

    for m in _TS_IMPORT_RE.finditer(source):
        result["imports"].append({"module": m.group(1)})

    return result


# --- Cross-file pattern detection ---

def find_repeated_patterns(
    patterns_by_file: dict[str, dict],
    *,
    function_threshold: int = 3,
    class_threshold: int = 3,
    error_handler_threshold: int = 4,
) -> list[Detection]:
    """Find patterns repeated across files above the given thresholds."""
    if not patterns_by_file:
        return []

    detections: list[Detection] = []

    # Detect repeated function signatures
    func_counter: Counter[str] = Counter()
    func_files: dict[str, list[str]] = {}
    for filepath, patterns in patterns_by_file.items():
        for func in patterns.get("functions", []):
            sig = f"{func['name']}({','.join(func.get('params', []))})"
            func_counter[sig] += 1
            func_files.setdefault(sig, []).append(filepath)

    for sig, count in func_counter.items():
        if count >= function_threshold:
            detections.append(
                Detection(
                    type=DetectionType.CODE_PATTERN,
                    count=count,
                    confidence_raw=min(0.4 + count * 0.1, 0.9),
                    files=func_files[sig],
                    description=f"Repeated function signature: {sig}",
                    instances=[{"signature": sig, "count": count}],
                )
            )

    # Detect repeated class hierarchies (same base class)
    base_counter: Counter[str] = Counter()
    base_files: dict[str, list[str]] = {}
    for filepath, patterns in patterns_by_file.items():
        for cls in patterns.get("classes", []):
            for base in cls.get("bases", []):
                if base:
                    base_counter[base] += 1
                    base_files.setdefault(base, []).append(filepath)

    for base, count in base_counter.items():
        if count >= class_threshold:
            detections.append(
                Detection(
                    type=DetectionType.CODE_PATTERN,
                    count=count,
                    confidence_raw=min(0.4 + count * 0.1, 0.9),
                    files=base_files[base],
                    description=f"Repeated class hierarchy: extends {base}",
                    instances=[{"base_class": base, "count": count}],
                )
            )

    # Detect repeated error handling patterns
    handler_counter: Counter[str] = Counter()
    handler_files: dict[str, list[str]] = {}
    for filepath, patterns in patterns_by_file.items():
        for handler in patterns.get("error_handlers", []):
            key = ",".join(sorted(handler.get("exceptions", [])))
            if key:
                handler_counter[key] += 1
                handler_files.setdefault(key, []).append(filepath)

    for key, count in handler_counter.items():
        if count >= error_handler_threshold:
            detections.append(
                Detection(
                    type=DetectionType.CODE_PATTERN,
                    count=count,
                    confidence_raw=min(0.3 + count * 0.1, 0.85),
                    files=handler_files[key],
                    description=f"Repeated error handler: except {key}",
                    instances=[{"exceptions": key, "count": count}],
                )
            )

    return detections
