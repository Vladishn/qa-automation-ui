from __future__ import annotations

from backend.app.quickset_timeline_analyzer import build_timeline_and_summary


def test_tv_auto_sync_analyzer_handles_missing_autosync_markers() -> None:
    payload = build_timeline_and_summary(
        session_id="QS_TEST_ANALYZER",
        scenario_name="TV_AUTO_SYNC",
        raw_events=[],
    )
    assert "session" in payload
    assert "timeline" in payload
    assert payload["session"]["scenario_name"] == "TV_AUTO_SYNC"
