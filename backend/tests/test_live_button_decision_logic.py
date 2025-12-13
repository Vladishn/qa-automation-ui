from __future__ import annotations

from typing import Dict, List

from backend.app.live_button_log_parser import LiveButtonPhaseSignals, LiveButtonSignals
from backend.app.quickset_timeline_analyzer import (
    StepRow,
    StepStatus,
    _build_live_button_session_summary,
)


def _build_rows(include_question: bool = True, include_metadata: bool = True) -> List[StepRow]:
    rows: List[StepRow] = []
    if include_question:
        rows.append(
            StepRow(
                name="question_expected_channel",
                label="Expected channel",
                status=StepStatus.INFO,
                user_answer="",
                details={},
            )
        )
    if include_metadata:
        rows.append(
            StepRow(
                name="live_expected_channel",
                label="Expected channel",
                status=StepStatus.INFO,
                details={},
            )
        )
    rows.extend(
        [
            StepRow(
                name="configure_live_mapping",
                label="Configure Live button mapping",
                status=StepStatus.INFO,
                details={},
            ),
            StepRow(
                name="phase1_live_press",
                label="Phase1",
                status=StepStatus.INFO,
                details={},
            ),
            StepRow(
                name="phase2_kill_and_relaunch",
                label="Phase2",
                status=StepStatus.INFO,
                details={},
            ),
            StepRow(
                name="phase3_reboot_persist",
                label="Phase3",
                status=StepStatus.INFO,
                details={},
            ),
            StepRow(
                name="analysis_summary",
                label="Scenario summary",
                status=StepStatus.INFO,
                details={},
            ),
        ]
    )
    return rows


def _build_user_answers(expected: str) -> Dict[str, str]:
    return {
        "question_expected_channel": expected,
    }


def _build_phases(channel: int) -> List[LiveButtonPhaseSignals]:
    return [
        LiveButtonPhaseSignals(
            phase="PHASE1",
            live_key_pressed=True,
            partnertv_launched=True,
            observed_channel=channel,
            raw_excerpt=f"Phase1 observed {channel}",
        ),
        LiveButtonPhaseSignals(
            phase="PHASE2",
            live_key_pressed=True,
            partnertv_launched=True,
            observed_channel=channel,
            raw_excerpt=f"Phase2 observed {channel}",
        ),
        LiveButtonPhaseSignals(
            phase="PHASE3",
            live_key_pressed=True,
            partnertv_launched=True,
            observed_channel=channel,
            raw_excerpt=f"Phase3 observed {channel}",
        ),
    ]


def test_live_button_passes_when_all_phases_match_expected_channel() -> None:
    rows = _build_rows()
    user_answers = _build_user_answers("50")
    live_signals = LiveButtonSignals(
        expected_channel=50,
        config_saved_channel=50,
        config_attempted=True,
        phases=_build_phases(50),
    )

    summary, analyzer_result = _build_live_button_session_summary(
        session_id="QS_TEST",
        scenario_name="LIVE_BUTTON_MAPPING",
        raw_events=[],
        timeline_rows=rows,
        user_answers=user_answers,
        live_signals=live_signals,
        expected_channel=50,
    )

    assert summary.overall_status == StepStatus.PASS
    assert analyzer_result.overall_status == "PASS"
    assert analyzer_result.failure_insights == []
    evidence = analyzer_result.evidence["live_button_signals"]
    assert evidence["config_saved_channel"] == 50
    assert all(phase["observed_channel"] == 50 for phase in evidence["phases"])


def test_live_button_reports_failure_when_phase3_wrong_channel() -> None:
    rows = _build_rows()
    user_answers = _build_user_answers("50")
    phases = _build_phases(50)
    phases[2] = LiveButtonPhaseSignals(
        phase="PHASE3",
        live_key_pressed=True,
        partnertv_launched=True,
        observed_channel=3,
    )
    live_signals = LiveButtonSignals(
        expected_channel=50,
        config_saved_channel=50,
        config_attempted=True,
        phases=phases,
    )

    summary, analyzer_result = _build_live_button_session_summary(
        session_id="QS_TEST",
        scenario_name="LIVE_BUTTON_MAPPING",
        raw_events=[],
        timeline_rows=rows,
        user_answers=user_answers,
        live_signals=live_signals,
        expected_channel=50,
    )

    assert summary.overall_status == StepStatus.FAIL
    assert analyzer_result.overall_status == "FAIL"
    codes = {ins.code for ins in analyzer_result.failure_insights}
    assert "live_button_wrong_channel_phase3" in codes


def test_live_button_fails_when_config_not_confirmed() -> None:
    rows = _build_rows()
    user_answers = _build_user_answers("50")
    live_signals = LiveButtonSignals(
        expected_channel=50,
        config_saved_channel=None,
        config_attempted=True,
        phases=_build_phases(50),
    )

    summary, analyzer_result = _build_live_button_session_summary(
        session_id="QS_TEST",
        scenario_name="LIVE_BUTTON_MAPPING",
        raw_events=[],
        timeline_rows=rows,
        user_answers=user_answers,
        live_signals=live_signals,
        expected_channel=50,
        log_excerpt="Sample log",
    )

    assert summary.overall_status == StepStatus.FAIL
    assert analyzer_result.overall_status == "FAIL"
    codes = {ins.code for ins in analyzer_result.failure_insights}
    assert "live_mapping_not_configured" in codes


def test_live_button_inconclusive_when_no_signals_detected() -> None:
    rows = _build_rows()
    user_answers = _build_user_answers("50")
    live_signals = LiveButtonSignals(
        expected_channel=50,
        config_saved_channel=None,
        config_attempted=False,
        phases=[],
    )

    summary, analyzer_result = _build_live_button_session_summary(
        session_id="QS_TEST",
        scenario_name="LIVE_BUTTON_MAPPING",
        raw_events=[],
        timeline_rows=rows,
        user_answers=user_answers,
        live_signals=live_signals,
        expected_channel=50,
        log_excerpt="QA LIVE SAMPLE",
    )

    assert summary.overall_status == StepStatus.INCONCLUSIVE
    assert summary.analysis_text == "INCONCLUSIVE – no log evidence captured."
    assert analyzer_result.overall_status == "INCONCLUSIVE"
    assert analyzer_result.has_failure is False
    codes = {ins.code for ins in analyzer_result.failure_insights}
    assert "live_button_logs_inconclusive_all_phases" in codes
    evidence = analyzer_result.evidence["live_button_signals"]
    excerpt = evidence.get("raw_excerpt")
    assert isinstance(excerpt, str) and excerpt.startswith("QA_LIVE")
    assert evidence.get("no_markers_found") is False


def test_expected_channel_metadata_row_used_when_no_question() -> None:
    rows = _build_rows(include_question=False, include_metadata=True)
    metadata_row = next(row for row in rows if row.name == "live_expected_channel")
    metadata_row.details["expected_channel"] = 77
    live_signals = LiveButtonSignals(
        expected_channel=77,
        config_saved_channel=77,
        config_attempted=True,
        phases=_build_phases(77),
    )

    summary, analyzer_result = _build_live_button_session_summary(
        session_id="QS_TEST",
        scenario_name="LIVE_BUTTON_MAPPING",
        raw_events=[],
        timeline_rows=rows,
        user_answers={},
        live_signals=live_signals,
        expected_channel=77,
    )

    assert summary.overall_status == StepStatus.PASS
    assert analyzer_result.overall_status == "PASS"
    assert metadata_row.user_answer == "77"
    assert metadata_row.status == StepStatus.PASS
