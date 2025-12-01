"""Pydantic schemas describing backend payloads."""

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field

Channel = Literal["DEV", "QA", "STAGE", "PROD"]
DomainType = Literal["FIRMWARE", "APP"]
RunStatus = Literal["NOT_STARTED", "RUNNING", "PASSED", "FAILED", "PARTIAL"]


class Platform(BaseModel):
    id: str
    label: str
    family: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None


class VersionUnderTest(BaseModel):
    id: str
    domain: DomainType
    platform_id: str = Field(..., alias="platformId")
    version_label: str = Field(..., alias="versionLabel")
    release_channel: Optional[Channel] = Field(None, alias="releaseChannel")
    is_active: bool = Field(False, alias="isActive")

    class Config:
        allow_population_by_field_name = True


class VersionCreate(BaseModel):
    domain: DomainType
    platform_id: str = Field(..., alias="platformId")
    version_label: str = Field(..., alias="versionLabel")
    release_channel: Optional[Channel] = Field(None, alias="releaseChannel")
    is_active: bool = Field(False, alias="isActive")

    class Config:
        allow_population_by_field_name = True


class TestScenario(BaseModel):
    id: str
    name: str
    priority: Optional[int] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class TestRunSummary(BaseModel):
    id: str
    session_id: str = Field(..., alias="sessionId")
    domain: DomainType
    platform_id: str = Field(..., alias="platformId")
    version_id: str = Field(..., alias="versionId")
    tester_id: Optional[str] = Field(None, alias="testerId")
    status: RunStatus
    pass_rate: float = Field(..., alias="passRate")
    passed_scenarios: int = Field(..., alias="passedScenarios")
    failed_scenarios: int = Field(..., alias="failedScenarios")
    total_scenarios: int = Field(..., alias="totalScenarios")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    finished_at: Optional[datetime] = Field(None, alias="finishedAt")

    class Config:
        allow_population_by_field_name = True


class TestRunCreate(BaseModel):
    session_id: str = Field(..., alias="sessionId")
    domain: DomainType
    platform_id: str = Field(..., alias="platformId")
    version_id: str = Field(..., alias="versionId")
    tester_id: Optional[str] = Field(None, alias="testerId")
    status: RunStatus
    pass_rate: float = Field(..., alias="passRate")
    passed_scenarios: int = Field(..., alias="passedScenarios")
    failed_scenarios: int = Field(..., alias="failedScenarios")
    total_scenarios: int = Field(..., alias="totalScenarios")

    class Config:
        allow_population_by_field_name = True


class TestStepIssue(BaseModel):
    id: str
    run_id: str = Field(..., alias="runId")
    scenario_id: str = Field(..., alias="scenarioId")
    step_index: int = Field(..., alias="stepIndex")
    title: str
    description: str
    suspected_root_cause: Optional[str] = Field(None, alias="suspectedRootCause")
    jira_summary_suggestion: Optional[str] = Field(None, alias="jiraSummarySuggestion")
    jira_description_suggestion: Optional[str] = Field(None, alias="jiraDescriptionSuggestion")

    class Config:
        allow_population_by_field_name = True


class SessionCreateRequest(BaseModel):
    domain: DomainType
    platform_id: str = Field(..., alias="platformId")
    version_id: str = Field(..., alias="versionId")
    tester_id: Optional[str] = Field(None, alias="testerId")
    scenarios: Optional[List[str]] = None
    comment: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class Session(BaseModel):
    id: str
    domain: DomainType
    platform_id: str = Field(..., alias="platformId")
    version_id: str = Field(..., alias="versionId")
    tester_id: Optional[str] = Field(None, alias="testerId")
    status: RunStatus
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    class Config:
        allow_population_by_field_name = True


class QuickSetRunRequest(BaseModel):
    tester_id: str = Field(..., alias="tester_id")
    stb_ip: str = Field(..., alias="stb_ip")
    scenario_name: str = Field(..., alias="scenario_name")

    class Config:
        allow_population_by_field_name = True


class QuickSetRunResponse(BaseModel):
    session_id: str = Field(..., alias="session_id")
    scenario_name: str = Field(..., alias="scenario_name")

    class Config:
        allow_population_by_field_name = True


class QuickSetStep(BaseModel):
    name: str
    status: str
    timestamp: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class QuickSetQuestion(BaseModel):
    id: str
    prompt: str
    metadata: dict = Field(default_factory=dict)


class QuickSetSession(BaseModel):
    session_id: str = Field(..., alias="session_id")
    tester_id: str = Field(..., alias="tester_id")
    stb_ip: str = Field(..., alias="stb_ip")
    scenario_name: str = Field(..., alias="scenario_name")
    start_time: datetime = Field(..., alias="start_time")
    end_time: Optional[datetime] = Field(None, alias="end_time")
    steps: List[QuickSetStep] = Field(default_factory=list)
    result: Optional[str] = None
    logs: dict = Field(default_factory=dict)
    state: str = "running"
    pending_question: Optional[QuickSetQuestion] = Field(None, alias="pending_question")

    class Config:
        allow_population_by_field_name = True


class QuickSetAnswer(BaseModel):
    answer: str
