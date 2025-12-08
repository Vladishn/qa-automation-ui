from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "regression_report.py"
spec = importlib.util.spec_from_file_location("regression_report_module", MODULE_PATH)
regression_report = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(regression_report)  # type: ignore[attr-defined]


def _question_step(name: str, answer: str = "yes", status: str = "PASS") -> Dict[str, Any]:
    return {
        "name": name,
        "label": name.replace("_", " ").title(),
        "status": status,
        "user_answer": answer,
        "details": {
            "answer": answer,
        },
    }


def _analysis_summary(details: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": "analysis_summary",
        "label": "Scenario summary",
        "status": details.get("status", "PASS"),
        "details": details,
    }


def _build_lines(data: Dict[str, Any]) -> List[str]:
    return regression_report.build_report_lines(data, source_path=Path("/tmp/session.json"))


def test_regression_report_tv_autosync_includes_tester_and_log_sections_for_brand_mismatch() -> None:
    data = {
        "session": {
            "session_id": "QS_TEST",
            "scenario_name": "TV_AUTO_SYNC",
            "overall_status": "FAIL",
            "has_failure": True,
            "brand_mismatch": True,
            "brand_status": "INCOMPATIBILITY",
            "tv_brand_user": "LG",
            "tv_brand_log": "Samsung",
            "has_volume_issue": False,
            "has_osd_issue": False,
            "analysis_text": "TV auto-sync failed: TV brand seen by tester does not match logs.",
        },
        "timeline": [
            _question_step("question_tv_volume_changed"),
            _question_step("question_tv_osd_seen"),
            _question_step("question_pairing_screen_seen"),
            _question_step("question_tv_brand_ui"),
            _analysis_summary(
                {
                    "analysis": "TV auto-sync failed: TV brand seen by tester does not match logs.",
                    "tester_verdict": "PASS",
                    "log_verdict": "PASS",
                    "telemetry_state": "TV_CONTROL",
                    "conflict_tester_vs_logs": False,
                    "failed_steps": ["question_tv_brand_ui"],
                }
            ),
        ],
    }

    lines = _build_lines(data)
    rendered = "\n".join(lines)

    assert "Tester verdict:" in rendered
    assert "Log / Telemetry verdict:" in rendered
    assert "Conflicts:" in rendered
    assert "Reason: Brand mismatch between tester and logs." in rendered


def test_regression_report_tv_autosync_inconclusive_pass_highlights_logs() -> None:
    data = {
        "session": {
            "session_id": "QS_PASS",
            "scenario_name": "TV_AUTO_SYNC",
            "overall_status": "PASS",
            "has_failure": False,
            "brand_mismatch": False,
            "tv_brand_user": "LG",
            "tv_brand_log": "LG",
            "has_volume_issue": False,
            "has_osd_issue": False,
            "analysis_text": "TV auto-sync functional criteria passed (tester confirmed volume, OSD, and pairing). Telemetry probe was inconclusive – no TV responses observed.",
        },
        "timeline": [
            _question_step("question_tv_volume_changed"),
            _question_step("question_tv_osd_seen"),
            _question_step("question_pairing_screen_seen"),
            _analysis_summary(
                {
                    "analysis": "TV auto-sync functional criteria passed...",
                    "tester_verdict": "PASS",
                    "log_verdict": "INCONCLUSIVE",
                    "telemetry_state": "UNKNOWN",
                    "conflict_tester_vs_logs": False,
                    "log_failure_reason": None,
                    "autosync_started": False,
                    "autosync_success": False,
                    "evidence": {
                        "tv_volume_events": False,
                        "tv_osd_events": False,
                        "volume_probe_state": "UNKNOWN",
                        "volume_probe_confidence": 0.2,
                    },
                }
            ),
        ],
    }

    lines = _build_lines(data)
    rendered = "\n".join(lines)

    assert "Telemetry/log verdict: INCONCLUSIVE – relying on tester answers." in rendered
    assert "Conflicts:" in rendered
    assert "Logs/telemetry inconclusive; relying on tester answers." in rendered
    assert "Evidence highlights:" in rendered
