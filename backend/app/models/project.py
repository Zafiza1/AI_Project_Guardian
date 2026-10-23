from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.services.check_commands import CHECK_COMMANDS

CheckStatus = Literal["running", "success", "failed", "timeout", "error"]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., min_length=1, max_length=255)
    repository_path: str = Field(..., min_length=1, max_length=1024)
    check_command: Optional[str] = Field(None, description="ID from GET /api/check-commands, or null")

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Display name must not be blank")
        return v

    @field_validator("check_command")
    @classmethod
    def _known_command(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        if v not in CHECK_COMMANDS:
            raise ValueError(f"Unknown check command. Allowed: {', '.join(CHECK_COMMANDS)}")
        return v


class HealthCheckResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    status: CheckStatus
    branch: Optional[str] = None
    is_clean: Optional[bool] = None
    changed_files: Optional[int] = None
    check_command: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: float
    output: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime

    @field_serializer("timestamp")
    def _ser_ts(self, v: datetime) -> str:
        return _as_utc(v).isoformat()


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    repository_path: str
    check_command: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    latest_check: Optional[HealthCheckResult] = None

    @field_serializer("created_at", "updated_at")
    def _ser_ts(self, v: datetime) -> str:
        return _as_utc(v).isoformat()


class CheckCommandInfo(BaseModel):
    id: str
    label: str
    description: str
    argv: list[str]


class ProjectCheck(BaseModel):
    project_id: int
    project_name: str
    check: Optional[HealthCheckResult] = None


class DashboardSummary(BaseModel):
    project_count: int
    check_count: int
    failed_check_count: int
    failing_project_count: int
    latest_checks: list[ProjectCheck]
    recent_failures: list[ProjectCheck]


class SettingsInfo(BaseModel):
    read_only: bool
    allowed_roots: list[str]
    command_timeout_seconds: int
    max_output_bytes: int
    max_concurrent_checks: int
