import sys

import pytest

from app.services import check_commands, git_service
from app.services.process_runner import run_process, safe_env
from app.services.sanitizer import REDACTED, sanitize_output


def test_run_process_captures_output_and_exit_code(tmp_path):
    result = run_process([sys.executable, "-c", "print('hi'); raise SystemExit(3)"], tmp_path, 10, 10_000)
    assert result.exit_code == 3
    assert "hi" in result.output
    assert not result.timed_out


def test_run_process_timeout_kills_process(tmp_path):
    result = run_process([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, 1, 10_000)
    assert result.timed_out
    assert result.exit_code is None
    assert result.duration_ms < 15_000


def test_run_process_timeout_kills_child_processes(tmp_path):
    # Parent spawns a child that keeps running; both must be stopped and the call must return.
    script = (
        "import subprocess, sys, time;"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
        "time.sleep(60)"
    )
    result = run_process([sys.executable, "-c", script], tmp_path, 2, 10_000)
    assert result.timed_out
    assert result.duration_ms < 20_000


def test_run_process_limits_output_size(tmp_path):
    result = run_process([sys.executable, "-c", "print('x' * 100000); print('END')"], tmp_path, 10, 1_000)
    assert result.truncated
    assert "truncated" in result.output
    assert result.output.rstrip().endswith("END")
    assert len(result.output) < 1_200


def test_run_process_rejects_string_command(tmp_path):
    with pytest.raises(ValueError):
        run_process("echo hi", tmp_path, 5, 1000)  # type: ignore[arg-type]


def test_safe_env_drops_secrets(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_supersecretvalue1234567890")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "abc123secret")
    env = safe_env()
    assert "GITHUB_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env["CI"] == "true"
    assert env["GIT_OPTIONAL_LOCKS"] == "0"


def test_child_process_does_not_see_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_TOKEN", "leak-me-please-123")
    code = "import os; print(os.environ.get('MY_API_TOKEN', 'absent'))"
    result = run_process([sys.executable, "-c", code], tmp_path, 10, 1000)
    assert result.output.strip() == "absent"


@pytest.mark.parametrize(
    "raw",
    [
        "remote: https://alice:hunter2@github.com/org/repo.git",
        "token ghp_abcdefghijklmnopqrstuvwxyz123456",
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwx",
        'password: "s3cr3t-value"',
        "Authorization: Bearer abcdef1234567890",
        "AKIAABCDEFGHIJKLMNOP",
    ],
)
def test_sanitizer_redacts_secrets(raw):
    cleaned = sanitize_output(raw)
    assert REDACTED in cleaned
    for secret in ["hunter2", "ghp_abc", "sk-abc", "s3cr3t", "abcdef1234567890", "AKIAABCD"]:
        assert secret not in cleaned


def test_sanitizer_redacts_sensitive_env_values(monkeypatch):
    monkeypatch.setenv("DEPLOY_SECRET", "zz-very-private-zz")
    assert "zz-very-private-zz" not in sanitize_output("value was zz-very-private-zz here")


def test_sanitizer_keeps_normal_output_and_strips_ansi():
    assert sanitize_output("\x1b[32m3 passed\x1b[0m in 0.1s") == "3 passed in 0.1s"


def test_allowlist_argv_has_no_shell():
    for command in check_commands.CHECK_COMMANDS.values():
        assert isinstance(command.argv, tuple)
        assert all(";" not in a and "&" not in a and "|" not in a for a in command.argv)


def test_git_status_on_non_repo(tmp_path):
    assert git_service.check_repository(tmp_path) is not None


def test_git_branch_parsing():
    assert git_service._parse_branch("## main...origin/main [ahead 1]") == "main"
    assert git_service._parse_branch("## No commits yet on dev") == "dev"
    assert git_service._parse_branch("## HEAD (no branch)") == "HEAD (detached)"
    assert git_service._parse_branch("## feature/x") == "feature/x"
