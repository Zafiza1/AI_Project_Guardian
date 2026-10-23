import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.database import HealthCheck, Project
from app.services import check_commands
from app.services.check_commands import CheckCommand


def _start_check(client, project_id):
    res = client.post(f"/api/projects/{project_id}/health-check")
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "running"
    return res.json()


def _wait_for(client, check_id, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check = client.get(f"/api/health-checks/{check_id}").json()
        if check["status"] != "running":
            return check
        time.sleep(0.05)
    raise AssertionError(f"health check {check_id} did not finish within {timeout}s")


def _run_check(client, project_id):
    return _wait_for(client, _start_check(client, project_id)["id"])


def _register(client, path, name="Demo", check_command=None):
    return client.post(
        "/api/projects",
        json={"display_name": name, "repository_path": str(path), "check_command": check_command},
    )


def test_register_valid_repository(client, make_repo):
    repo = make_repo()
    res = _register(client, repo)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["display_name"] == "Demo"
    assert body["repository_path"] == str(repo.resolve())
    assert body["created_at"].endswith("+00:00")

    listed = client.get("/api/projects").json()
    assert [p["id"] for p in listed] == [body["id"]]
    assert client.get(f"/api/projects/{body['id']}").status_code == 200


def test_register_rejects_nonexistent_path(client, allowed_root):
    res = _register(client, allowed_root / "missing")
    assert res.status_code == 400
    assert "does not exist" in res.json()["detail"]


def test_register_rejects_relative_path(client, allowed_root):
    res = _register(client, "some/relative/path")
    assert res.status_code == 400
    assert "absolute" in res.json()["detail"]


def test_register_rejects_non_git_directory(client, allowed_root):
    plain = allowed_root / "plain"
    plain.mkdir()
    res = _register(client, plain)
    assert res.status_code == 400
    assert "not a Git repository" in res.json()["detail"]


def test_register_rejects_path_outside_allowed_roots(client, make_repo, tmp_path):
    outside = make_repo("outside", parent=tmp_path)
    res = _register(client, outside)
    assert res.status_code == 400
    assert "outside the permitted" in res.json()["detail"]


def test_register_rejects_traversal_out_of_allowed_root(client, make_repo, allowed_root, tmp_path):
    make_repo("escaped", parent=tmp_path)
    res = _register(client, allowed_root / ".." / "escaped")
    assert res.status_code == 400
    assert "outside the permitted" in res.json()["detail"]


def test_register_requires_configured_roots(client, make_repo, monkeypatch):
    repo = make_repo()
    monkeypatch.setattr(settings, "allowed_roots", [])
    res = _register(client, repo)
    assert res.status_code == 400
    assert "GUARDIAN_ALLOWED_ROOTS" in res.json()["detail"]


def test_register_rejects_subdirectory_of_repo(client, make_repo):
    repo = make_repo(files={"src/app.py": "x = 1\n"})
    res = _register(client, repo / "src")
    assert res.status_code == 400
    assert "not its root" in res.json()["detail"]


def test_register_rejects_duplicate(client, make_repo):
    repo = make_repo()
    assert _register(client, repo).status_code == 201
    res = _register(client, repo, name="Again")
    assert res.status_code == 409


def test_register_rejects_arbitrary_command(client, make_repo):
    repo = make_repo()
    for command in ["rm -rf /", "python -c 'print(1)'", "git push", "pytest; del *"]:
        res = _register(client, repo, check_command=command)
        assert res.status_code == 422, command


def test_register_rejects_unknown_fields(client, make_repo):
    repo = make_repo()
    res = client.post(
        "/api/projects",
        json={"display_name": "x", "repository_path": str(repo), "test_command": "rm -rf /"},
    )
    assert res.status_code == 422


def test_health_check_reports_branch_and_clean_tree(client, make_repo):
    project = _register(client, make_repo()).json()
    check = _run_check(client, project["id"])
    assert check["status"] == "success"
    assert check["branch"] == "main"
    assert check["is_clean"] is True
    assert check["changed_files"] == 0
    assert "no check command configured" in check["output"]


def test_health_check_detects_modified_tree(client, make_repo):
    repo = make_repo()
    project = _register(client, repo).json()
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")
    check = _run_check(client, project["id"])
    assert check["status"] == "success"
    assert check["is_clean"] is False
    assert check["changed_files"] == 2


def test_health_check_runs_passing_pytest(client, make_repo, use_test_python):
    repo = make_repo(files={"test_ok.py": "def test_ok():\n    assert True\n"})
    project = _register(client, repo, check_command="pytest").json()
    check = _run_check(client, project["id"])
    assert check["status"] == "success", check["output"]
    assert check["exit_code"] == 0
    assert "1 passed" in check["output"]
    # Guardian is read-only: running the check must not dirty the working tree.
    assert not (repo / ".pytest_cache").exists()


def test_health_check_records_failing_pytest(client, make_repo, use_test_python):
    repo = make_repo(files={"test_bad.py": "def test_bad():\n    assert 1 == 2\n"})
    project = _register(client, repo, check_command="pytest").json()
    check = _run_check(client, project["id"])
    assert check["status"] == "failed"
    assert check["exit_code"] == 1
    assert "exited with code 1" in check["error"]
    assert "1 failed" in check["output"]


def test_health_check_timeout_is_recorded(client, make_repo, monkeypatch, use_test_python):
    monkeypatch.setitem(
        check_commands.CHECK_COMMANDS,
        "sleep-test",
        CheckCommand("sleep-test", "sleep", "test only", ("{python}", "-c", "import time; time.sleep(30)")),
    )
    monkeypatch.setattr(settings, "command_timeout_seconds", 1)
    project = _register(client, make_repo(), check_command="sleep-test").json()
    check = _run_check(client, project["id"])
    assert check["status"] == "timeout"
    assert check["exit_code"] is None
    assert check["duration_ms"] < 15_000
    assert "timed out" in check["error"]


def test_health_check_handles_deleted_repository(client, make_repo):
    import shutil
    import stat

    repo = make_repo()
    project = _register(client, repo).json()

    def _on_error(func, path, _exc):
        import os
        os.chmod(path, stat.S_IWRITE)
        func(path)

    shutil.rmtree(repo, onexc=_on_error)
    check = _run_check(client, project["id"])
    assert check["status"] == "error"
    assert "does not exist" in check["error"]


def test_health_check_rechecks_allowed_roots(client, make_repo, monkeypatch, tmp_path):
    project = _register(client, make_repo()).json()
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path / "elsewhere")])
    check = _run_check(client, project["id"])
    assert check["status"] == "error"
    assert "outside the permitted" in check["error"]


def test_health_check_unknown_project_404(client):
    assert client.post("/api/projects/999/health-check").status_code == 404
    assert client.get("/api/projects/999/health-checks").status_code == 404
    assert client.get("/api/health-checks/999").status_code == 404


def test_history_dashboard_and_delete(client, make_repo, use_test_python):
    good = _register(client, make_repo("good"), name="Good").json()
    bad_repo = make_repo("bad", files={"test_bad.py": "def test_bad():\n    assert False\n"})
    bad = _register(client, bad_repo, name="Bad", check_command="pytest").json()

    _run_check(client, good["id"])
    _run_check(client, good["id"])
    _run_check(client, bad["id"])

    history = client.get(f"/api/projects/{good['id']}/health-checks").json()
    assert len(history) == 2
    assert history[0]["id"] > history[1]["id"]

    summary = client.get("/api/dashboard").json()
    assert summary["project_count"] == 2
    assert summary["check_count"] == 3
    assert summary["failed_check_count"] == 1
    assert summary["failing_project_count"] == 1
    assert [f["project_name"] for f in summary["recent_failures"]] == ["Bad"]

    projects = {p["display_name"]: p for p in client.get("/api/projects").json()}
    assert projects["Bad"]["latest_check"]["status"] == "failed"
    assert projects["Good"]["latest_check"]["status"] == "success"

    assert client.delete(f"/api/projects/{bad['id']}").status_code == 204
    assert bad_repo.exists(), "deleting a project must never touch the repository"
    assert client.get("/api/dashboard").json()["check_count"] == 2


def test_results_persist_across_engine_restart(client, make_repo):
    project = _register(client, make_repo()).json()
    check = _run_check(client, project["id"])

    # A fresh engine on the same SQLite file simulates a backend restart.
    fresh_engine = create_engine(settings.database_url)
    try:
        with sessionmaker(bind=fresh_engine)() as db:
            assert db.get(Project, project["id"]).display_name == "Demo"
            stored = db.get(HealthCheck, check["id"])
            assert stored.status == "success"
            assert stored.output == check["output"]
    finally:
        fresh_engine.dispose()


def test_meta_endpoints(client, allowed_root):
    commands = client.get("/api/check-commands").json()
    assert {c["id"] for c in commands} >= {"pytest", "npm-test", "git-fsck"}
    info = client.get("/api/settings").json()
    assert info["read_only"] is True
    assert info["allowed_roots"] == [str(allowed_root)]


def _register_sleeper(client, make_repo, monkeypatch, seconds=30):
    monkeypatch.setitem(
        check_commands.CHECK_COMMANDS,
        "sleep-test",
        CheckCommand("sleep-test", "sleep", "test only", ("{python}", "-c", f"import time; time.sleep({seconds})")),
    )
    return _register(client, make_repo(), check_command="sleep-test").json()


def test_health_check_runs_in_background(client, make_repo, monkeypatch, use_test_python):
    monkeypatch.setattr(settings, "command_timeout_seconds", 2)
    project = _register_sleeper(client, make_repo, monkeypatch)

    started = time.monotonic()
    running = _start_check(client, project["id"])
    assert time.monotonic() - started < 1.5, "POST must return before the command finishes"

    # While running: visible as the project's latest check, but not counted as a result yet.
    assert client.get(f"/api/projects/{project['id']}").json()["latest_check"]["status"] == "running"
    summary = client.get("/api/dashboard").json()
    assert summary["check_count"] == 0
    assert summary["failing_project_count"] == 0

    # A second run for the same project is rejected until the first finishes.
    assert client.post(f"/api/projects/{project['id']}/health-check").status_code == 409

    done = _wait_for(client, running["id"])
    assert done["status"] == "timeout"
    _run_check(client, project["id"])


def test_interrupted_checks_are_marked_on_startup(client, make_repo):
    from fastapi.testclient import TestClient

    from app.database.database import SessionLocal
    from app.main import app

    project = _register(client, make_repo()).json()
    with SessionLocal() as db:
        db.add(HealthCheck(project_id=project["id"], status="running", duration_ms=0, output="queued"))
        db.commit()

    with TestClient(app) as restarted:  # runs the startup hook again
        history = restarted.get(f"/api/projects/{project['id']}/health-checks").json()
    assert history[0]["status"] == "error"
    assert "Interrupted" in history[0]["error"]
