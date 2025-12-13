"""Shared models for analyzer outputs and diagnostics."""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

FailureCategory = Literal[
    "functional",
    "integration",
    "environment",
    "data",
    "test_logic",
    "tooling",
    "timing",
    "ux",
    "device",
    "operational",
]

FailureSeverity = Literal["low", "medium", "high", "critical"]

# IMPORTANT:
# AnalyzerStatus must match the real statuses produced by the analyzers.
# We explicitly allow AWAITING_INPUT in addition to PASS/FAIL/PENDING/INFO.
AnalyzerStatus = Literal[
    "PASS",
    "FAIL",
    "PENDING",
    "INFO",
    "AWAITING_INPUT",
    "INCONCLUSIVE",
]

ConfidenceLevel = Literal["low", "medium", "high"]


class FailureInsight(BaseModel):
    code: str
    category: FailureCategory
    severity: FailureSeverity
    title: str
    description: str
    evidence_keys: List[str] = Field(default_factory=list)


class AnalyzerResult(BaseModel):
    overall_status: AnalyzerStatus
    has_failure: bool
    failed_steps: List[str] = Field(default_factory=list)
    awaiting_steps: List[str] = Field(default_factory=list)
    analysis_text: str

    failure_insights: List[FailureInsight] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "medium"
