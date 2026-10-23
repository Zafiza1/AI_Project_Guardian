"""AI provider interface and Ollama implementation for diagnosis."""
import json
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.core.config import settings
from app.models.diagnosis import DiagnosisFinding


class ProviderError(Exception):
    """Base exception for AI provider errors."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when the AI provider is not available."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when the AI provider times out."""
    pass


class InvalidResponseError(ProviderError):
    """Raised when the AI provider returns invalid response."""
    pass


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def diagnose(self, evidence: str) -> DiagnosisFinding:
        """Generate a diagnosis based on the provided evidence."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


class OllamaProvider(AIProvider):
    """Ollama provider for local AI models."""

    def __init__(self, endpoint: str = None, model: str = None, timeout: int = None):
        self.endpoint = (endpoint or settings.ai_endpoint).rstrip("/")
        self.model = model or settings.ai_model
        self.timeout = timeout or settings.ai_timeout_seconds

    def is_available(self) -> bool:
        """Check if Ollama is available by trying to list models."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.endpoint}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def diagnose(self, evidence: str) -> DiagnosisFinding:
        """Generate a diagnosis using Ollama."""
        prompt = self._build_prompt(evidence)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 2000},
                    },
                )
                response.raise_for_status()
                data = response.json()
                if "response" not in data:
                    raise InvalidResponseError("Ollama response missing 'response' field")

                return self._parse_response(data["response"])
        except httpx.TimeoutException:
            raise ProviderTimeoutError(f"Ollama request timed out after {self.timeout}s")
        except httpx.ConnectError as e:
            raise ProviderUnavailableError(f"Cannot connect to Ollama at {self.endpoint}: {e}")
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}")
        except json.JSONDecodeError as e:
            raise InvalidResponseError(f"Failed to parse Ollama response as JSON: {e}")

    def _build_prompt(self, evidence: str) -> str:
        """Build the prompt for the AI model."""
        return f"""You are an expert software engineer diagnosing a failed health check in a Git repository.

Analyze the following evidence from a health check run and provide a structured diagnosis.

EVIDENCE:
{evidence}

Respond with a JSON object containing ONLY these fields (no markdown, no additional text):
{{
  "problem_summary": "Brief summary of what went wrong",
  "suspected_root_cause": "Most likely cause based on the evidence",
  "evidence": ["list of relevant evidence points from the logs"],
  "file_paths": ["list of relevant file paths mentioned, if any"],
  "line_numbers": ["list of line numbers or ranges mentioned, if any"],
  "confidence_level": "high|medium|low",
  "confidence_explanation": "Why you assigned this confidence level",
  "remediation_steps": ["step 1", "step 2", ...],
  "verification_tests": ["test 1", "test 2", ...],
  "missing_information": ["what would help improve diagnosis, if anything"],
  "alternative_explanations": ["other possible causes, if any"],
  "severity": "critical|high|medium|low",
  "impact_assessment": "How this affects the project"
}}

IMPORTANT:
- Use ONLY the evidence provided. Do not invent log entries, file paths, or facts.
- If evidence is insufficient, state that in missing_information and set confidence to low.
- file_paths and line_numbers should only be included if explicitly mentioned in the evidence.
- Return ONLY the JSON object, nothing else.
"""

    def _parse_response(self, response_text: str) -> DiagnosisFinding:
        """Parse the AI response into a DiagnosisFinding."""
        # Try to extract JSON from the response (in case of markdown code blocks)
        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(json_text)
            return DiagnosisFinding(**data)
        except json.JSONDecodeError as e:
            raise InvalidResponseError(f"Failed to parse diagnosis JSON: {e}\nResponse was: {response_text[:500]}")
        except Exception as e:
            raise InvalidResponseError(f"Failed to validate diagnosis structure: {e}")


def get_provider() -> AIProvider:
    """Get the configured AI provider instance."""
    if settings.ai_provider.lower() == "ollama":
        return OllamaProvider()
    else:
        raise ValueError(f"Unsupported AI provider: {settings.ai_provider}")
