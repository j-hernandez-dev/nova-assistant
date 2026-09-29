"""Git availability is independent of command-shell availability."""

from __future__ import annotations

import os
import subprocess
from typing import Mapping
from enum import Enum


class GitCapability(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE_NOT_REPOSITORY = "AVAILABLE_NOT_REPOSITORY"
    AVAILABLE_REPOSITORY = "AVAILABLE_REPOSITORY"


def detect_git_capability(cwd: str | None = None,
                          environment: Mapping[str, str] | None = None) -> GitCapability:
    directory = cwd or os.getcwd()
    env_kwargs = {} if environment is None else {"env": dict(environment)}
    try:
        version = subprocess.run(
            ["git", "--version"], cwd=directory, capture_output=True,
            text=True, timeout=5,
            **env_kwargs,
        )
        if version.returncode != 0:
            return GitCapability.UNAVAILABLE
        repo = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=directory,
            capture_output=True, text=True, timeout=5,
            **env_kwargs,
        )
    except (OSError, subprocess.TimeoutExpired):
        return GitCapability.UNAVAILABLE
    if repo.returncode == 0 and repo.stdout.strip() == "true":
        return GitCapability.AVAILABLE_REPOSITORY
    return GitCapability.AVAILABLE_NOT_REPOSITORY
