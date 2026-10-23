"""Tests for AI diagnosis functionality."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ConnectError, HTTPStatusError, TimeoutException

from app.database.database import Diagnosis, HealthCheck, Project, SessionLocal, init_db
from app.models.diagnosis import DiagnosisFinding, DiagnosisStatus
from app.services.ai_provider import (
    InvalidResponseError,
    OllamaProvider,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.diagnosis_service import (
    DiagnosisAlreadyRunningError,
    InvalidHealthCheckError,
    get_diagnosis,
    list_diagnoses,
    start_diagnosis,
)
from app.services.evidence_collector import EvidenceCollector
from app.services.health_check_service import FINISHED_FAILURE_STATUSES


@pytest.fixture
def db():
    """Create a fresh database for each test."""
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def project(db):
    """Create a test project."""
    project = Project(
        display_name="Test Project",
        repository_path="/tmp/test-repo",
        check_command="pytest",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@pytest.fixture
def health_check(db, project):
    """Create a failed health check."""
    check = HealthCheck(
        project_id=project.id,
        status="failed",
        branch="main",
        is_clean=False,
        changed_files=5,
        check_command="pytest",
        exit_code=1,
        duration_ms=5000.0,
        output="test output with error",
        error="Test failed: assertion error",
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def test_evidence_collector_collects_bounded_evidence(db, health_check, project):
    """Test that evidence collector gathers and bounds diagnostic evidence."""
    collector = EvidenceCollector(max_bytes=1000)
    evidence = collector.collect(health_check, project)

    assert "PROJECT METADATA" in evidence
    assert "Test Project" in evidence
    assert "HEALTH CHECK SUMMARY" in evidence
    assert "failed" in evidence
    assert "GIT STATUS" in evidence
    assert "main" in evidence
    assert "COMMAND OUTPUT" in evidence


def test_evidence_collector_truncates_large_output(db, health_check, project):
    """Test that evidence collector truncates output that exceeds byte limit."""
    health_check.output = "x" * 200_000  # Large output
    collector = EvidenceCollector(max_bytes=1000)
    evidence = collector.collect(health_check, project)

    assert len(evidence.encode('utf-8')) < 1500  # Should be near limit
    assert "truncated" in evidence.lower()


def test_evidence_collector_redacts_secrets(db, health_check, project, monkeypatch):
    """Test that evidence collector redacts secrets."""
    monkeypatch.setenv("TEST_SECRET", "super-secret-value-123")
    health_check.output = "Error: secret is super-secret-value-123"
    collector = EvidenceCollector()
    evidence = collector.collect(health_check, project)

    assert "super-secret-value-123" not in evidence
    assert "[REDACTED]" in evidence


def test_ollama_provider_is_available():
    """Test Ollama provider availability check."""
    provider = OllamaProvider(endpoint="http://127.0.0.1:99999")  # Unlikely to be running

    # This should return False when Ollama is not available
    assert provider.is_available() is False


async def test_ollama_provider_diagnose_success():
    """Test successful diagnosis with mocked Ollama."""
    provider = OllamaProvider()
    mock_response = {
        "response": json.dumps({
            "problem_summary": "Test failure",
            "suspected_root_cause": "Assertion error",
            "evidence": ["test output"],
            "file_paths": ["test.py"],
            "line_numbers": ["42"],
            "confidence_level": "high",
            "confidence_explanation": "Clear error message",
            "remediation_steps": ["Fix assertion"],
            "verification_tests": ["Run test again"],
            "missing_information": [],
            "alternative_explanations": [],
            "severity": "medium",
            "impact_assessment": "Test suite fails",
        })
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = mock_response

        evidence = "Test evidence"
        findings = await provider.diagnose(evidence)

        assert isinstance(findings, DiagnosisFinding)
        assert findings.problem_summary == "Test failure"
        assert findings.confidence_level == "high"


async def test_ollama_provider_timeout():
    """Test Ollama provider timeout handling."""
    provider = OllamaProvider(timeout=1)

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = TimeoutException("Request timed out")

        with pytest.raises(ProviderTimeoutError):
            await provider.diagnose("test evidence")


async def test_ollama_provider_connection_error():
    """Test Ollama provider connection error handling."""
    provider = OllamaProvider()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = ConnectError("Cannot connect")

        with pytest.raises(ProviderUnavailableError):
            await provider.diagnose("test evidence")


async def test_ollama_provider_malformed_response():
    """Test Ollama provider malformed response handling."""
    provider = OllamaProvider()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {"response": "not valid json"}

        with pytest.raises(InvalidResponseError):
            await provider.diagnose("test evidence")


def test_start_diagnosis_requires_failed_check(db, health_check):
    """Test that diagnosis can only be requested for failed checks."""
    health_check.status = "success"
    db.commit()

    with pytest.raises(InvalidHealthCheckError) as exc:
        start_diagnosis(db, health_check.id)

    assert "only" in str(exc.value).lower()
    assert "failed" in str(exc.value).lower()


def test_start_diagnosis_prevents_duplicates(db, health_check):
    """Test that duplicate diagnosis requests are prevented."""
    # Create a pending diagnosis
    diagnosis = Diagnosis(
        health_check_id=health_check.id,
        status="pending",
        provider="ollama",
        model="llama3.2",
    )
    db.add(diagnosis)
    db.commit()

    with pytest.raises(DiagnosisAlreadyRunningError):
        start_diagnosis(db, health_check.id)


def test_start_diagnosis_creates_pending_record(db, health_check):
    """Test that starting a diagnosis creates a pending record."""
    diagnosis = start_diagnosis(db, health_check.id)

    assert diagnosis.status == "pending"
    assert diagnosis.health_check_id == health_check.id
    assert diagnosis.provider == "ollama"
    assert diagnosis.model == "llama3.2"
    assert diagnosis.findings is None
    assert diagnosis.error_message is None


def test_get_diagnosis(db, health_check):
    """Test retrieving a diagnosis by ID."""
    diagnosis = Diagnosis(
        health_check_id=health_check.id,
        status="completed",
        provider="ollama",
        model="llama3.2",
        findings={"problem_summary": "Test"},
    )
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)

    retrieved = get_diagnosis(db, diagnosis.id)
    assert retrieved is not None
    assert retrieved.id == diagnosis.id
    assert retrieved.status == "completed"


def test_list_diagnoses(db, health_check):
    """Test listing diagnoses for a health check."""
    for i in range(3):
        diagnosis = Diagnosis(
            health_check_id=health_check.id,
            status="completed",
            provider="ollama",
            model="llama3.2",
            findings={"problem_summary": f"Test {i}"},
        )
        db.add(diagnosis)
    db.commit()

    diagnoses = list_diagnoses(db, health_check.id)
    assert len(diagnoses) == 3
    # Should be ordered by created_at desc
    assert diagnoses[0].created_at >= diagnoses[1].created_at


def test_diagnosis_finding_validation():
    """Test that DiagnosisFinding validates required fields."""
    # Valid finding
    finding = DiagnosisFinding(
        problem_summary="Test",
        suspected_root_cause="Error",
        confidence_level="high",
        confidence_explanation="Clear",
        severity="medium",
        impact_assessment="Low",
    )
    assert finding.problem_summary == "Test"

    # Missing required field should raise validation error
    with pytest.raises(Exception):  # Pydantic ValidationError
        DiagnosisFinding(
            problem_summary="Test",
            # Missing required fields
        )
