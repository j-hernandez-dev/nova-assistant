"""Resolve model-supplied relative paths against one captured operation cwd."""

from pathlib import Path

from local_cli.execution_paths import capture_cwd


def resolve_tool_path(path: str, cwd: Path) -> Path:
    candidate = Path(path)
    return (candidate if candidate.is_absolute() else cwd / candidate).resolve()


def relative_path_escapes(path: str, cwd: Path) -> bool:
    candidate = Path(path)
    return not candidate.is_absolute() and not resolve_tool_path(path, cwd).is_relative_to(cwd)
