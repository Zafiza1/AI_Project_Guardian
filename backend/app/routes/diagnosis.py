from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.diagnosis import DiagnosisRequest, DiagnosisResponse
from app.services.diagnosis_service import (
    DiagnosisAlreadyRunningError,
    InvalidHealthCheckError,
    get_diagnosis,
    list_diagnoses,
    start_diagnosis,
)

router = APIRouter(prefix="/api/diagnoses", tags=["diagnoses"])


@router.post("", response_model=DiagnosisResponse, status_code=202)
def request_diagnosis(data: DiagnosisRequest, db: Session = Depends(get_db)):
    """Request an AI diagnosis for a failed health check."""
    try:
        diagnosis = start_diagnosis(db, data.health_check_id)
        return DiagnosisResponse.model_validate(diagnosis)
    except InvalidHealthCheckError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DiagnosisAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
def get_diagnosis_by_id(diagnosis_id: int, db: Session = Depends(get_db)):
    """Get a diagnosis by ID."""
    diagnosis = get_diagnosis(db, diagnosis_id)
    if not diagnosis:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    return DiagnosisResponse.model_validate(diagnosis)


@router.get("/health-check/{health_check_id}", response_model=list[DiagnosisResponse])
def list_diagnoses_for_health_check(
    health_check_id: int, limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)
):
    """List all diagnoses for a health check."""
    diagnoses = list_diagnoses(db, health_check_id, limit)
    return [DiagnosisResponse.model_validate(d) for d in diagnoses]
