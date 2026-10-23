"""Application settings loaded from environment variables and an optional backend/.env file."""
import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, '#' comments. Real env vars take precedence."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _split_roots(value: str) -> list[str]:
    # ';' works on every platform (Windows paths contain ':'), os.pathsep is accepted too.
    parts = value.replace(os.pathsep, ";").split(";")
    return [p.strip() for p in parts if p.strip()]


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    database_url: str
    host: str
    port: int
    allowed_roots: list[str] = field(default_factory=list)
    command_timeout_seconds: int = 120
    git_timeout_seconds: int = 15
    max_output_bytes: int = 64_000
    max_concurrent_checks: int = 2
    cors_origins: list[str] = field(default_factory=list)
    # Guardian never modifies repositories. This flag is informational and not configurable.
    read_only: bool = True
    # AI Diagnosis settings
    ai_provider: str = "ollama"
    ai_model: str = "llama3.2"
    ai_endpoint: str = "http://127.0.0.1:11434"
    ai_timeout_seconds: int = 60
    ai_max_evidence_bytes: int = 100_000


def load_settings() -> Settings:
    _load_dotenv(BACKEND_DIR / ".env")
    default_db = BACKEND_DIR / "data" / "guardian.db"
    return Settings(
        database_url=os.environ.get("GUARDIAN_DATABASE_URL", f"sqlite:///{default_db.as_posix()}"),
        host=os.environ.get("GUARDIAN_HOST", "127.0.0.1"),
        port=_int_env("GUARDIAN_PORT", 8000),
        allowed_roots=_split_roots(os.environ.get("GUARDIAN_ALLOWED_ROOTS", "")),
        command_timeout_seconds=_int_env("GUARDIAN_COMMAND_TIMEOUT_SECONDS", 120),
        git_timeout_seconds=_int_env("GUARDIAN_GIT_TIMEOUT_SECONDS", 15),
        max_output_bytes=_int_env("GUARDIAN_MAX_OUTPUT_BYTES", 64_000),
        max_concurrent_checks=max(1, _int_env("GUARDIAN_MAX_CONCURRENT_CHECKS", 2)),
        cors_origins=_split_roots(
            os.environ.get("GUARDIAN_CORS_ORIGINS", "http://localhost:5173;http://127.0.0.1:5173")
        ),
        ai_provider=os.environ.get("GUARDIAN_AI_PROVIDER", "ollama"),
        ai_model=os.environ.get("GUARDIAN_AI_MODEL", "llama3.2"),
        ai_endpoint=os.environ.get("GUARDIAN_AI_ENDPOINT", "http://127.0.0.1:11434"),
        ai_timeout_seconds=_int_env("GUARDIAN_AI_TIMEOUT_SECONDS", 60),
        ai_max_evidence_bytes=_int_env("GUARDIAN_AI_MAX_EVIDENCE_BYTES", 100_000),
    )


settings = load_settings()
