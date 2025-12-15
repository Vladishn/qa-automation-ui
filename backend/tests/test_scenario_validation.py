from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.routers import quickset as quickset_router
from backend.app.scenario_enums import ScenarioName
from backend.app.quickset_timeline_analyzer import build_timeline_and_summary
from backend.app.device_control import _parse_focus_from_window, _parse_focus_from_activity


client = TestClient(app)
API_HEADERS = {"X-QuickSet-Api-Key": "test-key"}


@pytest.fixture(autouse=True)
def stub_workflow_thread(monkeypatch):
    def _noop(handler, session_id, *args, **kwargs):
        return None

    monkeypatch.setattr(quickset_router, "_launch_workflow_thread", _noop)
    yield


def test_run_scenario_rejects_invalid_name():
    response = client.post(
        "/api/quickset/scenarios/run",
        json={"tester_id": "t1", "stb_ip": "127.0.0.1", "scenario_name": "INVALID"},
        headers=API_HEADERS,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported scenario"


def test_run_scenario_rejects_expected_channel_for_tv_auto_sync():
    response = client.post(
        "/api/quickset/scenarios/run",
        json={
            "tester_id": "t1",
            "stb_ip": "127.0.0.1",
            "scenario_name": "TV_AUTO_SYNC",
            "expected_channel": 5,
        },
        headers=API_HEADERS,
    )
    assert response.status_code == 400
    assert "expected_channel" in response.json()["detail"]


def test_run_scenario_accepts_live_with_expected_channel():
    response = client.post(
        "/api/quickset/scenarios/run",
        json={
            "tester_id": "t1",
            "stb_ip": "127.0.0.1",
            "scenario_name": "LIVE_BUTTON_MAPPING",
            "expected_channel": 11,
        },
        headers=API_HEADERS,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["scenario_name"] == ScenarioName.LIVE_BUTTON_MAPPING.value


def test_analyzer_dispatch_for_live_has_no_autosync_steps():
    result = build_timeline_and_summary(
        session_id="TEST_SESSION",
        scenario_name=ScenarioName.LIVE_BUTTON_MAPPING.value,
        raw_events=[],
    )
    assert result["analysis_result"]["awaiting_steps"] == []


def test_focus_parser_handles_window_output():
    sample = "mCurrentFocus=Window{42a u0 com.pkg/.MainActivity}"
    focus = _parse_focus_from_window(sample)
    assert focus is not None
    assert focus.package == "com.pkg"
    assert focus.activity == ".MainActivity"


def test_focus_parser_handles_activity_output():
    sample = "mResumedActivity: ActivityRecord{a com.yt/.LeanbackActivity}"
    focus = _parse_focus_from_activity(sample)
    assert focus is not None
    assert focus.package == "com.yt"
    assert focus.activity == ".LeanbackActivity"
