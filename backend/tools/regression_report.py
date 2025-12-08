import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional

# ROOT_DIR = backend (הקובץ נמצא ב-backend/tools)
ROOT_DIR = Path(__file__).resolve().parents[1]
REGRESSION_DIR = ROOT_DIR / "artifacts" / "regression"
EVIDENCE_KEYS_ORDER: Iterable[str] = (
    "tv_volume_events",
    "tv_osd_events",
    "ir_commands_sent",
    "cec_events_detected",
    "volume_probe_state",
    "volume_probe_confidence",
    "volume_probe_detection_state",
    "issue_confirmed_by_probe",
    "tv_brand_detected",
)


def norm_status(value: Any) -> str:
    """Normalize status string to lower-case."""
    return (value or "").lower()


def _extract_step(timeline: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    return next((row for row in timeline if row.get("name") == name), None)


def _format_step_answer(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return "N/A"
    answer = row.get("user_answer") or (row.get("details") or {}).get("answer")
    if not answer:
        answer = "UNKNOWN"
    status = row.get("status") or "UNKNOWN"
    return f"{str(answer).upper()} (step status: {status})"


def _derive_analysis_reason(session: Dict[str, Any], summary_details: Dict[str, Any]) -> Optional[str]:
    overall = (session.get("overall_status") or "").upper()
    if overall != "FAIL":
        if summary_details.get("log_verdict") == "INCONCLUSIVE":
            return "Telemetry/log verdict: INCONCLUSIVE – relying on tester answers."
        return None

    tester_verdict = (summary_details.get("tester_verdict") or "").upper()
    if tester_verdict == "FAIL":
        return "Reason: Tester verdict indicates a failure."

    if session.get("brand_status") == "INCOMPATIBILITY" or session.get("brand_mismatch"):
        return "Reason: Brand mismatch between tester and logs."

    if (summary_details.get("log_verdict") or "").upper() == "FAIL":
        failure_reason = summary_details.get("log_failure_reason")
        suffix = f" ({failure_reason})" if failure_reason else ""
        return f"Reason: Log/telemetry evidence indicates a failure{suffix}."

    return None


def _format_tv_autosync_sections(
    timeline: List[Dict[str, Any]],
    summary_details: Dict[str, Any],
) -> List[str]:
    lines: List[str] = []
    lines.append("Tester verdict:")
    lines.append(f"  Overall tester verdict : {summary_details.get('tester_verdict', 'UNKNOWN')}")
    for step_name, label in (
        ("question_tv_volume_changed", "TV volume changed"),
        ("question_tv_osd_seen", "TV OSD seen"),
        ("question_pairing_screen_seen", "Pairing screen seen"),
        ("question_tv_brand_ui", "TV brand (UI)"),
    ):
        step = _extract_step(timeline, step_name)
        lines.append(f"  {label:<23}: {_format_step_answer(step)}")
    lines.append("")

    log_verdict = summary_details.get("log_verdict", "UNKNOWN")
    telemetry_state = summary_details.get("telemetry_state", "UNKNOWN")
    log_reason = summary_details.get("log_failure_reason")
    lines.append("Log / Telemetry verdict:")
    lines.append(f"  Log verdict      : {log_verdict}")
    lines.append(f"  Telemetry state  : {telemetry_state}")
    if log_reason:
        lines.append(f"  Log reason       : {log_reason}")
    autosync_started = summary_details.get("autosync_started")
    if autosync_started is not None:
        lines.append(f"  Auto-sync started: {autosync_started}")
    autosync_success = summary_details.get("autosync_success")
    if autosync_success is not None:
        lines.append(f"  Auto-sync success: {autosync_success}")
    evidence = summary_details.get("evidence") or {}
    if evidence:
        lines.append("  Evidence highlights:")
        for key in EVIDENCE_KEYS_ORDER:
            if key in evidence:
                lines.append(f"    - {key}: {evidence[key]}")
    lines.append("")

    conflict = summary_details.get("conflict_tester_vs_logs")
    lines.append("Conflicts:")
    lines.append(f"  Tester vs logs/telemetry: {conflict if conflict is not None else 'N/A'}")
    if conflict:
        conflict_detail = log_reason or summary_details.get("analysis")
        if conflict_detail:
            lines.append(f"    Details: {conflict_detail}")
    elif log_verdict == "INCONCLUSIVE":
        lines.append("    Details: Logs/telemetry inconclusive; relying on tester answers.")
    lines.append("")
    return lines


def build_report_lines(data: Dict[str, Any], source_path: Optional[Path] = None) -> List[str]:
    session = data.get("session", {})
    timeline = data.get("timeline", [])
    has_failure = data.get("has_failure")
    if has_failure is None:
        has_failure = session.get("has_failure")

    sid = session.get("session_id") or session.get("id")
    scenario = session.get("scenario_name") or session.get("scenario")

    session_id = sid or data.get("session_id") or "UNKNOWN"
    tester = session.get("tester_id") or session.get("tester")
    stb_ip = session.get("stb_ip")
    overall_status = session.get("overall_status")

    brand_mismatch = session.get("brand_mismatch")
    tv_brand_user = session.get("tv_brand_user")
    tv_brand_log = session.get("tv_brand_log")
    has_volume_issue = session.get("has_volume_issue")
    has_osd_issue = session.get("has_osd_issue")
    analysis_text = session.get("analysis_text")

    failed_events = [e for e in timeline if norm_status(e.get("status")) == "fail"]

    analysis_event = _extract_step(timeline, "analysis_summary")
    summary_details = (analysis_event or {}).get("details") or {}
    failed_from_summary = summary_details.get("failed_steps") or []

    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("REGRESSION REPORT")
    lines.append("=" * 60)
    lines.append(f"Session ID   : {session_id}")
    if scenario:
        lines.append(f"Scenario     : {scenario}")
    if tester:
        lines.append(f"Tester       : {tester}")
    if stb_ip:
        lines.append(f"STB IP       : {stb_ip}")
    if overall_status:
        lines.append(f"Overall      : {overall_status}")
    if has_failure is not None:
        lines.append(f"Has failure  : {has_failure}")
    lines.append("")

    lines.append("TV / Brand:")
    if tv_brand_user or tv_brand_log:
        lines.append(f"  User brand : {tv_brand_user}")
        lines.append(f"  Log brand  : {tv_brand_log}")
    if brand_mismatch is not None:
        lines.append(f"  Mismatch   : {brand_mismatch}")
    lines.append("")

    lines.append("Volume / OSD:")
    if has_volume_issue is not None:
        lines.append(f"  Volume issue: {has_volume_issue}")
    if has_osd_issue is not None:
        lines.append(f"  OSD issue   : {has_osd_issue}")
    lines.append("")

    if analysis_text:
        lines.append("Analysis:")
        lines.append(f"  {analysis_text}")
        reason_line = _derive_analysis_reason(session, summary_details)
        if reason_line:
            lines.append(f"  {reason_line}")
        lines.append("")

    if scenario == "TV_AUTO_SYNC":
        lines.extend(_format_tv_autosync_sections(timeline, summary_details))

    if failed_events:
        lines.append("Failed steps (from timeline):")
        for idx, e in enumerate(failed_events, start=1):
            name = e.get("name") or e.get("label") or f"step_{idx}"
            label = e.get("label") or ""
            details = e.get("details") or {}
            reason = (
                details.get("probe_mismatch_reason")
                or details.get("mismatch_reason")
                or details.get("analysis")
                or details.get("error")
                or ""
            )
            disp = name
            if label and label != name:
                disp += f" ({label})"
            lines.append(f"  {idx}. {disp}")
            if reason:
                lines.append(f"       - {reason}")
        lines.append("")

    if failed_from_summary:
        lines.append("Failed steps (from summary.failed_steps):")
        for idx, name in enumerate(failed_from_summary, start=1):
            lines.append(f"  {idx}. {name}")
        lines.append("")

    if not failed_events and not failed_from_summary:
        lines.append("No failed steps recorded.")
        lines.append("")

    lines.append("Source file:")
    if source_path:
        lines.append(f"  {source_path}")
    else:
        lines.append("  (in-memory data)")

    return lines


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: regression_report.py SESSION_ID")
        raise SystemExit(1)

    sid = sys.argv[1]
    path = REGRESSION_DIR / f"session_{sid}.json"

    if not path.exists():
        print(f"[ERROR] Snapshot not found: {path}")
        raise SystemExit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    lines = build_report_lines(data, source_path=path)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
