"""Allowlist of check commands.

API clients may only reference a check by its ID. Each ID maps to a fixed argument array that is
executed without a shell, so no client-supplied text ever reaches the command line.
"""
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class CheckCommand:
    id: str
    label: str
    description: str
    argv: tuple[str, ...]


CHECK_COMMANDS: dict[str, CheckCommand] = {
    c.id: c
    for c in [
        CheckCommand(
            id="pytest",
            label="pytest",
            description="Run Python tests with pytest (uses the repo's .venv/venv if present).",
            argv=("{python}", "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"),
        ),
        CheckCommand(
            id="npm-test",
            label="npm test",
            description="Run the package.json 'test' script (CI=true, no watch mode).",
            argv=("npm", "test", "--silent"),
        ),
        CheckCommand(
            id="git-fsck",
            label="git fsck",
            description="Verify Git object database integrity (read-only).",
            argv=("git", "fsck", "--no-progress", "--connectivity-only"),
        ),
    ]
}


def get_check_command(command_id: Optional[str]) -> Optional[CheckCommand]:
    if not command_id:
        return None
    return CHECK_COMMANDS.get(command_id)


def _repo_python(repo_path: Path) -> str:
    for venv in (".venv", "venv"):
        for rel in ("Scripts/python.exe", "bin/python"):
            candidate = repo_path / venv / rel
            if candidate.is_file():
                return str(candidate)
    return shutil.which("python") or shutil.which("python3") or sys.executable


def resolve_argv(command: CheckCommand, repo_path: Path) -> list[str]:
    """Turn the allowlisted template into a concrete argv, resolving executables to absolute paths."""
    argv = list(command.argv)
    if argv[0] == "{python}":
        argv[0] = _repo_python(repo_path)
    else:
        # shutil.which resolves Windows wrappers such as npm.cmd.
        resolved = shutil.which(argv[0])
        if resolved is None:
            raise FileNotFoundError(f"Executable '{argv[0]}' was not found on PATH")
        argv[0] = resolved
    return argv
