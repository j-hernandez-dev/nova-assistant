"""Filesystem boundary shared by legacy adapters during the cwd migration."""

from pathlib import Path


def capture_cwd(cwd: str | Path | None = None) -> Path:
    """Resolve and validate the entry cwd once, before concurrent work starts."""
    path = Path.cwd() if cwd is None else Path(cwd)
    resolved = path.resolve()
    if not resolved.is_dir():
        raise ValueError(f"working directory is not a directory: {path}")
    return resolved
