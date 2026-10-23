"""Restricts repository paths to explicitly permitted root directories."""
import os
from pathlib import Path

from app.core.config import settings


class PathNotAllowedError(ValueError):
    pass


def _norm(path: Path) -> str:
    return os.path.normcase(str(path))


def allowed_roots() -> list[Path]:
    roots = []
    for root in settings.allowed_roots:
        try:
            roots.append(Path(root).expanduser().resolve())
        except OSError:
            continue
    return roots


def is_within_allowed_roots(path: Path) -> bool:
    target = _norm(path)
    for root in allowed_roots():
        root_str = _norm(root)
        if target == root_str or target.startswith(root_str.rstrip("\\/") + os.sep):
            return True
    return False


def resolve_repository_path(raw_path: str) -> Path:
    """Validate a client-supplied path and return its canonical absolute form.

    Raises PathNotAllowedError with a user-facing message when the path is rejected.
    """
    raw_path = raw_path.strip()
    if not raw_path:
        raise PathNotAllowedError("Repository path is required")
    if "\x00" in raw_path:
        raise PathNotAllowedError("Repository path contains invalid characters")

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        raise PathNotAllowedError("Repository path must be an absolute path")

    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise PathNotAllowedError("Repository path does not exist")
    if not resolved.is_dir():
        raise PathNotAllowedError("Repository path is not a directory")

    if not settings.allowed_roots:
        raise PathNotAllowedError(
            "No permitted directories are configured. Set GUARDIAN_ALLOWED_ROOTS in backend/.env"
        )
    # Checked after resolve() so symlinks/junctions cannot escape the permitted roots.
    if not is_within_allowed_roots(resolved):
        raise PathNotAllowedError("Repository path is outside the permitted directories")
    return resolved
