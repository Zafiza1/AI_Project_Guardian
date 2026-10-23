"""Read-only Git inspection through the Git CLI."""
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.services.process_runner import run_process

# Disable repo-configurable features that could execute programs or write to the repository.
_GIT_SAFETY_ARGS = ["-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", "--no-pager"]


@dataclass
class GitStatus:
    branch: Optional[str] = None
    is_clean: Optional[bool] = None
    changed_files: Optional[int] = None
    changes: list[str] = field(default_factory=list)
    error: Optional[str] = None


class GitError(Exception):
    pass


def _git(args: list[str], repo_path: Path) -> str:
    git = shutil.which("git")
    if git is None:
        raise GitError("Git CLI was not found on PATH")
    result = run_process(
        [git, *_GIT_SAFETY_ARGS, *args],
        cwd=repo_path,
        timeout=settings.git_timeout_seconds,
        max_output_bytes=settings.max_output_bytes,
    )
    if result.timed_out:
        raise GitError(f"git {args[0]} timed out after {settings.git_timeout_seconds}s")
    if result.exit_code != 0:
        raise GitError(result.output.strip() or f"git {args[0]} failed with exit code {result.exit_code}")
    return result.output


def check_repository(repo_path: Path) -> Optional[str]:
    """Return None when repo_path is the top level of a Git work tree, otherwise an error message."""
    try:
        toplevel = _git(["rev-parse", "--show-toplevel"], repo_path).strip()
    except GitError as exc:
        if "not a git repository" in str(exc).lower():
            return "Path is not a Git repository"
        return f"Git could not read the repository: {exc}"
    if os.path.normcase(str(Path(toplevel).resolve())) != os.path.normcase(str(repo_path)):
        return f"Path is inside a repository but is not its root ({toplevel})"
    return None


def _parse_branch(header: str) -> Optional[str]:
    # Examples: "## main...origin/main [ahead 1]", "## No commits yet on main", "## HEAD (no branch)"
    branch = header.removeprefix("## ").strip()
    for prefix in ("No commits yet on ", "Initial commit on "):
        if branch.startswith(prefix):
            return branch.removeprefix(prefix)
    if branch.startswith("HEAD (no branch)"):
        return "HEAD (detached)"
    return branch.split("...", 1)[0].split(" ", 1)[0] or None


def get_status(repo_path: Path) -> GitStatus:
    try:
        output = _git(["status", "--porcelain=v1", "--branch", "--untracked-files=normal"], repo_path)
    except GitError as exc:
        return GitStatus(error=str(exc))
    lines = [line for line in output.splitlines() if line.strip()]
    branch = None
    if lines and lines[0].startswith("## "):
        branch = _parse_branch(lines.pop(0))
    return GitStatus(branch=branch, is_clean=len(lines) == 0, changed_files=len(lines), changes=lines)
