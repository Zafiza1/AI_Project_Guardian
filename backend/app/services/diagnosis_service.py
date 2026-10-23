"""Service for generating and managing AI diagnoses of failed health checks."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import Diagnosis, HealthCheck, Project, SessionLocal
from app.models.diagnosis import DiagnosisFinding, DiagnosisStatus
from app.services.ai_provider import (
    InvalidResponseError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    get_provider,
)
from app.services.evidence_collector import EvidenceCollector
from app.services.health_check_service import FINISHED_FAILURE_STATUSES


class DiagnosisAlreadyRunningError(Exception):
    """Raised when a diagnosis is already in progress for a health check."""
    pass


class InvalidHealthCheckError(Exception):
    """Raised when a health check is not eligible for diagnosis."""
    pass


_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="diagnosis")
        return _executor


def start_diagnosis(db: Session, health_check_id: int) -> Diagnosis:
    """Start a diagnosis for a health check. Returns a Diagnosis with status 'pending'."""
    health_check = db.get(HealthCheck, health_check_id)
    if not health_check:
        raise InvalidHealthCheckError(f"Health check {health_check_id} not found")

    # Only diagnose failed checks
    if health_check.status not in FINISHED_FAILURE_STATUSES:
        raise InvalidHealthCheckError(
            f"Health check {health_check_id} has status '{health_check.status}'; "
            f"only {FINISHED_FAILURE_STATUSES} can be diagnosed"
        )

    # Check for existing pending diagnosis
    existing = (
        db.query(Diagnosis)
        .filter(Diagnosis.health_check_id == health_check_id, Diagnosis.status == "pending")
        .first()
    )
    if existing:
        raise DiagnosisAlreadyRunningError(f"A diagnosis is already in progress for health check {health_check_id}")

    # Create diagnosis record
    diagnosis = Diagnosis(
        health_check_id=health_check_id,
        status="pending",
        provider=settings.ai_provider,
        model=settings.ai_model,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)

    # Run diagnosis in background
    _get_executor().submit(_run_diagnosis, diagnosis.id, health_check_id)

    return diagnosis


def _run_diagnosis(diagnosis_id: int, health_check_id: int) -> None:
    """Background task to execute the diagnosis."""
    # Run the async function in a new event loop
    asyncio.run(_run_diagnosis_async(diagnosis_id, health_check_id))


async def _run_diagnosis_async(diagnosis_id: int, health_check_id: int) -> None:
    """Async task to execute the diagnosis."""
    db = SessionLocal()
    try:
        diagnosis = db.get(Diagnosis, diagnosis_id)
        health_check = db.get(HealthCheck, health_check_id)
        project = db.get(Project, health_check.project_id) if health_check else None

        if not diagnosis or not health_check or not project:
            # Record was deleted while we were waiting
            return

        try:
            # Collect evidence
            collector = EvidenceCollector()
            evidence = collector.collect(health_check, project)

            # Get AI provider and generate diagnosis
            provider = get_provider()
            if not provider.is_available():
                raise ProviderUnavailableError(f"AI provider {settings.ai_provider} is not available")

            findings = await provider.diagnose(evidence)

            # Save results
            diagnosis.status = "completed"
            diagnosis.findings = findings.model_dump()
            diagnosis.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()

        except (ProviderUnavailableError, ProviderTimeoutError, InvalidResponseError, ProviderError) as e:
            # Provider errors - mark as failed but preserve the health check
            diagnosis.status = "failed"
            diagnosis.error_message = str(e)
            diagnosis.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()

        except Exception as e:
            # Unexpected errors
            diagnosis.status = "failed"
            diagnosis.error_message = f"Unexpected error: {e}"
            diagnosis.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()

    finally:
        db.close()


def get_diagnosis(db: Session, diagnosis_id: int) -> Optional[Diagnosis]:
    """Get a diagnosis by ID."""
    return db.get(Diagnosis, diagnosis_id)


def list_diagnoses(db: Session, health_check_id: int, limit: int = 10) -> list[Diagnosis]:
    """List diagnoses for a health check."""
    return (
        db.query(Diagnosis)
        .filter(Diagnosis.health_check_id == health_check_id)
        .order_by(Diagnosis.created_at.desc())
        .limit(limit)
        .all()
    )


def shutdown() -> None:
    """Shutdown the diagnosis executor."""
    global _executor
    with _executor_lock:
        executor, _executor = _executor, None
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)
