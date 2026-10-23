from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.project import HealthCheckResult, ProjectCreate, ProjectResponse
from app.services import project_service
from app.services.health_check_service import CheckAlreadyRunningError, start_health_check

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_project_or_404(db: Session, project_id: int):
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _to_response(project, latest) -> ProjectResponse:
    response = ProjectResponse.model_validate(project)
    response.latest_check = HealthCheckResult.model_validate(latest) if latest else None
    return response


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    try:
        project = project_service.create_project(db, data)
    except project_service.DuplicateProjectError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except project_service.ProjectValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_response(project, None)


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    latest = project_service.latest_checks_by_project(db)
    return [_to_response(p, latest.get(p.id)) for p in project_service.list_projects(db)]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    return _to_response(project, project_service.latest_checks_by_project(db).get(project.id))


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    if not project_service.delete_project(db, project_id):
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/health-check", response_model=HealthCheckResult, status_code=202)
def trigger_health_check(project_id: int, db: Session = Depends(get_db)):
    """Starts a check in the background and returns it with status 'running'."""
    project = _get_project_or_404(db, project_id)
    try:
        return start_health_check(db, project)
    except CheckAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{project_id}/health-checks", response_model=list[HealthCheckResult])
def list_health_checks(
    project_id: int, limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)
):
    _get_project_or_404(db, project_id)
    return project_service.list_health_checks(db, project_id, limit)
