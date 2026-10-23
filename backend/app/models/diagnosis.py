from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


DiagnosisStatus = Literal["pending", "completed", "failed"]


class DiagnosisFinding(BaseModel):
    """Structured findings from AI diagnosis."""
    problem_summary: str = Field(..., description="Concise summary of the problem")
    suspected_root_cause: str = Field(..., description="Suspected root cause based on evidence")
    evidence: list[str] = Field(default_factory=list, description="Relevant evidence extracted from logs")
    file_paths: list[str] = Field(default_factory=list, description="Relevant file paths mentioned in evidence")
    line_numbers: list[str] = Field(default_factory=list, description="Line numbers or ranges when available")
    confidence_level: str = Field(..., description="Confidence level: high, medium, or low")
    confidence_explanation: str = Field(..., description="Explanation for the confidence level")
    remediation_steps: list[str] = Field(default_factory=list, description="Recommended remediation steps")
    verification_tests: list[str] = Field(default_factory=list, description="Suggested verification tests")
    missing_information: list[str] = Field(default_factory=list, description="Information that could improve diagnosis")
    alternative_explanations: list[str] = Field(default_factory=list, description="Alternative possible causes")
    severity: str = Field(..., description="Severity: critical, high, medium, or low")
    impact_assessment: str = Field(..., description="Assessment of the impact on the project")


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    health_check_id: int
    status: DiagnosisStatus
    provider: str
    model: str
    findings: Optional[DiagnosisFinding] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    @field_serializer("created_at", "completed_at")
    def _ser_ts(self, v: Optional[datetime]) -> Optional[str]:
        if v is None:
            return None
        return _as_utc(v).isoformat()


class DiagnosisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    health_check_id: int = Field(..., description="ID of the health check to diagnose")
