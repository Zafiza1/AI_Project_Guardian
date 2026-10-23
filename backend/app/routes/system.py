from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.models.project import CheckCommandInfo, DashboardSummary, HealthCheckResult, SettingsInfo
from app.services import project_service
from app.services.check_commands import CHECK_COMMANDS

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(db: Session = Depends(get_db)):
    return project_service.dashboard_summary(db)


@router.get("/health-checks/{check_id}", response_model=HealthCheckResult)
def get_health_check(check_id: int, db: Session = Depends(get_db)):
    """Single run; poll this after POST /api/projects/{id}/health-check until status != 'running'."""
    check = project_service.get_health_check(db, check_id)
    if not check:
        raise HTTPException(status_code=404, detail="Health check not found")
    return check


@router.get("/check-commands", response_model=list[CheckCommandInfo])
def check_commands():
    return [
        CheckCommandInfo(id=c.id, label=c.label, description=c.description, argv=list(c.argv))
        for c in CHECK_COMMANDS.values()
    ]


@router.get("/settings", response_model=SettingsInfo)
def get_settings():
    return SettingsInfo(
        read_only=settings.read_only,
        allowed_roots=settings.allowed_roots,
        command_timeout_seconds=settings.command_timeout_seconds,
        max_output_bytes=settings.max_output_bytes,
        max_concurrent_checks=settings.max_concurrent_checks,
    )
