from __future__ import annotations

from typing import List, Set

from backend.quickset_timeline_analyzer import (
    StepRow,
    StepStatus,
    LogEvidence,
    _build_session_summary,
)


def _build_rows(rows: List[StepRow]) -> List[StepRow]:
    # helper to ensure we always include analysis summary at the end
    names = {row.name for row in rows}
    if "analysis_summary" not in names:
        rows.append(
            StepRow(
                name="analysis_summary",
                label="Scenario summary",
                status=StepStatus.INFO,
                details={},
            )
        )
    return rows


def _run_summary(rows: List[StepRow], log_evidence: LogEvidence, log_brand: str | None = None) -> tuple:
    timeline = _build_rows(rows)
    missing: Set[str] = set()
    summary, analyzer_result = _build_session_summary(
        session_id="QS_TEST",
        scenario_name="TV_AUTO_SYNC",
        raw_events=[],
        timeline_rows=timeline,
        log_brand=log_brand,
        missing_critical=missing,
        log_evidence=log_evidence,
    )
    return summary, analyzer_result


def test_tv_auto_sync_brand_mismatch_is_fail() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
            details={"volume_probe_detection_state": "tv_control"},
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.FAIL,
            user_answer="dhshkdhs",
            details={
                "tv_brand_user": "dhshkdhs",
                "tv_brand_log": "LG",
                "brand_mismatch": True,
            },
        ),
    ]
    log_evidence = LogEvidence(autosync_started=True, autosync_success=True, osd_tv=True, volume_source="TV")

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="LG")

    assert summary.overall_status == StepStatus.FAIL
    assert summary.has_failure is True
    assert summary.brand_mismatch is True
    assert summary.has_volume_issue is False
    assert summary.has_osd_issue is False
    assert summary.brand_status == "INCOMPATIBILITY"
    assert summary.analysis_text.startswith("TV auto-sync failed: TV brand seen by tester does not match logs.")
    assert analyzer_result.failure_insights  # still reports mismatch insight if needed


def test_tv_auto_sync_probe_unknown_but_tester_pass_is_pass() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
            details={
                "volume_probe_detection_state": "unknown",
                "volume_probe_confidence": 0.2,
            },
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="Lg",
            details={
                "tv_brand_user": "Lg",
                "tv_brand_log": None,
                "brand_mismatch": False,
            },
        ),
        StepRow(
            name="volume_probe_result",
            label="Volume probe result",
            status=StepStatus.INFO,
            details={
                "volume_source": "TV",
                "confidence": 0.8,
            },
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=True,
        autosync_success=True,
        osd_tv=False,
        osd_stb=False,
        volume_source_history=["TV", "TV"],
        tv_config_seen=True,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand=None)

    assert summary.overall_status == StepStatus.PASS
    assert summary.has_failure is False
    assert summary.brand_status == "OK"
    assert summary.volume_status == "UNKNOWN"
    assert summary.osd_status == "UNKNOWN"
    assert summary.has_volume_issue is False
    assert summary.has_osd_issue is False
    assert summary.analysis_text.startswith("TV auto-sync functional criteria passed")

    insight_codes = {ins.code: ins for ins in analyzer_result.failure_insights}
    assert "volume_probe_inconclusive" in insight_codes
    assert insight_codes["volume_probe_inconclusive"].category == "tooling"
    assert "probe_detected_stb_control" not in insight_codes


def test_tv_auto_sync_autosync_failed_but_telemetry_unknown_is_tooling() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="LG",
            details={"tv_brand_user": "LG", "tv_brand_log": "LG"},
        ),
        StepRow(
            name="volume_probe_result",
            label="Volume probe result",
            status=StepStatus.INFO,
            details={
                "volume_source": "UNKNOWN",
                "confidence": 0.0,
            },
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=True,
        autosync_success=False,
        tv_volume_events=False,
        tv_osd_events=False,
        volume_source_history=["UNKNOWN"],
        tv_config_seen=True,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="LG")

    assert summary.overall_status == StepStatus.FAIL
    assert summary.analysis_text.startswith("Auto-sync did not complete successfully in logs.")
    assert summary.volume_status == "UNKNOWN"
    assert summary.osd_status == "UNKNOWN"
    assert summary.has_volume_issue is False
    assert summary.has_osd_issue is False
    insight_codes = {ins.code: ins for ins in analyzer_result.failure_insights}
    assert "autosync_not_completed" in insight_codes
    assert insight_codes["autosync_not_completed"].category == "functional"
    assert insight_codes.get("volume_probe_inconclusive") is not None
    assert insight_codes["volume_probe_inconclusive"].category == "tooling"


def test_tv_auto_sync_probe_stb_control_confident_is_fail() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
            details={
                "volume_probe_detection_state": "stb_control",
                "volume_probe_confidence": 0.9,
            },
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="LG",
            details={"tv_brand_user": "LG", "tv_brand_log": "LG"},
        ),
        StepRow(
            name="volume_probe_result",
            label="Volume probe result",
            status=StepStatus.INFO,
            details={
                "volume_source": "STB",
                "confidence": 0.9,
            },
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=True,
        autosync_success=True,
        osd_tv=False,
        osd_stb=True,
        volume_source="STB",
        volume_source_history=["STB", "STB", "STB"],
        stb_volume_events=True,
        tv_config_seen=False,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="LG")

    assert summary.overall_status == StepStatus.FAIL
    assert summary.has_failure is True
    assert summary.volume_status == "INCOMPATIBILITY"
    assert summary.osd_status == "INCOMPATIBILITY"
    assert summary.has_volume_issue is True
    assert summary.has_osd_issue is True
    assert "telemetry indicates STB" in summary.analysis_text
    stb_insight = next(ins for ins in analyzer_result.failure_insights if ins.code == "probe_detected_stb_control")
    assert stb_insight.category == "functional"
    assert all(ins.code != "volume_probe_inconclusive" for ins in analyzer_result.failure_insights)


def test_tv_auto_sync_good_log_sets_ok_status() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="Samsung",
            details={"tv_brand_user": "Samsung", "tv_brand_log": "Samsung"},
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=True,
        autosync_success=True,
        tv_volume_events=True,
        tv_osd_events=True,
        volume_source_history=["STB", "TV", "TV"],
        tv_config_seen=True,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="Samsung")

    assert summary.overall_status == StepStatus.PASS
    assert summary.volume_status == "OK"
    assert summary.osd_status == "OK"
    assert summary.has_volume_issue is False
    assert summary.has_osd_issue is False
    assert all(ins.code != "probe_detected_stb_control" for ins in analyzer_result.failure_insights)


def test_tv_auto_sync_tv_config_cleared_sets_incompatibility_and_insight() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="Philips",
            details={"tv_brand_user": "Philips", "tv_brand_log": "Philips"},
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=True,
        autosync_success=False,
        tv_volume_events=False,
        tv_osd_events=False,
        volume_source_history=["TV", "STB", "STB"],
        tv_config_seen=True,
        tv_config_cleared_during_run=True,
        stb_volume_events=True,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="Philips")

    assert summary.overall_status == StepStatus.FAIL
    assert summary.volume_status == "INCOMPATIBILITY"
    assert summary.osd_status == "INCOMPATIBILITY"
    assert summary.has_volume_issue is True
    assert summary.has_osd_issue is True
    insight_codes = {ins.code for ins in analyzer_result.failure_insights}
    assert "tv_config_cleared_during_run" in insight_codes


def test_tv_auto_sync_mixed_signals_result_in_unknown() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="LG",
            details={"tv_brand_user": "LG", "tv_brand_log": "LG"},
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=True,
        autosync_success=True,
        tv_volume_events=False,
        tv_osd_events=False,
        volume_source_history=["STB", "TV", "STB", "TV"],
        tv_config_seen=False,
        stb_volume_events=True,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="LG")

    assert summary.overall_status == StepStatus.PASS
    assert summary.volume_status == "UNKNOWN"
    assert summary.osd_status == "UNKNOWN"
    assert summary.has_volume_issue is False
    assert summary.has_osd_issue is False
    tool_insight = next(ins for ins in analyzer_result.failure_insights if ins.code == "volume_probe_inconclusive")
    assert tool_insight.category == "tooling"


def test_tv_auto_sync_autosync_started_inferred_from_probe_signals() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
            details={
                "volume_probe_detection_state": "stb_control",
                "volume_probe_confidence": 0.95,
            },
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="Samsung",
            details={"tv_brand_user": "Samsung", "tv_brand_log": "Samsung"},
        ),
        StepRow(
            name="volume_probe_result",
            label="Volume probe result",
            status=StepStatus.INFO,
            details={
                "volume_source": "STB",
                "confidence": 0.9,
            },
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=False,
        autosync_success=False,
        osd_tv=False,
        osd_stb=True,
        volume_source=None,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="Samsung")

    assert summary.overall_status == StepStatus.FAIL
    assert "Auto-sync was not triggered" not in summary.analysis_text
    assert any(ins.code == "probe_detected_stb_control" for ins in analyzer_result.failure_insights)
    assert all(ins.code != "autosync_not_started" for ins in analyzer_result.failure_insights)


def test_tv_auto_sync_started_but_not_completed_emits_not_completed_insight() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
            details={"volume_probe_detection_state": "unknown"},
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="LG",
            details={"tv_brand_user": "LG", "tv_brand_log": "LG"},
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=True,
        autosync_success=False,
        osd_tv=False,
        osd_stb=False,
        volume_source=None,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="LG")

    assert summary.overall_status == StepStatus.FAIL
    assert "did not complete" in summary.analysis_text
    assert any(ins.code == "autosync_not_completed" for ins in analyzer_result.failure_insights)
    assert all(ins.code != "autosync_not_started" for ins in analyzer_result.failure_insights)


def test_tv_auto_sync_reports_not_started_when_no_signals() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.PASS,
            user_answer="yes",
            details={},
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
            details={},
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
            details={},
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="LG",
            details={
                "tv_brand_user": "LG",
                "tv_brand_log": None,
                "brand_mismatch": False,
            },
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=False,
        autosync_success=False,
        osd_tv=False,
        osd_stb=False,
        volume_source=None,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand=None)

    assert summary.overall_status == StepStatus.FAIL
    assert "Auto-sync was not triggered in logs." in summary.analysis_text
    assert any(ins.code == "autosync_not_started" for ins in analyzer_result.failure_insights)


def test_tv_auto_sync_tester_no_volume_forces_fail() -> None:
    rows = [
        StepRow(
            name="question_tv_volume_changed",
            label="TV volume changed",
            status=StepStatus.FAIL,
            user_answer="no",
        ),
        StepRow(
            name="question_tv_osd_seen",
            label="TV OSD seen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_pairing_screen_seen",
            label="Pairing screen",
            status=StepStatus.PASS,
            user_answer="yes",
        ),
        StepRow(
            name="question_tv_brand_ui",
            label="TV brand (UI vs log)",
            status=StepStatus.PASS,
            user_answer="LG",
            details={"tv_brand_user": "LG", "tv_brand_log": "LG"},
        ),
    ]
    log_evidence = LogEvidence(
        autosync_started=True,
        autosync_success=False,
        osd_tv=False,
        osd_stb=False,
        volume_source=None,
    )

    summary, analyzer_result = _run_summary(rows, log_evidence, log_brand="LG")

    assert summary.overall_status == StepStatus.FAIL
    assert summary.has_failure is True
    assert summary.volume_status == "FAIL"
    assert summary.has_volume_issue is True
    assert summary.analysis_text.startswith("TV auto-sync failed: tester did not observe TV volume change.")
    assert any(ins.code == "tester_saw_no_volume_change" for ins in analyzer_result.failure_insights)
