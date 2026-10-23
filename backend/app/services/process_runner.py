"""Safe subprocess execution: argv arrays only, no shell, minimal env, timeouts, output caps."""
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Only these variables are inherited by child processes, so secrets in the
# Guardian's own environment (tokens, API keys, cloud credentials) never leak into checks.
_INHERITED_ENV = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "OS",
    "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "PROGRAMW6432", "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL", "LC_CTYPE",
    "USER", "USERNAME", "LOGNAME", "SHELL", "NVM_HOME", "NVM_SYMLINK",
}

_FIXED_ENV = {
    "CI": "true",
    "NO_COLOR": "1",
    "FORCE_COLOR": "0",
    "GIT_TERMINAL_PROMPT": "0",
    # Prevents `git status` from refreshing (writing) the index: Guardian stays read-only.
    "GIT_OPTIONAL_LOCKS": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
}


@dataclass
class ProcessResult:
    exit_code: Optional[int]
    output: str
    timed_out: bool
    truncated: bool
    duration_ms: float


def safe_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() in _INHERITED_ENV}
    env.update(_FIXED_ENV)
    return env


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            # Kills npm/node/python grandchildren too; proc.kill() alone would orphan them.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def run_process(argv: list[str], cwd: Path, timeout: float, max_output_bytes: int) -> ProcessResult:
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ValueError("argv must be a non-empty list of strings")

    popen_kwargs: dict = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        popen_kwargs["start_new_session"] = True

    start = time.perf_counter()
    # Output goes to a temp file instead of a pipe: no pipe-buffer deadlocks and memory stays bounded.
    with tempfile.TemporaryFile() as out:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            env=safe_env(),
            shell=False,
            **popen_kwargs,
        )
        timed_out = False
        try:
            exit_code: Optional[int] = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            exit_code = None
        duration_ms = (time.perf_counter() - start) * 1000

        out.seek(0, os.SEEK_END)
        size = out.tell()
        # Keep the tail: test runners print their summary last.
        offset = max(0, size - max_output_bytes)
        out.seek(offset)
        data = out.read(max_output_bytes)

    text = data.decode("utf-8", errors="replace")
    truncated = offset > 0
    if truncated:
        text = f"[... {offset} bytes of earlier output truncated ...]\n" + text
    return ProcessResult(
        exit_code=exit_code, output=text, timed_out=timed_out, truncated=truncated, duration_ms=duration_ms
    )
