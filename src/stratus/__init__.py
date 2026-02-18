"""stratus: Open-source framework for Claude Code sessions."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("stratus")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
