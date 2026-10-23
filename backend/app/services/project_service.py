import os
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import HealthCheck, Project
from app.models.project import ProjectCreate
from app.services import git_service
from app.services.health_check_service import FINISHED_FAILURE_STATUSES, RUNNING
from app.services.path_policy import resolve_repository_path


class ProjectValidationError(ValueError):
    pass


class DuplicateProjectError(ValueError):
    pass


def create_project(db: Session, data: ProjectCreate) -> Project:
    try:
        repo_path = resolve_repository_path(data.repository_path)
    except ValueError as exc:
        raise ProjectValidationError(str(exc))

    repo_error = git_service.check_repository(repo_path)
    if repo_error:
        raise ProjectValidationError(repo_error)

    stored_path = str(repo_path)
    key = os.path.normcase(stored_path)
    existing = next((p for p in db.query(Project).all() if os.path.normcase(p.repository_path) == key), None)
    if existing:
        raise DuplicateProjectError(f"This repository is already registered as '{existing.display_name}'")

    project = Project(display_name=data.display_name, repository_path=stored_path, check_command=data.check_command)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session) -> list[Project]:
    return db.query(Project).order_by(Project.display_name).all()


def get_project(db: Session, project_id: int) -> Optional[Project]:
    return db.get(Project, project_id)


def delete_project(db: Session, project_id: int) -> bool:
    """Removes the project from Guardian's database only; the repository on disk is untouched."""
    project = db.get(Project, project_id)
    if not project:
        return False
    db.delete(project)
    db.commit()
    return True


def list_health_checks(db: Session, project_id: int, limit: int = 50) -> list[HealthCheck]:
    return (
        db.query(HealthCheck)
        .filter(HealthCheck.project_id == project_id)
        .order_by(HealthCheck.timestamp.desc(), HealthCheck.id.desc())
        .limit(limit)
        .all()
    )


def get_health_check(db: Session, check_id: int) -> Optional[HealthCheck]:
    return db.get(HealthCheck, check_id)


def latest_checks_by_project(db: Session) -> dict[int, HealthCheck]:
    latest_ids = db.query(func.max(HealthCheck.id)).group_by(HealthCheck.project_id).subquery()
    checks = db.query(HealthCheck).filter(HealthCheck.id.in_(latest_ids.select())).all()
    return {c.project_id: c for c in checks}


def dashboard_summary(db: Session) -> dict:
    latest = latest_checks_by_project(db)
    projects = list_projects(db)
    recent_failures = (
        db.query(HealthCheck)
        .filter(HealthCheck.status.in_(FINISHED_FAILURE_STATUSES))
        .order_by(HealthCheck.timestamp.desc(), HealthCheck.id.desc())
        .limit(10)
        .all()
    )
    names = {p.id: p.display_name for p in projects}
    return {
        "project_count": len(projects),
        "check_count": db.query(func.count(HealthCheck.id)).filter(HealthCheck.status != RUNNING).scalar() or 0,
        "failed_check_count": db.query(func.count(HealthCheck.id))
        .filter(HealthCheck.status.in_(FINISHED_FAILURE_STATUSES))
        .scalar()
        or 0,
        "failing_project_count": sum(1 for c in latest.values() if c.status in FINISHED_FAILURE_STATUSES),
        "latest_checks": [
            {"project_id": p.id, "project_name": p.display_name, "check": latest.get(p.id)} for p in projects
        ],
        "recent_failures": [
            {"project_id": c.project_id, "project_name": names.get(c.project_id, "?"), "check": c}
            for c in recent_failures
        ],
    }
