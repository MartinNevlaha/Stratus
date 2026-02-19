# Re-exports all tests from the canonical test module.
# This file exists to satisfy the TDD enforcer which maps
# src/stratus/self_debug/analyzer.py -> tests/test_analyzer.py.
# All actual tests live in tests/test_self_debug_analyzer.py.
from tests.test_self_debug_analyzer import *  # noqa: F401, F403
