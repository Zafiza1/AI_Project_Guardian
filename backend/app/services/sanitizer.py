"""Removes secrets and terminal noise from command output before it is stored or displayed."""
import os
import re

REDACTED = "[REDACTED]"

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # https://user:password@host
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/:@]+:[^\s/@]+@"), r"\1" + REDACTED + "@"),
    # Authorization: Bearer xxx / token xxx
    (re.compile(r"(?i)\b(bearer|basic|token)\s+[a-z0-9._~+/=-]{8,}"), r"\1 " + REDACTED),
    # Well-known token formats
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), REDACTED),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), REDACTED),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTED),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), REDACTED),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), REDACTED),
    # KEY=value / "api_key": "value" style assignments with sensitive names
    (
        re.compile(
            r"(?i)\b([a-z0-9_]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)s?[a-z0-9_]*)"
            r"(\s*[:=]\s*)([\"']?)[^\s\"',;]+\3"
        ),
        r"\1\2\3" + REDACTED + r"\3",
    ),
]

_SENSITIVE_ENV_NAME = re.compile(r"(?i)(password|passwd|secret|token|key|credential|auth)")


def _sensitive_env_values() -> list[str]:
    values = []
    for name, value in os.environ.items():
        if _SENSITIVE_ENV_NAME.search(name) and len(value) >= 6:
            values.append(value)
    return sorted(values, key=len, reverse=True)


def sanitize_output(text: str) -> str:
    if not text:
        return text
    text = _ANSI_RE.sub("", text).replace("\r\n", "\n")
    for value in _sensitive_env_values():
        text = text.replace(value, REDACTED)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
