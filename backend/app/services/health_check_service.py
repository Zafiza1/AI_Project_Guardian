"""Runs a project's health check: path policy -> Git repository -> Git status -> allowlisted command."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import HealthCheck, Project, SessionLocal
from app.services import git_service
from app.services.check_commands import get_check_command, resolve_argv
from app.services.path_policy import PathNotAllowedError, resolve_repository_path
from app.services.process_runner import run_process
from app.services.sanitizer import sanitize_output

MAX_LISTED_CHANGES = 50
RUNNING = "running"
FINISHED_FAILURE_STATUSES = ("failed", "timeout", "error")


class CheckAlreadyRunningError(Exception):
    pass


_running: set[int] = set()
_running_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _running_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_checks, thread_name_prefix="health-check")
        return _executor


def _execute(project: Project, log: list[str]) -> dict:
    """Run every step, appending human-readable lines to `log`. Returns the HealthCheck fields."""
    result = {
        "status": "success",
        "branch": None,
        "is_clean": None,
        "changed_files": None,
        "check_command": project.check_command,
        "exit_code": None,
        "error": None,
    }

    def fail(status: str, message: str) -> dict:
        result["status"] = status
        result["error"] = message
        log.append(f"ERROR: {message}")
        return result

    # 1. Path policy is re-validated on every run (the config or filesystem may have changed).
    log.append("[1/4] Repository path")
    try:
        repo_path = resolve_repository_path(project.repository_path)
    except PathNotAllowedError as exc:
        return fail("error", str(exc))
    log.append(f"  OK  {repo_path}")

    # 2. Git repository
    log.append("[2/4] Git repository")
    repo_error = git_service.check_repository(repo_path)
    if repo_error:
        return fail("error", repo_error)
    log.append("  OK  valid Git work tree")

    # 3. Git status
    log.append("[3/4] Git status")
    status = git_service.get_status(repo_path)
    if status.error:
        return fail("error", f"git status failed: {status.error}")
    result.update(branch=status.branch, is_clean=status.is_clean, changed_files=status.changed_files)
    log.append(f"  Branch: {status.branch or 'unknown'}")
    if status.is_clean:
        log.append("  Working tree: clean")
    else:
        log.append(f"  Working tree: {status.changed_files} changed/untracked file(s)")
        log.extend(f"    {line}" for line in status.changes[:MAX_LISTED_CHANGES])
        if len(status.changes) > MAX_LISTED_CHANGES:
            log.append(f"    ... and {len(status.changes) - MAX_LISTED_CHANGES} more")

    # 4. Allowlisted check command
    log.append("[4/4] Check command")
    if not project.check_command:
        log.append("  SKIPPED  no check command configured")
        return result
    command = get_check_command(project.check_command)
    if command is None:
        return fail("error", f"Check command '{project.check_command}' is not in the allowlist")
    try:
        argv = resolve_argv(command, repo_path)
    except FileNotFoundError as exc:
        return fail("error", str(exc))

    timeout = settings.command_timeout_seconds
    log.append(f"  Running: {command.label} (timeout {timeout}s)")
    try:
        proc = run_process(argv, repo_path, timeout, settings.max_output_bytes)
    except OSError as exc:
        return fail("error", f"Could not start '{command.label}': {exc}")

    result["exit_code"] = proc.exit_code
    log.append("----- command output -----")
    log.append(proc.output.rstrip() or "(no output)")
    log.append("--------------------------")
    if proc.timed_out:
        return fail("timeout", f"'{command.label}' timed out after {timeout}s and was stopped")
    if proc.exit_code != 0:
        return fail("failed", f"'{command.label}' exited with code {proc.exit_code}")
    log.append(f"  OK  '{command.label}' exited with code 0")
    return result


def _apply_result(health_check: HealthCheck, result: dict, log: list[str], duration_ms: float) -> None:
    result["error"] = sanitize_output(result["error"]) if result.get("error") else None
    for key, value in result.items():
        setattr(health_check, key, value)
    health_check.duration_ms = duration_ms
    health_check.output = sanitize_output("\n".join(log))


def _run_in_background(check_id: int, project_id: int) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        health_check = db.get(HealthCheck, check_id)
        if project is None or health_check is None:
            return  # Removed before the worker picked it up.

        log: list[str] = []
        start = time.perf_counter()
        try:
            result = _execute(project, log)
        except Exception as exc:  # Never let an unexpected failure go unrecorded.
            message = f"Unexpected error: {exc}"
            log.append(f"ERROR: {message}")
            result = {"status": "error", "error": message}
        _apply_result(health_check, result, log, (time.perf_counter() - start) * 1000)
        try:
            db.commit()
        except Exception:
            # The project (and its checks) may have been removed while the check was running.
            db.rollback()
    finally:
        db.close()
        with _running_lock:
            _running.discard(project_id)


def start_health_check(db: Session, project: Project) -> HealthCheck:
    """Record a 'running' check and execute it on the worker pool. Poll it via GET /api/health-checks/{id}."""
    with _running_lock:
        if project.id in _running:
            raise CheckAlreadyRunningError("A health check is already running for this project")
        _running.add(project.id)
    try:
        health_check = HealthCheck(
            project_id=project.id,
            status=RUNNING,
            check_command=project.check_command,
            duration_ms=0,
            output="Health check queued...",
        )
        db.add(health_check)
        db.commit()
        db.refresh(health_check)
        _get_executor().submit(_run_in_background, health_check.id, project.id)
        return health_check
    except Exception:
        with _running_lock:
            _running.discard(project.id)
        raise


def mark_interrupted_checks(db: Session) -> int:
    """Checks left 'running' by a previous backend process can never finish; record them as errors."""
    stale = db.query(HealthCheck).filter(HealthCheck.status == RUNNING).all()
    for check in stale:
        check.status = "error"
        check.error = "Interrupted: the backend stopped before this check finished"
        check.output = (check.output or "") + "\nERROR: interrupted by backend restart"
    db.commit()
    return len(stale)


def shutdown() -> None:
    global _executor
    with _running_lock:
        executor, _executor = _executor, None
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)
