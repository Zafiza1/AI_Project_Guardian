import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Must be configured before the app (and its database engine) is imported.
_SESSION_DIR = Path(tempfile.mkdtemp(prefix="guardian-tests-"))
os.environ["GUARDIAN_DATABASE_URL"] = f"sqlite:///{(_SESSION_DIR / 'test.db').as_posix()}"
os.environ["GUARDIAN_ALLOWED_ROOTS"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.database.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import check_commands  # noqa: E402

GIT = shutil.which("git")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        [GIT, "-c", "user.name=Guardian Test", "-c", "user.email=test@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def allowed_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "allowed"
    root.mkdir()
    monkeypatch.setattr(settings, "allowed_roots", [str(root)])
    return root


@pytest.fixture
def make_repo(allowed_root):
    def _make(name: str = "repo", files: dict[str, str] | None = None, parent: Path | None = None) -> Path:
        repo = (parent or allowed_root) / name
        repo.mkdir(parents=True)
        _git(repo, "init", "-q", "-b", "main")
        for rel, content in (files or {"README.md": "hello\n"}).items():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(content, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "init")
        return repo

    return _make


@pytest.fixture
def use_test_python(monkeypatch):
    """Run '{python}' checks with the interpreter running the tests (which has pytest installed)."""
    monkeypatch.setattr(check_commands, "_repo_python", lambda _repo: sys.executable)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
