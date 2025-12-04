# backend/tests/test_tv_autosync_contract.py
"""
Regression contract for TV_AUTO_SYNC QuickSet analyzer.

This test suite enforces that 4 golden sessions always produce
the same summary + key step statuses.

Scenarios covered (see tv_autosync_contract.yml):
- happy_path
- no_volume_change_issue
- brand_mismatch_only
- volume_mismatch_only
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import yaml

# ==== PATHS – adjust if your repo layout is different ======================

# root of the backend repo (…/TestProj/backend/)
BACKEND_ROOT = Path(__file__).resolve().parents[1]

# artifacts directory created by the CLI / runner
ARTIFACTS_DIR = BACKEND_ROOT.parent / "artifacts"

# where the JSONL step events live
STEPS_DIR = ARTIFACTS_DIR / "quickset_steps"

# where the tester answers live (if applicable)
ANSWERS_DIR = ARTIFACTS_DIR / "quickset_user_answers"

# contract file
CONTRACT_PATH = BACKEND_ROOT / "tests" / "data" / "tv_autosync_contract.yml"

# import from your analyzer
from backend.quickset_timeline_analyzer import build_timeline_and_summary  # type: ignore  # noqa: E402


# ==== helpers ==============================================================


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file (one JSON object per line). Returns empty list if file is missing."""
    if not path.exists():
        return []
    lines: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines.append(json.loads(line))
    return lines


def load_session_artifacts(session_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load raw QuickSet events + user answers for a given session_id."""
    steps_path = STEPS_DIR / f"{session_id}.jsonl"
    answers_path = ANSWERS_DIR / f"{session_id}.jsonl"

    events = load_jsonl(steps_path)
    answers = load_jsonl(answers_path)

    if not events:
        raise AssertionError(
            f"[TV_AUTO_SYNC contract] No events found for session_id={session_id} "
            f"(expected at {steps_path}). Make sure you kept the artifacts."
        )
    return events, answers


def load_contract() -> Dict[str, Any]:
    if not CONTRACT_PATH.exists():
        raise AssertionError(
            f"[TV_AUTO_SYNC contract] Contract file not found at {CONTRACT_PATH}"
        )
    with CONTRACT_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "scenarios" not in data:
        raise AssertionError(
            f"[TV_AUTO_SYNC contract] Malformed YAML: expected 'scenarios' key in {CONTRACT_PATH}"
        )
    return data["scenarios"]


def find_timeline_row(timeline: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
    for row in timeline:
        if row.get("name") == name:
            return row
    raise AssertionError(f"[TV_AUTO_SYNC contract] Timeline row '{name}' not found")


# ==== fixtures =============================================================


@pytest.fixture(scope="session")
def contract() -> Dict[str, Any]:
    """Loaded tv_autosync_contract.yml content."""
    return load_contract()


@pytest.fixture(scope="session")
def backend_root() -> Path:
    return BACKEND_ROOT


# ==== parametrized contract test ==========================================


@pytest.mark.parametrize(
    "scenario_key",
    [
        "happy_path",
        "no_volume_change_issue",
        "brand_mismatch_only",
        "volume_mismatch_only",
    ],
)
def test_tv_autosync_contract(scenario_key: str, contract: Dict[str, Any]) -> None:
    """
    Single contract test that runs the analyzer on a real session for each scenario
    and asserts both summary fields and key timeline statuses.
    """
    scenario_cfg = contract.get(scenario_key)
    assert scenario_cfg is not None, f"Scenario '{scenario_key}' missing from contract YAML"

    session_id = scenario_cfg["session_id"]
    expected_summary = scenario_cfg["expected_summary"]
    expected_steps = scenario_cfg["expected_steps"]

    # 1. load events + answers from artifacts
    raw_events, user_answers = load_session_artifacts(session_id)

    # 2. run analyzer exactly like the router does
    session_summary, timeline = build_timeline_and_summary(raw_events, user_answers)

    # 3. assert summary contract
    assert session_summary["scenario_name"] == expected_summary["scenario_name"]
    assert session_summary["overall_status"] == expected_summary["overall_status"]
    assert session_summary["analysis_text"] == expected_summary["analysis_text"]

    assert session_summary["brand_mismatch"] == expected_summary["brand_mismatch"]
    assert session_summary["tv_brand_user"] == expected_summary["tv_brand_user"]
    assert session_summary["tv_brand_log"] == expected_summary["tv_brand_log"]

    assert session_summary["has_volume_issue"] == expected_summary["has_volume_issue"]
    assert session_summary["has_osd_issue"] == expected_summary["has_osd_issue"]
    assert session_summary["has_failure"] == expected_summary["has_failure"]

    # 4. assert key step statuses
    for step_name, expected_status in expected_steps.items():
        row = find_timeline_row(timeline, step_name)
        actual_status = row.get("status")
        assert (
            actual_status == expected_status
        ), f"[{scenario_key}] step '{step_name}' status {actual_status!r} != expected {expected_status!r}"


# ==== explicit targeted tests (optional but useful for debugging) ==========
# אם תצטרך דיבוג מדויק – אפשר להוסיף פה טסטים נפרדים לכל תרחיש.
# כרגע הכל מכוסה על ידי הטסט הפרמטרי למעלה.
