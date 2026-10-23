"""Collects and bounds diagnostic evidence for AI analysis."""
from typing import Optional

from app.core.config import settings
from app.database.database import HealthCheck, Project
from app.services.sanitizer import sanitize_output


class EvidenceCollector:
    """Collects bounded diagnostic evidence from health check results."""

    def __init__(self, max_bytes: int = None):
        self.max_bytes = max_bytes or settings.ai_max_evidence_bytes

    def collect(self, health_check: HealthCheck, project: Project) -> str:
        """Collect evidence from health check and project, bounded by size limits."""
        sections = []

        # 1. Project metadata
        sections.append(self._format_project_section(project))

        # 2. Health check summary
        sections.append(self._format_health_check_section(health_check))

        # 3. Git status (if available)
        if health_check.branch or health_check.is_clean is not None:
            sections.append(self._format_git_section(health_check))

        # 4. Command output (redacted and bounded)
        if health_check.output:
            sections.append(self._format_output_section(health_check.output))

        # 5. Error information
        if health_check.error:
            sections.append(self._format_error_section(health_check.error))

        # Combine and truncate if needed
        full_evidence = "\n\n".join(sections)
        return self._truncate(full_evidence)

    def _format_project_section(self, project: Project) -> str:
        """Format project metadata."""
        return f"""PROJECT METADATA:
- Name: {project.display_name}
- Repository path: {project.repository_path}
- Check command: {project.check_command or 'None'}
- Created: {project.created_at.isoformat()}
"""

    def _format_health_check_section(self, health_check: HealthCheck) -> str:
        """Format health check summary."""
        return f"""HEALTH CHECK SUMMARY:
- Status: {health_check.status}
- Timestamp: {health_check.timestamp.isoformat()}
- Duration: {health_check.duration_ms:.0f}ms
- Exit code: {health_check.exit_code or 'N/A'}
- Check command: {health_check.check_command or 'None'}
"""

    def _format_git_section(self, health_check: HealthCheck) -> str:
        """Format Git status information."""
        lines = ["GIT STATUS:"]
        if health_check.branch:
            lines.append(f"- Branch: {health_check.branch}")
        if health_check.is_clean is not None:
            clean_status = "clean" if health_check.is_clean else f"{health_check.changed_files or '?'} changed files"
            lines.append(f"- Working tree: {clean_status}")
        return "\n".join(lines)

    def _format_output_section(self, output: str) -> str:
        """Format command output with redaction and bounding."""
        # Sanitize to remove secrets
        sanitized = sanitize_output(output)
        # Truncate if too long
        truncated = self._truncate(sanitized, max_bytes=self.max_bytes // 2)
        return f"""COMMAND OUTPUT:
{truncated}
"""

    def _format_error_section(self, error: str) -> str:
        """Format error information."""
        sanitized = sanitize_output(error)
        return f"""ERROR:
{sanitized}
"""

    def _truncate(self, text: str, max_bytes: int = None) -> str:
        """Truncate text to fit within byte limit."""
        limit = max_bytes or self.max_bytes
        if len(text.encode('utf-8')) <= limit:
            return text

        # Binary search for truncation point
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if len(text[:mid].encode('utf-8')) <= limit:
                low = mid
            else:
                high = mid - 1

        truncated = text[:low]
        if len(truncated) < len(text):
            truncated += "\n[... evidence truncated due to size limit ...]"
        return truncated
