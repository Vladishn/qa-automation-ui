"""Centralized configuration helpers for the QA automation tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

# Absolute project root derived from this file's location.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Canonical log directories used across the project.
LOG_ROOT: Path = PROJECT_ROOT / "logs"
RAW_LOGCAT_DIR: Path = LOG_ROOT / "raw_logcat"
SESSION_LOG_DIR: Path = LOG_ROOT / "sessions"
REPORT_DIR: Path = LOG_ROOT / "reports"
KNOWLEDGE_DIR: Path = PROJECT_ROOT / "knowledge"
TV_AUTO_SYNC_KNOWLEDGE: Path = KNOWLEDGE_DIR / "quickset_tv_auto_sync.yaml"


def ensure_directories() -> None:
    """Ensure that the log directories exist before writing any artifacts."""
    for path in (LOG_ROOT, RAW_LOGCAT_DIR, SESSION_LOG_DIR, REPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)


@dataclass
class SessionConfig:
    """Describes the runtime parameters for a specific QA session."""

    session_id: str
    stb_ip: str
    scenario_name: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the configuration into a dictionary for logging."""
        return {
            "session_id": self.session_id,
            "stb_ip": self.stb_ip,
            "scenario_name": self.scenario_name,
        }

    @property
    def logcat_path(self) -> Path:
        """Return the default file path for the session's raw logcat capture."""
        ensure_directories()
        return RAW_LOGCAT_DIR / f"{self.session_id}.log"

    @property
    def session_log_path(self) -> Path:
        """Return the JSONL path that will store the scenario step results."""
        ensure_directories()
        return SESSION_LOG_DIR / f"{self.session_id}.jsonl"

    @property
    def report_path(self) -> Path:
        """Return the default markdown report output path."""
        ensure_directories()
        return REPORT_DIR / f"report_{self.session_id}.md"
