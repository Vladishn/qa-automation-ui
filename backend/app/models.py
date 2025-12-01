# app/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Channel = Literal["DEV", "QA", "STAGE", "PROD"]
DomainType = Literal["FIRMWARE", "APP"]
RunStatus = Literal["NOT_STARTED", "RUNNING", "PASSED", "FAILED", "PARTIAL"]


@dataclass
class PlatformModel:
    id: str                  # e.g. "SEI_X4_FW", "ANDROID_TV_VSTB"
    label: str               # human-friendly label
    family: Optional[str] = None  # e.g. "STB", "SMART_TV", "MOBILE"
    vendor: Optional[str] = None  # e.g. "SEI", "Ventiva", "LG", "Samsung"
    model: Optional[str] = None   # e.g. "SEI X4", "S70PCI"


@dataclass
class VersionModel:
    id: str
    domain: DomainType       # "FIRMWARE" or "APP"
    platform_id: str
    version_label: str
    release_channel: Optional[Channel] = None
    is_active: bool = False


@dataclass
class TestScenarioModel:
    id: str
    name: str
    priority: Optional[int] = None   # 1–5
    description: Optional[str] = None
    tags: Optional[List[str]] = None


@dataclass
class TestRunModel:
    id: str
    session_id: str
    domain: DomainType
    platform_id: str
    version_id: str
    tester_id: Optional[str] = None
    status: RunStatus = "NOT_STARTED"
    pass_rate: float = 0.0
    passed_scenarios: int = 0
    failed_scenarios: int = 0
    total_scenarios: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@dataclass
class TestIssueModel:
    """
    Generic issue model (what storage / routers expect).
    Represents an issue on a specific step inside a scenario.
    """
    id: str
    run_id: str
    scenario_id: str
    step_index: int
    title: str
    description: str
    suspected_root_cause: Optional[str] = None
    jira_summary_suggestion: Optional[str] = None
    jira_description_suggestion: Optional[str] = None


@dataclass
class SessionModel:
    id: str
    domain: DomainType
    platform_id: str
    version_id: str
    tester_id: Optional[str] = None
    status: RunStatus = "NOT_STARTED"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


QuickSetStatus = Literal["pending", "running", "pass", "fail", "info"]
QuickSetInputKind = Literal["continue", "boolean", "text"]


class QuickSetStep(BaseModel):
    name: str
    status: QuickSetStatus
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QuickSetQuestion(BaseModel):
    id: str
    prompt: str
    step_name: str
    input_kind: QuickSetInputKind
    choices: Optional[List[str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QuickSetSession(BaseModel):
    session_id: str
    tester_id: str
    stb_ip: str
    scenario_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    steps: List[QuickSetStep] = Field(default_factory=list)
    result: Optional[QuickSetStatus] = None
    logs: Dict[str, str] = Field(default_factory=lambda: {"adb": "", "logcat": ""})
    state: str = "running"
    pending_question: Optional[QuickSetQuestion] = None
    summary: Optional[str] = None
