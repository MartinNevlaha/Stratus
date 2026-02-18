"""Tests for learning/ast_analyzer.py — Python AST + TypeScript regex extraction."""

from __future__ import annotations

from stratus.learning.ast_analyzer import (
    extract_python_patterns,
    extract_typescript_patterns,
    find_repeated_patterns,
)


class TestExtractPythonPatterns:
    def test_function_signatures(self):
        source = '''
def greet(name: str) -> str:
    return f"Hello, {name}"

def add(a: int, b: int) -> int:
    return a + b
'''
        patterns = extract_python_patterns(source)
        assert len(patterns["functions"]) == 2
        assert patterns["functions"][0]["name"] == "greet"
        assert patterns["functions"][0]["params"] == ["name"]
        assert patterns["functions"][1]["name"] == "add"

    def test_class_hierarchies(self):
        source = '''
class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass
'''
        patterns = extract_python_patterns(source)
        assert len(patterns["classes"]) == 3
        assert patterns["classes"][1]["name"] == "Dog"
        assert patterns["classes"][1]["bases"] == ["Animal"]
        assert patterns["classes"][2]["bases"] == ["Animal"]

    def test_decorator_usage(self):
        source = '''
@pytest.mark.unit
def test_something():
    pass

@app.route("/api")
def handler():
    pass
'''
        patterns = extract_python_patterns(source)
        funcs_with_decorators = [f for f in patterns["functions"] if f.get("decorators")]
        assert len(funcs_with_decorators) == 2

    def test_import_patterns(self):
        source = '''
import os
import json
from pathlib import Path
from typing import Optional
'''
        patterns = extract_python_patterns(source)
        assert len(patterns["imports"]) == 4

    def test_error_handling(self):
        source = '''
def risky():
    try:
        do_something()
    except ValueError as e:
        handle_value_error(e)
    except (TypeError, KeyError):
        handle_other()
'''
        patterns = extract_python_patterns(source)
        assert len(patterns["error_handlers"]) >= 1

    def test_empty_source(self):
        patterns = extract_python_patterns("")
        assert patterns["functions"] == []
        assert patterns["classes"] == []
        assert patterns["imports"] == []
        assert patterns["error_handlers"] == []

    def test_malformed_source(self):
        patterns = extract_python_patterns("def broken(:\n  pass")
        assert patterns["functions"] == []
        assert patterns["classes"] == []

    def test_nested_functions(self):
        source = '''
def outer():
    def inner():
        pass
    return inner()
'''
        patterns = extract_python_patterns(source)
        # Should capture at least the top-level function
        assert len(patterns["functions"]) >= 1

    def test_return_type_captured(self):
        source = '''
def get_name() -> str:
    return "test"
'''
        patterns = extract_python_patterns(source)
        assert patterns["functions"][0]["return_type"] == "str"

    def test_no_return_type(self):
        source = '''
def do_stuff():
    pass
'''
        patterns = extract_python_patterns(source)
        assert patterns["functions"][0]["return_type"] is None


class TestExtractTypescriptPatterns:
    def test_function_declarations(self):
        source = '''
function greet(name: string): string {
    return `Hello, ${name}`;
}

const add = (a: number, b: number): number => a + b;
'''
        patterns = extract_typescript_patterns(source)
        assert len(patterns["functions"]) >= 1

    def test_class_declarations(self):
        source = '''
class UserService extends BaseService {
    private db: Database;
}

class AuthController {
    handle() {}
}
'''
        patterns = extract_typescript_patterns(source)
        assert len(patterns["classes"]) == 2
        assert patterns["classes"][0]["name"] == "UserService"
        assert "BaseService" in patterns["classes"][0].get("extends", "")

    def test_import_statements(self):
        source = '''
import { Router } from 'express';
import axios from 'axios';
import * as path from 'path';
'''
        patterns = extract_typescript_patterns(source)
        assert len(patterns["imports"]) == 3

    def test_empty_source(self):
        patterns = extract_typescript_patterns("")
        assert patterns["functions"] == []
        assert patterns["classes"] == []
        assert patterns["imports"] == []

    def test_method_declarations(self):
        source = '''
class Foo {
    async getData(): Promise<Data> {
        return fetch('/api');
    }
    public setName(name: string): void {
    }
}
'''
        patterns = extract_typescript_patterns(source)
        # Methods are captured via function regex
        assert len(patterns["functions"]) >= 1


class TestFindRepeatedPatterns:
    def test_detects_repeated_function_signatures(self):
        patterns_by_file = {
            "a.py": {
                "functions": [
                    {"name": "handle_error", "params": ["e"],
                     "return_type": None, "decorators": []},
                ],
                "classes": [],
                "imports": [],
                "error_handlers": [],
            },
            "b.py": {
                "functions": [
                    {"name": "handle_error", "params": ["e"],
                     "return_type": None, "decorators": []},
                ],
                "classes": [],
                "imports": [],
                "error_handlers": [],
            },
            "c.py": {
                "functions": [
                    {"name": "handle_error", "params": ["e"],
                     "return_type": None, "decorators": []},
                ],
                "classes": [],
                "imports": [],
                "error_handlers": [],
            },
        }
        detections = find_repeated_patterns(patterns_by_file)
        assert len(detections) >= 1
        assert detections[0].count >= 3

    def test_detects_repeated_class_hierarchy(self):
        patterns_by_file = {
            "a.py": {
                "functions": [],
                "classes": [{"name": "ServiceA", "bases": ["BaseService"]}],
                "imports": [],
                "error_handlers": [],
            },
            "b.py": {
                "functions": [],
                "classes": [{"name": "ServiceB", "bases": ["BaseService"]}],
                "imports": [],
                "error_handlers": [],
            },
            "c.py": {
                "functions": [],
                "classes": [{"name": "ServiceC", "bases": ["BaseService"]}],
                "imports": [],
                "error_handlers": [],
            },
        }
        detections = find_repeated_patterns(patterns_by_file)
        assert len(detections) >= 1

    def test_no_repeats(self):
        patterns_by_file = {
            "a.py": {
                "functions": [{"name": "foo", "params": [], "return_type": None, "decorators": []}],
                "classes": [],
                "imports": [],
                "error_handlers": [],
            },
            "b.py": {
                "functions": [{"name": "bar", "params": [], "return_type": None, "decorators": []}],
                "classes": [],
                "imports": [],
                "error_handlers": [],
            },
        }
        detections = find_repeated_patterns(patterns_by_file)
        assert detections == []

    def test_empty_input(self):
        assert find_repeated_patterns({}) == []

    def test_below_threshold(self):
        """Two occurrences is below the default threshold of 3."""
        patterns_by_file = {
            "a.py": {
                "functions": [{"name": "handle_error", "params": ["e"],
                     "return_type": None, "decorators": []}],
                "classes": [],
                "imports": [],
                "error_handlers": [],
            },
            "b.py": {
                "functions": [{"name": "handle_error", "params": ["e"],
                     "return_type": None, "decorators": []}],
                "classes": [],
                "imports": [],
                "error_handlers": [],
            },
        }
        detections = find_repeated_patterns(patterns_by_file)
        assert detections == []

    def test_repeated_error_handlers(self):
        patterns_by_file = {
            "a.py": {
                "functions": [],
                "classes": [],
                "imports": [],
                "error_handlers": [{"exceptions": ["ValueError"], "handler_type": "except"}],
            },
            "b.py": {
                "functions": [],
                "classes": [],
                "imports": [],
                "error_handlers": [{"exceptions": ["ValueError"], "handler_type": "except"}],
            },
            "c.py": {
                "functions": [],
                "classes": [],
                "imports": [],
                "error_handlers": [{"exceptions": ["ValueError"], "handler_type": "except"}],
            },
            "d.py": {
                "functions": [],
                "classes": [],
                "imports": [],
                "error_handlers": [{"exceptions": ["ValueError"], "handler_type": "except"}],
            },
        }
        detections = find_repeated_patterns(patterns_by_file, error_handler_threshold=4)
        assert len(detections) >= 1
