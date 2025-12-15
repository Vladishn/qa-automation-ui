# backend/quickset_timeline_analyzer.py

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Literal
from datetime import datetime
import re
from pathlib import Path

from .analyzers.base import AnalyzerResult, FailureInsight
from .quickset_log_parser import QuicksetLogSignals, parse_quickset_logs
from .live_button_log_parser import LiveButtonSignals, parse_live_button_logs
from .scenario_enums import ScenarioName

# QuickSet log parsing relies on QuicksetLogSignals/parse_quickset_logs as the
# single source of truth for TV_AUTO_SYNC log evidence.


class StepStatus(str, Enum):
    INFO = "INFO"
    PASS = "PASS"
    FAIL = "FAIL"
    AWAITING_INPUT = "AWAITING_INPUT"
    INCONCLUSIVE = "INCONCLUSIVE"


MetricStatus = Literal["OK", "FAIL", "INCOMPATIBILITY", "NOT_EVALUATED"]
TelemetryState = Literal["TV_CONTROL_CONFIDENT", "STB_CONTROL_CONFIDENT", "UNKNOWN"]

WHITELISTED_STEPS = {
    "question_manual_trigger",
    "question_tv_volume_changed",
    "question_tv_osd_seen",
    "question_pairing_screen_seen",
    "question_tv_brand_ui",
    "question_notes",
    "question_expected_channel",
    "live_expected_channel",
    "device_focus_precheck",
    "test_started",
    "configure_live_mapping",
    "phase1_live_press",
    "phase2_kill_and_relaunch",
    "phase3_reboot_persist",
    "test_completed",
    "analysis_summary",
}

CRITICAL_STEPS = {
    "question_tv_volume_changed",
    "question_tv_osd_seen",
    "question_pairing_screen_seen",
    "question_tv_brand_ui",
}

ROOT_CAUSE_METADATA: Dict[str, Dict[str, Any]] = {
    "tester_saw_no_volume_change": {
        "category": "functional",
        "severity": "high",
        "title": "No TV volume change observed",
        "default_description": "Tester did not observe TV volume change.",
        "recommendations": [
            "Ensure STB IR blaster is pointing directly at the TV.",
            "Reduce distance between STB and TV.",
        ],
        "evidence_keys": ["volume_probe_state", "tv_volume_events"],
    },
    "tester_saw_no_osd": {
        "category": "functional",
        "severity": "high",
        "title": "TV OSD not seen",
        "default_description": "Tester did not observe TV OSD.",
        "recommendations": [
            "Ensure STB IR blaster is pointing at the TV.",
            "Retry Auto-Sync after adjusting IR alignment.",
        ],
        "evidence_keys": ["tv_osd_events"],
    },
    "volume_probe_inconclusive": {
        "category": "tooling",
        "severity": "medium",
        "title": "Volume probe inconclusive",
        "default_description": "Volume probe returned UNKNOWN; no evidence of TV control.",
        "recommendations": [
            "Reduce distance between STB and TV.",
            "Retry TV auto-sync after adjusting IR alignment.",
        ],
        "evidence_keys": ["volume_probe_state"],
    },
    "ir_no_effect": {
        "category": "device",
        "severity": "high",
        "title": "IR commands produced no TV response",
        "default_description": "No TV response to IR commands was detected.",
        "recommendations": [
            "Ensure STB IR blaster is pointing directly at the TV.",
            "Retry Auto-Sync after adjusting IR alignment.",
        ],
        "evidence_keys": ["ir_commands_sent", "tv_volume_events", "tv_osd_events"],
    },
    "ruleset_ok_but_no_control": {
        "category": "integration",
        "severity": "medium",
        "title": "Ruleset succeeded but control missing",
        "default_description": "QuickSet ruleset reported success, but no TV control was confirmed.",
        "recommendations": [
            "Re-run TV auto-sync after verifying IR alignment.",
            "Check hotel mode.",
        ],
        "evidence_keys": ["tv_volume_events", "tv_osd_events"],
    },
    "cec_inactive": {
        "category": "integration",
        "severity": "medium",
        "title": "HDMI-CEC inactive",
        "default_description": "HDMI-CEC events were not detected; CEC might be disabled.",
        "recommendations": [
            "Enable HDMI-CEC on the TV.",
        ],
        "evidence_keys": ["cec_events_detected"],
    },
    "no_tv_response": {
        "category": "functional",
        "severity": "critical",
        "title": "No TV responses observed",
        "default_description": "Tester reported no TV responses and logs lacked TV control evidence.",
        "recommendations": [
            "Ensure STB IR blaster is pointing directly at the TV.",
            "Reduce distance between STB and TV.",
            "Retry Auto-Sync after adjusting IR alignment.",
        ],
        "evidence_keys": ["tv_volume_events", "tv_osd_events"],
    },
    "probe_detected_stb_control": {
        "category": "functional",
        "severity": "high",
        "title": "Probe detected STB control",
        "default_description": "Telemetry probe indicates STB controls volume/OSD despite tester reporting TV control.",
        "recommendations": [
            "Verify TV remote pairing and ensure TV volume control is enabled.",
            "Re-run TV auto-sync to confirm TV control.",
        ],
        "evidence_keys": ["volume_probe_state", "volume_probe_confidence"],
    },
    "brand_mismatch_detected": {
        "category": "integration",
        "severity": "medium",
        "title": "Brand mismatch between tester and logs",
        "default_description": "Tester reported a different TV brand than logs detected.",
        "recommendations": [
            "Re-run TV auto-sync and verify TV brand selection.",
        ],
        "evidence_keys": ["tv_brand_detected"],
    },
    "autosync_not_started": {
        "category": "functional",
        "severity": "high",
        "title": "TV auto-sync not triggered",
        "default_description": "QuickSet logs do not show TV auto-sync starting.",
        "recommendations": [
            "Restart the TV auto-sync flow from the STB.",
            "Verify connectivity between the STB and QuickSet services.",
        ],
        "evidence_keys": [],
    },
    "autosync_not_completed": {
        "category": "functional",
        "severity": "high",
        "title": "TV auto-sync did not complete",
        "default_description": "QuickSet logs show TV auto-sync started but not completed successfully.",
        "recommendations": [
            "Retry TV auto-sync and review QuickSet error logs.",
        ],
        "evidence_keys": [],
    },
    "autosync_logs_inconclusive": {
        "category": "tooling",
        "severity": "low",
        "title": "Logs inconclusive for auto-sync",
        "default_description": "Logs did not contain QuickSet or volume/OSD signals; relying on tester verdict.",
        "recommendations": [
            "Retry TV auto-sync and ensure device logs include QuickSet output.",
        ],
        "evidence_keys": [],
    },
    "tv_config_cleared_during_run": {
        "category": "integration",
        "severity": "medium",
        "title": "QuickSet removed TV configuration",
        "default_description": "QuickSet removed TV configuration during the run, so control reverted to STB.",
        "recommendations": [
            "Re-run TV auto-sync and verify TV configuration persists.",
        ],
        "evidence_keys": ["tv_config_events", "volume_source_history"],
    },
    "live_button_wrong_channel": {
        "category": "functional",
        "severity": "high",
        "title": "Live button mapped to wrong channel",
        "default_description": "Logs show the Live button opened PartnerTV+ on an unexpected channel.",
        "recommendations": [
            "Reconfigure the Live button mapping to the desired channel.",
            "Verify the Live button customization settings in PartnerTV+.",
        ],
        "evidence_keys": ["live_button_signals"],
    },
    "live_button_logs_inconclusive": {
        "category": "tooling",
        "severity": "low",
        "title": "Logs inconclusive for Live button",
        "default_description": "Logs did not contain enough Live-button signals; relying on tester verdict.",
        "recommendations": [
            "Retry the Live button test and ensure logging captures the key press and app launch.",
        ],
        "evidence_keys": ["live_button_signals"],
    },
    "live_button_tester_failure": {
        "category": "functional",
        "severity": "medium",
        "title": "Tester reported Live button failure",
        "default_description": "Tester reported that the Live button did not open PartnerTV+ on the expected channel.",
        "recommendations": [
            "Re-run the Live button mapping flow and verify the configured channel.",
        ],
        "evidence_keys": ["live_button_signals"],
    },
    "live_button_logs_inconclusive_all_phases": {
        "category": "tooling",
        "severity": "low",
        "title": "Live button logs inconclusive",
        "default_description": "Live button logs did not include configuration or press signals.",
        "recommendations": [
            "Verify logcat capture for the session and rerun the Live button automation.",
        ],
        "evidence_keys": ["live_button_signals"],
    },
    "live_mapping_not_configured": {
        "category": "functional",
        "severity": "high",
        "title": "Live button mapping not configured",
        "default_description": "Logs did not confirm that the Live button mapping was saved.",
        "recommendations": [
            "Reconfigure the Live button mapping in Settings and re-run the test.",
        ],
        "evidence_keys": ["live_button_signals"],
    },
    "live_mapping_screen_not_reached": {
        "category": "functional",
        "severity": "high",
        "title": "Live channel settings screen not reached",
        "default_description": "Automation could not reach the Live channel settings UI.",
        "recommendations": [
            "Re-run the scenario and ensure the device exits third-party apps before opening Settings.",
        ],
        "evidence_keys": ["live_button_signals"],
    },
}

for idx, phase_label in enumerate(("Initial Live press", "After force-stop", "After reboot"), start=1):
    ROOT_CAUSE_METADATA[f"live_button_wrong_channel_phase{idx}"] = {
        "category": "functional",
        "severity": "high",
        "title": f"Live button wrong channel – phase {idx}",
        "default_description": f"{phase_label}: PartnerTV+ opened on the wrong channel.",
        "recommendations": [
            "Reconfigure the Live button mapping to the desired channel.",
            "Verify PartnerTV+ GUIDE intent parameters.",
        ],
        "evidence_keys": ["live_button_signals"],
    }
    ROOT_CAUSE_METADATA[f"live_button_no_launch_phase{idx}"] = {
        "category": "functional",
        "severity": "high",
        "title": f"Live button failed to launch – phase {idx}",
        "default_description": f"{phase_label}: Live key press did not launch PartnerTV+.",
        "recommendations": [
            "Check that PartnerTV+ is installed and automation can launch it.",
            "Confirm the Live key navigation path is correct.",
        ],
        "evidence_keys": ["live_button_signals"],
    }
    ROOT_CAUSE_METADATA[f"live_button_logs_inconclusive_phase{idx}"] = {
        "category": "tooling",
        "severity": "low",
        "title": f"Live button logs inconclusive – phase {idx}",
        "default_description": f"{phase_label}: Logs did not capture enough evidence.",
        "recommendations": [
            "Re-run the scenario with log capture enabled and verify QA_LIVE markers.",
        ],
        "evidence_keys": ["live_button_signals"],
    }

TV_AUTO_SYNC_MARKERS = {
    "question_tv_volume_changed",
    "question_tv_osd_seen",
    "question_pairing_screen_seen",
    "question_tv_brand_ui",
    "question_manual_trigger",
    "question_notes",
    "tester_trigger_quickset",
    "tv_metadata",
    "volume_probe_result",
    "volume_probe_prompt",
}

YES_ANSWERS = {"yes", "כן", "y", "true", "1"}
NO_ANSWERS = {"no", "לא", "n", "false", "0"}

STATE_SNAPSHOT_STEP_NAME = "state_snapshot"
STATE_LABEL_BEFORE = "before_autosync"
STATE_LABEL_AFTER = "after_autosync"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIVE_LOG_DIR = PROJECT_ROOT / "artifacts" / "live_logs"
LOG_DIR_CANDIDATES = [
    PROJECT_ROOT / "artifacts" / "quickset_logs",
    PROJECT_ROOT / "artifacts" / "logs",
]
LIVE_LOG_SNIPPET_PATTERNS = [
    re.compile(r"QA_LIVE", re.IGNORECASE),
    re.compile(r"PartnerTV\+\s+GUIDE intent sent", re.IGNORECASE),
    re.compile(r"GlobalKeyInterceptor", re.IGNORECASE),
]
PROBE_EVENT_NAMES = {
    "volume_probe_result",
    "volume_behavior_probe",
}
IGNORED_VOLUME_EVENTS = {
    "state_snapshot",
    "log_analysis_start",
    "log_analysis_complete",
    "logcat_capture_start",
    "logcat_capture_stop",
}
VOLUME_SIGNAL_KEYS = (
    "volume_source",
    "tv_volume_source",
    "nes_volume_source",
    "current_volume_source",
    "volume_changed",
    "tv_volume_changed",
    "volume_probe_changed",
    "volume_keys_control_tv",
    "osd_tv",
    "osd_stb",
    "osd_source",
)


@dataclass
class SnapshotState:
    label: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def current_volume_source(self) -> Optional[str]:
        return self.raw.get("current_volume_source")

    @property
    def tv_device_name(self) -> Optional[str]:
        return self.raw.get("tv_device_name")


@dataclass
class StepRow:
    name: str
    label: str
    status: StepStatus
    timestamp: Optional[str] = None
    question: Optional[str] = None
    user_answer: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class SessionSummary:
    session_id: str
    scenario_name: str
    started_at: Optional[str]
    finished_at: Optional[str]
    overall_status: StepStatus
    brand_mismatch: bool
    tv_brand_user: Optional[str]
    tv_brand_log: Optional[str]
    has_volume_issue: bool
    has_osd_issue: bool
    notes: Optional[str]
    analysis_text: str
    has_failure: bool
    brand_status: MetricStatus
    volume_status: MetricStatus
    osd_status: MetricStatus

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["overall_status"] = self.overall_status.value
        return data


@dataclass
class LogEvidence:
    autosync_started: bool = False
    autosync_success: bool = False
    autosync_errors: List[str] = field(default_factory=list)
    osd_tv: bool = False
    osd_stb: bool = False
    tv_volume_events: bool = False
    tv_osd_events: bool = False
    volume_source: Optional[str] = None
    log_brand: Optional[str] = None
    log_text: str = ""
    ir_commands_sent: bool = False
    cec_events_detected: bool = False
    cec_inactive: bool = False
    quickset_seen: bool = False
    volume_source_history: List[str] = field(default_factory=list)
    tv_config_seen: bool = False
    tv_config_cleared_during_run: bool = False
    tv_config_events: List[str] = field(default_factory=list)
    stb_volume_events: bool = False
    log_signals: Optional[QuicksetLogSignals] = None


@dataclass
class AutosyncLogVerdictInfo:
    autosync_started: bool
    autosync_success: bool
    autosync_failed: bool
    logs_inconclusive: bool


def load_logcat_text(session_id: str, scenario_name: Optional[str] = None) -> str:
    scenario_slug = (scenario_name or "").strip().lower()
    suffixes: List[str] = []
    if scenario_slug:
        suffixes.append(scenario_slug)
    suffixes.extend(["tv_auto_sync", "live_button_mapping", ""])
    candidates: List[Path] = []
    for base in LOG_DIR_CANDIDATES:
        for suffix in suffixes:
            if suffix:
                candidates.append(base / session_id / f"{session_id}_{suffix}.log")
                candidates.append(base / f"{session_id}_{suffix}.log")
            else:
                candidates.append(base / session_id / f"{session_id}.log")
                candidates.append(base / f"{session_id}.log")
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="ignore")
    for base in LOG_DIR_CANDIDATES:
        if not base.exists():
            continue
        matches = sorted(base.glob(f"{session_id}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return matches[0].read_text(encoding="utf-8", errors="ignore")
        session_dir = base / session_id
        if session_dir.exists():
            matches = sorted(session_dir.glob(f"{session_id}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                return matches[0].read_text(encoding="utf-8", errors="ignore")
    return ""


def load_live_button_log_text(session_id: str) -> str:
    log_path = LIVE_LOG_DIR / f"live_{session_id}.log"
    if log_path.exists():
        return log_path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _extract_live_log_excerpt(log_text: Optional[str], session_id: Optional[str] = None) -> Tuple[str, bool]:
    if not log_text:
        return "[no live log captured]", True
    session_token = f"SESSION={session_id}" if session_id else None
    if session_token and session_token in log_text:
        idx = log_text.index(session_token)
        start = max(0, idx - 200)
        end = min(len(log_text), idx + 400)
        return log_text[start:end].strip(), False
    for pattern in LIVE_LOG_SNIPPET_PATTERNS:
        match = pattern.search(log_text)
        if match:
            start = max(0, match.start() - 200)
            end = min(len(log_text), match.end() + 400)
            return log_text[start:end].strip(), False
    snippet = log_text[:800].strip()
    if not snippet:
        snippet = "[live log captured but empty excerpt]"
    return snippet, True


def _detect_volume_source(log_text: str) -> Optional[str]:
    lower = log_text.lower()
    if re.search(r"volume[_ ]source\s*[:=]\s*tv", lower) or "volume routed to tv" in lower:
        return "TV"
    if re.search(r"volume[_ ]source\s*[:=]\s*stb", lower) or "volume routed to stb" in lower:
        return "STB"
    return None


def _detect_brand_from_log_text(log_text: str) -> Optional[str]:
    match = re.search(r"tv[_ ]brand\s*[:=]\s*([A-Za-z0-9 _-]+)", log_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"matchedbrand\s*[:=]\s*([A-Za-z0-9 _-]+)", log_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def analyze_log_evidence(
    log_text: str,
    default_brand: Optional[str],
) -> LogEvidence:
    evidence = LogEvidence(log_text=log_text)
    lower = log_text.lower()
    evidence.autosync_started = any(keyword in lower for keyword in (
        "startautosync",
        "begin tv autosync",
        "uei autosync",
        "autosync start",
    ))
    evidence.autosync_success = any(keyword in lower for keyword in (
        "autosync success",
        "tv sync complete",
        "autosync: matched",
        "autosync completed",
    ))
    evidence.osd_tv = any(keyword in lower for keyword in (
        "volume_osd_tv",
        "com.samsung.osd",
        "vendor.tv.osd",
        "tv osd",
    ))
    evidence.osd_stb = any(keyword in lower for keyword in (
        "droidlogicvolumepanel",
        "systemui volume",
        "stb osd",
        "volume panel stb",
    ))
    evidence.ir_commands_sent = any(keyword in lower for keyword in (
        "sendir",
        "sending ir",
        "ir command",
        "ir-blaster",
        "ir blaster",
        "ir tx",
    ))
    evidence.cec_events_detected = bool(
        re.search(r"\bcec[_-]?event\b", lower)
        or "hdmi-cec" in lower
        or re.search(r"\bcec:\b", lower)
        or re.search(r"\bcec\b", lower)
    )
    evidence.cec_inactive = bool(
        re.search(r"cec (?:inactive|disabled|off|not available)", lower)
    )
    evidence.volume_source = _detect_volume_source(log_text)
    log_brand_text = _detect_brand_from_log_text(log_text)
    evidence.log_brand = log_brand_text or default_brand
    return evidence


def _evaluate_autosync_from_logs(log_signals: Optional[QuicksetLogSignals]) -> AutosyncLogVerdictInfo:
    if not log_signals:
        return AutosyncLogVerdictInfo(
            autosync_started=False,
            autosync_success=False,
            autosync_failed=False,
            logs_inconclusive=True,
        )
    started = bool(log_signals.autosync_started)
    success = bool(log_signals.autosync_completed_successfully)
    failed = bool(log_signals.autosync_failed or log_signals.autosync_error_codes)
    logs_inconclusive = (
        not log_signals.quickset_seen
        and not started
        and not success
        and not log_signals.autosync_failed
        and not log_signals.autosync_error_codes
        and log_signals.tv_volume_events == 0
        and log_signals.tv_osd_events == 0
        and log_signals.stb_volume_events == 0
        and log_signals.stb_osd_events == 0
    )
    return AutosyncLogVerdictInfo(
        autosync_started=started,
        autosync_success=success,
        autosync_failed=failed,
        logs_inconclusive=logs_inconclusive,
    )


def _merge_quickset_signals(log_evidence: LogEvidence, signals: QuickSetLogSignals) -> None:
    if not signals:
        return
    log_evidence.log_signals = signals
    if signals.quickset_seen:
        log_evidence.quickset_seen = True
    if signals.tv_brand_inferred:
        log_evidence.log_brand = log_evidence.log_brand or signals.tv_brand_inferred
    if signals.autosync_started or signals.autosync_completed_successfully or signals.autosync_failed:
        log_evidence.autosync_started = True
    if signals.autosync_completed_successfully:
        log_evidence.autosync_success = True
    elif signals.autosync_failed:
        log_evidence.autosync_success = False
    if signals.autosync_error_codes:
        for err in signals.autosync_error_codes:
            cleaned = err.strip()
            if cleaned and cleaned not in log_evidence.autosync_errors:
                log_evidence.autosync_errors.append(cleaned)
        if len(log_evidence.autosync_errors) > 12:
            log_evidence.autosync_errors = log_evidence.autosync_errors[-12:]
    if signals.tv_volume_events:
        log_evidence.tv_volume_events = True
    if signals.tv_osd_events:
        log_evidence.tv_osd_events = True
        log_evidence.osd_tv = True
    if signals.stb_osd_events:
        log_evidence.osd_stb = True
    if signals.stb_volume_events:
        log_evidence.stb_volume_events = True
    if signals.volume_source_history:
        log_evidence.volume_source_history.extend(signals.volume_source_history)
        if len(log_evidence.volume_source_history) > 60:
            log_evidence.volume_source_history = log_evidence.volume_source_history[-60:]
    final_source = signals.volume_source_final
    if final_source and final_source != "UNKNOWN":
        log_evidence.volume_source = final_source
    elif (
        not log_evidence.volume_source
        and signals.volume_source_initial
        and signals.volume_source_initial != "UNKNOWN"
    ):
        log_evidence.volume_source = signals.volume_source_initial
    if signals.tv_config_events:
        for entry in signals.tv_config_events:
            if entry not in log_evidence.tv_config_events:
                log_evidence.tv_config_events.append(entry)
        if len(log_evidence.tv_config_events) > 12:
            log_evidence.tv_config_events = log_evidence.tv_config_events[-12:]
    if signals.tv_config_seen:
        log_evidence.tv_config_seen = True
    if signals.tv_config_cleared_during_run:
        log_evidence.tv_config_cleared_during_run = True


# ----------------------- PUBLIC ENTRYPOINT ----------------------- #

def build_timeline_and_summary(
    session_id: str,
    scenario_name: str,
    raw_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    snapshots = _extract_snapshots(raw_events)
    before_snap = snapshots.get(STATE_LABEL_BEFORE)
    after_snap = snapshots.get(STATE_LABEL_AFTER)

    if not scenario_name:
        raise ValueError("Scenario name is required for analyzer dispatch.")
    try:
        scenario_enum = ScenarioName(scenario_name.upper())
    except ValueError as exc:
        raise ValueError(f"Unsupported scenario for analyzer: {scenario_name}") from exc

    user_answers = _extract_user_answers(raw_events)
    volume_probe = _extract_volume_probe(raw_events, user_answers)
    log_brand = _derive_log_brand(before_snap, after_snap, raw_events)
    live_log_text = load_live_button_log_text(session_id) if scenario_enum is ScenarioName.LIVE_BUTTON_MAPPING else ""
    log_text = live_log_text or load_logcat_text(session_id, scenario_enum.value)
    log_evidence = analyze_log_evidence(log_text, log_brand)
    live_log_excerpt = live_log_text or log_text
    expected_channel_value = _resolve_expected_channel(user_answers, raw_events)
    log_signals: Optional[QuicksetLogSignals] = None
    if scenario_enum is ScenarioName.TV_AUTO_SYNC:
        log_signals = parse_quickset_logs(log_text)
        _merge_quickset_signals(log_evidence, log_signals)
        autosync_started_flag = bool(getattr(log_signals, "autosync_started", False))
        autosync_success_flag = bool(getattr(log_signals, "autosync_completed_successfully", False))
        log_evidence.autosync_started = log_evidence.autosync_started or autosync_started_flag
        log_evidence.autosync_success = log_evidence.autosync_success or autosync_success_flag

    timeline_rows, missing_critical = _build_timeline_rows(
        raw_events=raw_events,
        user_answers=user_answers,
        before_snap=before_snap,
        after_snap=after_snap,
        volume_probe=volume_probe,
        log_brand=log_evidence.log_brand,
        log_evidence=log_evidence,
    )

    if scenario_enum is ScenarioName.LIVE_BUTTON_MAPPING:
        live_signals = parse_live_button_logs(
            log_text,
            expected_channel_value,
            session_id=session_id,
        )
        summary, analyzer_result = _build_live_button_session_summary(
            session_id=session_id,
            scenario_name=scenario_enum.value,
            raw_events=raw_events,
            timeline_rows=timeline_rows,
            user_answers=user_answers,
            live_signals=live_signals,
            expected_channel=expected_channel_value,
            log_excerpt=live_log_excerpt,
        )
    else:
        summary, analyzer_result = _build_session_summary(
            session_id=session_id,
            scenario_name=scenario_enum.value,
            raw_events=raw_events,
            timeline_rows=timeline_rows,
            log_brand=log_evidence.log_brand,
            missing_critical=missing_critical,
            log_evidence=log_evidence,
        )

    summary_dict = summary.to_dict()
    analysis_result_payload = analyzer_result.model_dump(mode="json")
    analysis_result_payload.update(
        {
            "brand_status": summary.brand_status,
            "volume_status": summary.volume_status,
            "osd_status": summary.osd_status,
        }
    )

    return {
        "session": summary_dict,
        "timeline": [row.to_dict() for row in timeline_rows],
        "has_failure": summary.has_failure,
        "analysis_result": analysis_result_payload,
    }


# ----------------------- HELPERS: EXTRACTION --------------------- #

def _parse_ts(v: Any) -> Optional[str]:
    if not v:
        return None
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt.isoformat()
        except Exception:
            return v
    return str(v)


def _extract_snapshots(events: List[Dict[str, Any]]) -> Dict[str, SnapshotState]:
    res: Dict[str, SnapshotState] = {}
    for ev in events:
        if ev.get("step_name") != STATE_SNAPSHOT_STEP_NAME:
            continue
        details = ev.get("details") or {}
        label = details.get("label")
        data = details.get("data") or {}
        if label:
            res[label] = SnapshotState(label=label, raw=data)
    return res


def _normalize_base_step_name(name: str) -> str:
    if name.endswith("_answer"):
        return name[: -len("_answer")]
    if name.endswith(".answer"):
        return name[: -len(".answer")]
    if name.endswith("-answer"):
        return name[: -len("-answer")]
    return name


def _is_question_step(base_name: str) -> bool:
    return base_name.startswith("question_")


def _infer_scenario_name(events: List[Dict[str, Any]]) -> str:
    for ev in events:
        details = ev.get("details") or {}
        for key in ("scenario_name", "scenario_id", "scenario"):
            candidate = ev.get(key) or details.get(key)
            if candidate:
                text = str(candidate).strip()
                if text and text.upper() != "UNKNOWN":
                    return text.upper()

    for ev in events:
        step_name = str(ev.get("step_name") or "")
        base_name = _normalize_base_step_name(step_name)
        if base_name in TV_AUTO_SYNC_MARKERS or "tv_auto_sync" in step_name.lower():
            return "TV_AUTO_SYNC"
        if base_name in {
            "question_expected_channel",
            "configure_live_mapping",
            "phase1_live_press",
            "phase2_kill_and_relaunch",
            "phase3_reboot_persist",
        }:
            return "LIVE_BUTTON_MAPPING"

    return "UNKNOWN"


def _extract_user_answers(events: List[Dict[str, Any]]) -> Dict[str, str]:
    answers: Dict[str, str] = {}
    for ev in events:
        raw_name = ev.get("step_name") or ""
        base = _normalize_base_step_name(raw_name)
        details = ev.get("details") or {}
        candidate = (
            details.get("answer")
            or details.get("value")
            or details.get("user_answer")
        )
        if candidate is None:
            continue
        answers[base] = str(candidate).strip()
    return answers


VolumeSource = Literal["TV", "STB", "unknown"]


def _condense_event(
    event: Dict[str, Any],
    detail_keys: Optional[Tuple[str, ...]] = None,
) -> Dict[str, Any]:
    details = event.get("details") or {}
    if detail_keys is None:
        keys = (
            "volume_source",
            "confidence",
            "raw_code",
            "label",
            "data",
            "prompt",
            "answer",
            "question_id",
            "instruction",
        )
    else:
        keys = detail_keys
    condensed = {key: details.get(key) for key in keys if key in details}
    return {
        "step_name": event.get("step_name"),
        "timestamp": event.get("timestamp"),
        "details": condensed,
    }


def _detect_volume_change_from_logs(
    raw_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    evidence: List[Dict[str, Any]] = []
    detection_state: Literal["tv_control", "stb_control", "unknown"] = "unknown"
    detection_reason: Optional[str] = None
    source: Optional[str] = None
    change_detected: Optional[bool] = None
    tv_signal_reason: Optional[str] = None
    stb_signal_reason: Optional[str] = None

    def _record_tv_signal(reason: str) -> None:
        nonlocal tv_signal_reason
        if not tv_signal_reason:
            tv_signal_reason = reason

    def _record_stb_signal(reason: str) -> None:
        nonlocal stb_signal_reason
        if not stb_signal_reason:
            stb_signal_reason = reason

    for ev in raw_events:
        step_name = str(ev.get("step_name") or "")
        base_name = _normalize_base_step_name(step_name).lower()
        if _is_question_step(base_name) or base_name in IGNORED_VOLUME_EVENTS:
            continue
        details = ev.get("details") or {}
        has_signal = _event_has_volume_signal(details)
        is_probe_step = base_name in PROBE_EVENT_NAMES
        if not (is_probe_step or has_signal):
            continue
        evidence.append(_condense_event(ev))

        source_candidate = _extract_source_from_details(details)
        if source_candidate == "TV":
            _record_tv_signal("Logs indicate TV is controlling volume.")
        elif source_candidate == "STB":
            _record_stb_signal("Logs indicate STB is controlling volume.")

        if bool(details.get("osd_tv")):
            _record_tv_signal("Logs detected TV OSD activity.")
        if bool(details.get("osd_stb")):
            _record_stb_signal("Logs detected STB OSD activity.")

        change_flag = _extract_change_flag_from_details(details)
        if change_flag is not None:
            change_detected = change_flag

        if is_probe_step:
            matched = details.get("matched_signatures") or []
            categories = {
                (str(sig.get("category") or "").upper())
                for sig in matched
                if isinstance(sig, dict)
            }
            if any(cat.endswith("_TV") or cat.endswith("_1") for cat in categories):
                _record_tv_signal("Probe signatures indicate TV control.")
            if any(cat.endswith("_STB") or cat.endswith("_0") for cat in categories):
                _record_stb_signal("Probe signatures indicate STB control.")

            raw_code = details.get("raw_code")
            try:
                if raw_code is not None:
                    normalized_code = int(raw_code)
                else:
                    normalized_code = None
            except (TypeError, ValueError):
                normalized_code = None
            if normalized_code == 1:
                _record_tv_signal("Probe result indicates TV control.")
            elif normalized_code == 0:
                _record_stb_signal("Probe result indicates STB control.")

    if stb_signal_reason:
        detection_state = "stb_control"
        detection_reason = stb_signal_reason
        source = "STB"
    elif tv_signal_reason:
        detection_state = "tv_control"
        detection_reason = tv_signal_reason
        source = "TV"

    result: Dict[str, Any] = {
        "detection_state": detection_state,
        "source": source,
        "raw_evidence": evidence,
        "reason": detection_reason,
        "change_detected": change_detected if detection_state != "unknown" else None,
    }
    return result


def _normalize_probe_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in YES_ANSWERS:
            return True
        if normalized in NO_ANSWERS:
            return False
    return None


def _normalize_probe_source(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        upper = stripped.upper()
        if upper in {"TV", "TELEVISION"}:
            return "TV"
        if upper in {"STB", "SETTOP", "SET_TOP_BOX", "BOX"}:
            return "STB"
        if upper == "UNKNOWN":
            return "UNKNOWN"
        if upper.isdigit():
            return _normalize_probe_source(int(upper))
        return "UNKNOWN"
    if isinstance(value, (int, float)):
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return "UNKNOWN"
        if numeric == 1:
            return "TV"
        if numeric == 0:
            return "STB"
        return "UNKNOWN"
    return "UNKNOWN"


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except (ValueError, TypeError, AttributeError):
        return default


def _resolve_expected_channel(
    user_answers: Dict[str, str],
    raw_events: List[Dict[str, Any]],
    default: int = 3,
) -> int:
    if "question_expected_channel" in user_answers:
        return _safe_int(user_answers["question_expected_channel"], default)
    for ev in raw_events:
        base_name = _normalize_base_step_name(str(ev.get("step_name") or ""))
        if base_name not in {"live_expected_channel", "question_expected_channel"}:
            continue
        details = ev.get("details") or {}
        candidate = details.get("expected_channel") or details.get("answer") or details.get("value")
        if candidate is None:
            continue
        return _safe_int(candidate, default)
    return default


def _event_has_volume_signal(details: Dict[str, Any]) -> bool:
    for key in VOLUME_SIGNAL_KEYS:
        if key not in details:
            continue
        value = details.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return True
    return False


def _extract_source_from_details(details: Dict[str, Any]) -> Optional[str]:
    source_candidate = (
        details.get("volume_source")
        or details.get("tv_volume_source")
        or details.get("nes_volume_source")
        or details.get("current_volume_source")
    )
    normalized = _normalize_probe_source(source_candidate)
    if normalized:
        return normalized.upper()
    volume_keys = details.get("volume_keys_control_tv")
    if isinstance(volume_keys, bool):
        return "TV" if volume_keys else "STB"
    return None


def _extract_change_flag_from_details(details: Dict[str, Any]) -> Optional[bool]:
    return _normalize_probe_bool(
        details.get("volume_changed")
        or details.get("volume_change")
        or details.get("tv_volume_changed")
        or details.get("volume_probe_changed")
    )


def _extract_volume_probe(
    raw_events: List[Dict[str, Any]],
    user_answers: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    _ = user_answers  # user answers are not used for probe inference
    detection = _detect_volume_change_from_logs(raw_events)
    source_from_logs = detection.get("source")
    detection_state = detection.get("detection_state") or "unknown"
    evidence_from_logs = detection.get("raw_evidence") or []
    detection_reason = detection.get("reason")
    change_detected = detection.get("change_detected")
    latest_event: Optional[Dict[str, Any]] = None
    latest_details: Dict[str, Any] = {}
    for ev in raw_events:
        step_name = str(ev.get("step_name") or "")
        base_name = _normalize_base_step_name(step_name).lower()
        if _is_question_step(base_name) or base_name in IGNORED_VOLUME_EVENTS:
            continue
        details = ev.get("details") or {}
        has_signal = _event_has_volume_signal(details)
        is_probe_step = base_name in PROBE_EVENT_NAMES
        if is_probe_step or has_signal:
            latest_event = ev
            latest_details = details

    if not latest_event:
        raw_answer: Optional[str] = None
        fallback_source = None
        confidence = None
    else:
        raw_answer = (
            latest_details.get("answer")
            or latest_details.get("value")
            or latest_details.get("user_answer")
        )
        if raw_answer is not None:
            raw_answer = str(raw_answer).strip() or None
        fallback_source = _extract_source_from_details(latest_details)
        confidence = _safe_float(
            latest_details.get("confidence")
            or latest_details.get("probability")
            or latest_details.get("score")
        )

    source = source_from_logs or fallback_source
    if source:
        source = source.upper()

    changed: Optional[bool] = change_detected if detection_state != "unknown" else None

    return {
        "raw_answer": raw_answer,
        "source": source,
        "changed": changed,
        "evidence": evidence_from_logs,
        "detection_state": detection_state,
        "detection_reason": detection_reason,
        "confidence": confidence,
    }


# ----------------------- TIMELINE BUILD -------------------------- #

def _build_timeline_rows(
    raw_events: List[Dict[str, Any]],
    user_answers: Dict[str, str],
    before_snap: Optional[SnapshotState],
    after_snap: Optional[SnapshotState],
    volume_probe: Optional[Dict[str, Any]],
    log_brand: Optional[str],
    log_evidence: LogEvidence,
) -> tuple[List[StepRow], set[str]]:
    rows_by_name: Dict[str, StepRow] = {}

    for ev in raw_events:
        raw_name = ev.get("step_name") or ""
        base_name = _normalize_base_step_name(raw_name)
        if base_name not in WHITELISTED_STEPS:
            continue

        ts = _parse_ts(ev.get("timestamp"))
        details = ev.get("details") or {}
        question = details.get("question")
        label = _friendly_label(base_name)

        row = rows_by_name.get(base_name)
        if row is None:
            row = StepRow(
                name=base_name,
                label=label,
                status=StepStatus.INFO,
                timestamp=ts,
                question=question,
                user_answer=user_answers.get(base_name),
                details={},
            )
            rows_by_name[base_name] = row
        else:
            if ts:
                row.timestamp = ts
            if question and not row.question:
                row.question = question

        row.details.update(details)
        event_status = _event_status_to_step_status(ev.get("status"))
        if event_status:
            row.status = event_status

    for name, row in rows_by_name.items():
        if name == "question_manual_trigger":
            _apply_manual_trigger(row)
        elif name == "question_tv_volume_changed":
            _apply_volume_changed(row)
        elif name == "question_tv_osd_seen":
            _apply_osd(row)
        elif name == "question_pairing_screen_seen":
            _apply_pairing(row)
        elif name == "question_tv_brand_ui":
            _apply_brand(row, log_brand)
        elif name == "question_notes":
            _apply_notes(row)
        elif name == "live_expected_channel":
            _apply_expected_channel_metadata(row)

    _apply_volume_probe_to_rows(rows_by_name, volume_probe)

    rows = sorted(
        rows_by_name.values(),
        key=lambda r: (r.timestamp or "", r.name),
    )
    present_critical = {row.name for row in rows if row.name in CRITICAL_STEPS}
    missing_critical = CRITICAL_STEPS - present_critical
    return rows, missing_critical


def _event_status_to_step_status(raw_value: Any) -> Optional[StepStatus]:
    if not raw_value:
        return None
    normalized = str(raw_value).strip().upper()
    if normalized in StepStatus.__members__:
        return StepStatus[normalized]
    if normalized in ("RUNNING", "START"):
        return StepStatus.INFO
    return None


def _find_row(rows: List[StepRow], name: str) -> Optional[StepRow]:
    return next((row for row in rows if row.name == name), None)


def _friendly_label(name: str) -> str:
    mapping = {
        "question_manual_trigger": "Manual trigger",
        "question_tv_volume_changed": "TV volume changed",
        "question_tv_osd_seen": "TV OSD seen",
        "question_pairing_screen_seen": "Pairing screen",
        "question_tv_brand_ui": "TV brand (UI vs log)",
        "question_notes": "Tester notes",
        "question_expected_channel": "Expected channel",
        "live_expected_channel": "Expected channel",
        "device_focus_precheck": "Device focus precheck",
        "test_started": "Test started",
        "configure_live_mapping": "Configure Live button mapping",
        "phase1_live_press": "Phase 1: Live press",
        "phase2_kill_and_relaunch": "Phase 2: Kill + press",
        "phase3_reboot_persist": "Phase 3: Reboot + press",
        "test_completed": "Test completed",
        "analysis_summary": "Scenario summary",
    }
    return mapping.get(name, name)


# ----------------------- PER STEP LOGIC -------------------------- #

def _apply_manual_trigger(row: StepRow) -> None:
    row.status = StepStatus.PASS if row.user_answer else StepStatus.INFO


def _apply_volume_changed(row: StepRow) -> None:
    ans = (row.user_answer or "").strip().lower()
    if not ans:
        row.status = StepStatus.AWAITING_INPUT
        return
    if ans in YES_ANSWERS:
        row.status = StepStatus.PASS
    elif ans in NO_ANSWERS:
        row.status = StepStatus.FAIL
    else:
        row.status = StepStatus.PASS


def _apply_osd(row: StepRow) -> None:
    ans = (row.user_answer or "").strip().lower()
    if not ans:
        row.status = StepStatus.AWAITING_INPUT
        return
    if ans in YES_ANSWERS:
        row.status = StepStatus.PASS
    elif ans in NO_ANSWERS:
        row.status = StepStatus.FAIL
    else:
        row.status = StepStatus.PASS


def _apply_pairing(row: StepRow) -> None:
    ans = (row.user_answer or "").strip().lower()
    if not ans:
        row.status = StepStatus.AWAITING_INPUT
        return
    if ans in {"yes", "כן", "y", "true", "1"}:
        row.status = StepStatus.PASS
    elif ans in {"no", "לא", "n", "false", "0"}:
        row.status = StepStatus.FAIL
    else:
        row.status = StepStatus.PASS


def _derive_log_brand(
    before_snap: Optional[SnapshotState],
    after_snap: Optional[SnapshotState],
    raw_events: List[Dict[str, Any]],
) -> Optional[str]:
    for ev in reversed(raw_events):
        if ev.get("step_name") != "tv_metadata":
            continue
        details = ev.get("details") or {}
        for key in (
            "tv_brand_logs",
            "tv_brand",
            "brand",
            "tv_device_name",
        ):
            value = details.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for snap in (after_snap, before_snap):
        if not snap:
            continue
        if snap.tv_device_name:
            text = snap.tv_device_name.strip()
            if text:
                return text
    return None


def _apply_brand(
    row: StepRow,
    log_brand: Optional[str],
) -> None:
    user_brand = (row.user_answer or "").strip()
    log_brand_normalized = (log_brand or row.details.get("tv_brand_log") or "").strip()

    row.details["tv_brand_user"] = user_brand or None
    row.details["tv_brand_log"] = log_brand_normalized or None
    row.details["brand_mismatch"] = False

    if not user_brand:
        row.status = StepStatus.AWAITING_INPUT
        return

    if not log_brand_normalized:
        row.status = StepStatus.PASS
        return

    if user_brand.lower() == log_brand_normalized.lower():
        row.status = StepStatus.PASS
    else:
        row.status = StepStatus.FAIL
        row.details["brand_mismatch"] = True
        row.details["mismatch_reason"] = (
            f"Tester saw {user_brand or 'unknown'}, logs show {log_brand_normalized}."
        )


def _apply_notes(row: StepRow) -> None:
    row.status = StepStatus.INFO


def _apply_expected_channel_metadata(row: StepRow) -> None:
    expected_value = row.details.get("expected_channel") or row.details.get("answer")
    if expected_value is None:
        row.status = StepStatus.INFO
        return
    row.user_answer = str(expected_value)
    row.status = StepStatus.PASS


def _answer_flags(row: Optional[StepRow]) -> tuple[bool, bool]:
    if not row:
        return False, False
    ans = (row.user_answer or "").strip().lower()
    return ans in YES_ANSWERS, ans in NO_ANSWERS


def _normalized_answer(row: Optional[StepRow]) -> str:
    if not row or not row.user_answer:
        return ""
    return str(row.user_answer).strip().lower()


def _tester_issue_from_row(row: Optional[StepRow]) -> Optional[bool]:
    if not row:
        return None
    if row.status == StepStatus.FAIL:
        return True
    if row.status == StepStatus.PASS:
        return False
    return None


def _combine_metric_status(
    analyzer_issue: Optional[bool],
    tester_issue: Optional[bool],
) -> MetricStatus:
    if analyzer_issue is None:
        return "NOT_EVALUATED"
    if analyzer_issue is False:
        if tester_issue is None or tester_issue is False:
            return "OK"
        return "INCOMPATIBILITY"
    if tester_issue is None or tester_issue is True:
        return "FAIL"
    return "INCOMPATIBILITY"


def _has_tv_control_evidence(
    volume_row: Optional[StepRow],
    osd_row: Optional[StepRow],
    log_evidence: LogEvidence,
) -> bool:
    for row in (volume_row, osd_row):
        if not row:
            continue
        detection_state = str(row.details.get("volume_probe_detection_state") or "").strip().lower()
        if detection_state == "tv_control":
            return True
        source = str(row.details.get("volume_probe_source") or "").strip().upper()
        if source == "TV":
            return True
    volume_source = str(log_evidence.volume_source or "").strip().upper()
    if volume_source == "TV":
        return True
    if log_evidence.osd_tv:
        return True
    if log_evidence.tv_volume_events or log_evidence.tv_osd_events:
        return True
    return False


def _resolve_metric_status_from_tester(
    *,
    tester_yes: bool,
    tester_no: bool,
    telemetry_state: TelemetryState,
    analyzer_ready: bool,
    telemetry_metric_status: Optional[MetricStatus] = None,
) -> tuple[MetricStatus, bool]:
    if not analyzer_ready:
        return "NOT_EVALUATED", False
    if tester_no:
        return "FAIL", True
    telemetry_issue = telemetry_state == "STB_CONTROL_CONFIDENT"
    base_status: MetricStatus
    if telemetry_metric_status:
        base_status = telemetry_metric_status
    elif telemetry_state == "TV_CONTROL_CONFIDENT":
        base_status = "OK"
    elif telemetry_state == "STB_CONTROL_CONFIDENT":
        base_status = "INCOMPATIBILITY"
    else:
        base_status = "UNKNOWN"

    if tester_yes:
        return base_status, telemetry_issue and base_status == "INCOMPATIBILITY"

    if telemetry_state == "UNKNOWN" and not telemetry_metric_status:
        return "UNKNOWN", False
    return base_status, telemetry_issue and base_status == "INCOMPATIBILITY"


def _flag_probe_issue(
    row: Optional[StepRow],
    reason: str,
    *,
    allow_from_awaiting: bool = False,
) -> None:
    if not row:
        return
    if row.status == StepStatus.AWAITING_INPUT and not allow_from_awaiting:
        return
    row.status = StepStatus.FAIL
    existing = row.details.get("probe_mismatch_reason")
    if existing:
        row.details["probe_mismatch_reason"] = f"{existing}; {reason}"
    else:
        row.details["probe_mismatch_reason"] = reason
    row.details["issue_confirmed_by_probe"] = True


def _annotate_probe_note(row: Optional[StepRow], message: str, *, confirmed: bool = False) -> None:
    if not row or not message:
        return
    existing = row.details.get("probe_mismatch_reason")
    if existing:
        row.details["probe_mismatch_reason"] = f"{existing}; {message}"
    else:
        row.details["probe_mismatch_reason"] = message
    if confirmed:
        row.details["issue_confirmed_by_probe"] = True


def _apply_axis_timeline_status(
    row: Optional[StepRow],
    *,
    axis_label: str,
    tester_no: bool,
    telemetry_state: TelemetryState,
    analyzer_ready: bool,
    probe_confidence: float,
) -> None:
    if not row or not analyzer_ready:
        return
    if tester_no:
        row.status = StepStatus.FAIL
        return
    if telemetry_state == "STB_CONTROL_CONFIDENT":
        row.status = StepStatus.FAIL
        confidence_text = f"{probe_confidence:.2f}".rstrip("0").rstrip(".")
        reason = (
            f"Probe indicates STB controls {axis_label.lower()} (confidence {confidence_text})."
            if probe_confidence
            else f"Probe indicates STB controls {axis_label.lower()}."
        )
        _annotate_probe_note(row, reason, confirmed=True)
    elif telemetry_state == "UNKNOWN":
        row.status = StepStatus.INFO
        _annotate_probe_note(
            row,
            f"Telemetry inconclusive for {axis_label.lower()}; no TV control evidence detected.",
            confirmed=False,
        )
    else:
        row.status = StepStatus.PASS
        if "probe_mismatch_reason" in row.details and not tester_no:
            row.details.pop("probe_mismatch_reason", None)


def _apply_volume_probe_to_rows(
    rows_by_name: Dict[str, StepRow],
    volume_probe: Optional[Dict[str, Any]],
) -> None:
    if not volume_probe:
        return

    osd_row = rows_by_name.get("question_tv_osd_seen")
    if osd_row:
        osd_row.details["volume_probe_raw_answer"] = volume_probe.get("raw_answer")
        osd_row.details["volume_probe_source"] = volume_probe.get("source")
        osd_row.details["volume_probe_changed"] = volume_probe.get("changed")
        osd_row.details["volume_probe_detection_state"] = volume_probe.get("detection_state")
        if volume_probe.get("confidence") is not None:
            osd_row.details["volume_probe_confidence"] = volume_probe.get("confidence")
        if volume_probe.get("detection_reason"):
            osd_row.details["volume_probe_detection_reason"] = volume_probe.get("detection_reason")
        evidence = volume_probe.get("evidence")
        if evidence:
            osd_row.details["volume_probe_evidence"] = evidence[:3]

    volume_row = rows_by_name.get("question_tv_volume_changed")
    if volume_row:
        volume_row.details["volume_probe_source"] = volume_probe.get("source")
        volume_row.details["volume_probe_changed"] = volume_probe.get("changed")
        volume_row.details["volume_probe_detection_state"] = volume_probe.get("detection_state")
        if volume_probe.get("confidence") is not None:
            volume_row.details["volume_probe_confidence"] = volume_probe.get("confidence")
        if volume_probe.get("detection_reason"):
            volume_row.details["volume_probe_detection_reason"] = volume_probe.get("detection_reason")

    detection_state = str(volume_probe.get("detection_state") or "unknown").lower()
    volume_yes, volume_no = _answer_flags(volume_row)
    osd_yes, osd_no = _answer_flags(osd_row)
    volume_unanswered = not (volume_yes or volume_no) if volume_row else True
    osd_unanswered = not (osd_yes or osd_no) if osd_row else True

    if detection_state == "tv_control":
        if volume_row and (volume_no or volume_unanswered):
            reason = (
                "Tester reported no TV volume change but logs detected TV control."
                if volume_no
                else "Tester did not confirm TV volume change but logs detected TV control."
            )
            _flag_probe_issue(volume_row, reason, allow_from_awaiting=True)
        if osd_row and (osd_no or osd_unanswered):
            reason = (
                "Tester reported no TV OSD but logs detected TV control."
                if osd_no
                else "Tester did not confirm TV OSD but logs detected TV control."
            )
            _flag_probe_issue(osd_row, reason, allow_from_awaiting=True)
    elif detection_state == "stb_control":
        if volume_row:
            reason = (
                "Tester reported TV volume change but logs indicate STB is controlling volume."
                if volume_yes
                else "Logs indicate STB is controlling volume instead of TV."
            )
            _flag_probe_issue(volume_row, reason, allow_from_awaiting=True)
        if osd_row:
            reason = (
                "Tester reported TV OSD but logs indicate STB OSD."
                if osd_yes
                else "Logs indicate STB OSD/volume control instead of TV."
            )
            _flag_probe_issue(osd_row, reason, allow_from_awaiting=True)


# ----------------------- SESSION SUMMARY ------------------------- #

def _extract_session_times(
    events: List[Dict[str, Any]]
) -> Tuple[Optional[str], Optional[str]]:
    timestamps = [
        _parse_ts(ev.get("timestamp"))
        for ev in events
        if ev.get("timestamp")
    ]
    timestamps = [t for t in timestamps if t]
    if not timestamps:
        return None, None
    return timestamps[0], timestamps[-1]


def _compute_overall_status(rows: List[StepRow]) -> StepStatus:
    has_fail = any(r.status == StepStatus.FAIL for r in rows)
    has_await = any(r.status == StepStatus.AWAITING_INPUT for r in rows)
    if has_fail:
        return StepStatus.FAIL
    if has_await:
        return StepStatus.AWAITING_INPUT
    return StepStatus.PASS


def _normalize_volume_source(value: Optional[str]) -> str:
    if value is None:
        return "UNKNOWN"
    upper = value.strip().upper()
    if upper in {"TV", "STB"}:
        return upper
    if upper in {"1", "TELEVISION"}:
        return "TV"
    if upper in {"0", "SETTOP", "SET_TOP_BOX", "BOX"}:
        return "STB"
    return "UNKNOWN"


def classify_volume_telemetry(
    volume_source: Optional[str],
    tv_volume_events: Optional[bool],
    tv_osd_events: Optional[bool],
    volume_probe_confidence: Optional[float] = None,
    volume_source_history: Optional[List[str]] = None,
    tv_config_seen: Optional[bool] = None,
    tv_config_cleared: Optional[bool] = None,
    stb_volume_events: Optional[bool] = None,
) -> Tuple[TelemetryState, str, MetricStatus, Optional[Dict[str, Any]]]:
    normalized_source = _normalize_volume_source(volume_source) if volume_source else None
    tv_events = bool(tv_volume_events or tv_osd_events)
    confidence = float(volume_probe_confidence or 0.0)
    history = [src for src in (volume_source_history or []) if src in {"TV", "STB"}]
    recent = history[-6:]
    tv_count = recent.count("TV")
    stb_count = recent.count("STB")
    tv_config_active = bool(tv_config_seen and not tv_config_cleared)
    last_state = next((src for src in reversed(recent) if src in {"TV", "STB"}), normalized_source)

    tv_history_confident = tv_count >= max(2, stb_count + 1)
    if tv_events or tv_history_confident or (tv_config_active and (tv_count >= max(1, stb_count) or last_state == "TV")):
        return "TV_CONTROL_CONFIDENT", "TV", "OK", None

    stb_history_confident = stb_count >= max(2, tv_count + 1)
    stb_signals = bool(stb_volume_events) or normalized_source == "STB" or stb_history_confident
    config_forces_stb = bool(tv_config_cleared and not tv_events)

    if (stb_signals and not tv_events and not tv_config_active) or config_forces_stb:
        severity = "high" if confidence >= 0.5 else "medium"
        insight = {
            "code": "probe_detected_stb_control",
            "category": "functional",
            "severity": severity,
            "title": "Probe detected STB control",
            "description": (
                "Volume probe and logs indicate STB is controlling volume/OSD instead of the TV."
            ),
            "evidence_keys": ["volume_probe_state", "volume_probe_confidence"],
        }
        return "STB_CONTROL_CONFIDENT", "STB", "INCOMPATIBILITY", insight

    insight = {
        "code": "volume_probe_inconclusive",
        "category": "tooling",
        "severity": "low",
        "title": "Volume probe inconclusive",
        "description": (
            "Volume probe and logs did not provide enough evidence of TV control."
        ),
        "evidence_keys": ["volume_probe_state", "tv_volume_events", "tv_osd_events"],
    }
    return "UNKNOWN", "UNKNOWN", "UNKNOWN", insight


def _add_root_cause(
    root_causes: List[FailureInsight],
    recommendations: List[str],
    code: str,
    description: str,
) -> None:
    if not code or not description:
        return
    if any(item.code == code for item in root_causes):
        return
    meta = ROOT_CAUSE_METADATA.get(
        code,
        {
            "category": "functional",
            "severity": "medium",
            "title": description,
            "default_description": description,
            "recommendations": [],
            "evidence_keys": [],
        },
    )
    insight = FailureInsight(
        code=code,
        category=meta.get("category", "functional"),
        severity=meta.get("severity", "medium"),
        title=meta.get("title", description),
        description=description or meta.get("default_description", description),
        evidence_keys=meta.get("evidence_keys", []),
    )
    root_causes.append(insight)
    for rec in meta.get("recommendations", []):
        if rec not in recommendations:
            recommendations.append(rec)


def _build_analysis_details(
    *,
    volume_row: Optional[StepRow],
    osd_row: Optional[StepRow],
    log_evidence: LogEvidence,
    tv_brand_detected: Optional[str],
    tv_control_evidence: bool,
    missing_tv_responses: bool,
    volume_yes: bool,
    volume_no: bool,
    osd_yes: bool,
    osd_no: bool,
    has_volume_issue: bool,
    has_osd_issue: bool,
    final_autosync_success: bool,
    telemetry_state: TelemetryState,
    brand_mismatch: bool,
    autosync_never_started: bool,
    autosync_failed: bool,
    logs_inconclusive_for_autosync: bool,
    probe_state: str,
    probe_confidence: float,
) -> Tuple[List[FailureInsight], Dict[str, Any], List[str], str]:
    root_causes: List[FailureInsight] = []
    recs: List[str] = []

    if volume_no:
        _add_root_cause(root_causes, recs, "tester_saw_no_volume_change", "Tester did not observe TV volume change.")
    if osd_no:
        _add_root_cause(root_causes, recs, "tester_saw_no_osd", "Tester did not observe TV OSD.")

    if missing_tv_responses:
        _add_root_cause(
            root_causes,
            recs,
            "no_tv_response",
            "Tester reported no TV responses and logs lacked TV control evidence.",
        )

    if log_evidence.ir_commands_sent and missing_tv_responses:
        _add_root_cause(
            root_causes,
            recs,
            "ir_no_effect",
            "No TV response to IR commands was detected.",
        )

    if log_evidence.autosync_success and not final_autosync_success:
        _add_root_cause(
            root_causes,
            recs,
            "ruleset_ok_but_no_control",
            "QuickSet ruleset reported success, but no TV control was confirmed.",
        )

    if log_evidence.cec_inactive:
        _add_root_cause(
            root_causes,
            recs,
            "cec_inactive",
            "HDMI-CEC events were not detected; CEC might be disabled.",
        )
    if autosync_never_started:
        _add_root_cause(
            root_causes,
            recs,
            "autosync_not_started",
            "QuickSet logs did not show TV auto-sync starting.",
        )
    if autosync_failed and not autosync_never_started:
        _add_root_cause(
            root_causes,
            recs,
            "autosync_not_completed",
            "QuickSet logs show TV auto-sync started but not completed successfully.",
        )
    if logs_inconclusive_for_autosync:
        _add_root_cause(
            root_causes,
            recs,
            "autosync_logs_inconclusive",
            "Logs did not contain QuickSet or volume/OSD signals; relying on tester verdict.",
        )
    if brand_mismatch:
        _add_root_cause(
            root_causes,
            recs,
            "brand_mismatch_detected",
            "Tester brand does not match logs.",
        )
    if log_evidence.tv_config_cleared_during_run:
        _add_root_cause(
            root_causes,
            recs,
            "tv_config_cleared_during_run",
            "QuickSet removed TV configuration during the auto-sync run.",
        )

    tv_brand_detected = log_evidence.log_brand or tv_brand_detected
    ir_commands_sent = log_evidence.ir_commands_sent
    cec_events_detected = log_evidence.cec_events_detected
    tv_osd_events = log_evidence.tv_osd_events or log_evidence.osd_tv
    tv_volume_events = log_evidence.tv_volume_events or tv_control_evidence
    volume_probe_state_local = probe_state or "UNKNOWN"
    volume_probe_confidence_local = probe_confidence

    evidence_block = {
        "tv_brand_detected": tv_brand_detected,
        "ir_commands_sent": ir_commands_sent,
        "cec_events_detected": cec_events_detected,
        "tv_osd_events": tv_osd_events,
        "tv_volume_events": tv_volume_events,
        "volume_probe_state": volume_probe_state_local,
        "volume_probe_confidence": volume_probe_confidence_local,
        "autosync_errors": list(log_evidence.autosync_errors),
        "tv_config_cleared_during_run": log_evidence.tv_config_cleared_during_run,
        "tv_config_events": list(log_evidence.tv_config_events[-6:]),
        "volume_source_history": list(log_evidence.volume_source_history[-6:]),
    }
    if log_evidence.log_signals:
        evidence_block["log_signals"] = log_evidence.log_signals.model_dump(mode="json")

    contradiction_detected = any(
        bool(row and row.details.get("issue_confirmed_by_probe")) for row in (volume_row, osd_row)
    )
    volume_detection_state = str(volume_row.details.get("volume_probe_detection_state") or "").strip().lower() if volume_row else ""
    if volume_detection_state == "stb_control" or (log_evidence.volume_source or "").upper() == "STB":
        contradiction_detected = True

    if contradiction_detected:
        confidence = "high"
    elif missing_tv_responses:
        confidence = "low"
    elif has_volume_issue or has_osd_issue:
        confidence = "medium"
    else:
        confidence = "high"

    return root_causes, evidence_block, recs, confidence


def _build_live_button_session_summary(
    *,
    session_id: str,
    scenario_name: str,
    raw_events: List[Dict[str, Any]],
    timeline_rows: List[StepRow],
    user_answers: Dict[str, str],
    live_signals: LiveButtonSignals,
    expected_channel: int,
    log_excerpt: Optional[str] = None,
) -> Tuple[SessionSummary, AnalyzerResult]:
    started_at, finished_at = _extract_session_times(raw_events)
    summary_row = _find_row(timeline_rows, "analysis_summary")
    expected_row = _find_row(timeline_rows, "question_expected_channel") or _find_row(
        timeline_rows, "live_expected_channel"
    )
    config_row = _find_row(timeline_rows, "configure_live_mapping")
    phase_rows = {
        "PHASE1": _find_row(timeline_rows, "phase1_live_press"),
        "PHASE2": _find_row(timeline_rows, "phase2_kill_and_relaunch"),
        "PHASE3": _find_row(timeline_rows, "phase3_reboot_persist"),
    }

    expected_channel_text = user_answers.get("question_expected_channel")
    if expected_row:
        expected_value = expected_channel_text or expected_row.details.get("expected_channel")
        expected_row.user_answer = str(expected_value or expected_channel)
        expected_row.status = StepStatus.PASS

    raw_excerpt_snippet, no_markers_found = _extract_live_log_excerpt(log_excerpt, session_id)

    def _collect_step_statuses() -> Tuple[List[str], List[str]]:
        awaiting = sorted(row.name for row in timeline_rows if row.status == StepStatus.AWAITING_INPUT)
        failed = sorted(row.name for row in timeline_rows if row.status == StepStatus.FAIL)
        return awaiting, failed

    root_causes: List[FailureInsight] = []
    recommendations: List[str] = []

    def _add_live_root_cause(code: str, description: str) -> None:
        _add_root_cause(root_causes, recommendations, code, description)

    config_details = dict(config_row.details or {}) if config_row else {}
    ui_prompt_detected = bool(config_details.get("ui_prompt_detected"))
    ui_value_after_raw = config_details.get("value_after")
    try:
        ui_value_after = int(ui_value_after_raw) if ui_value_after_raw is not None else None
    except (TypeError, ValueError):
        ui_value_after = None
    ui_confirm_method = config_details.get("confirm_method_used")

    if ui_prompt_detected and not getattr(live_signals, "config_screen_detected", False):
        live_signals.config_screen_detected = True
    if ui_value_after is not None and expected_channel is not None and ui_value_after == expected_channel:
        live_signals.config_verified = True
    config_attempted = bool(getattr(live_signals, "config_attempted", False)) or ui_prompt_detected
    config_verified = bool(getattr(live_signals, "config_verified", False))
    session_logs_found = bool(getattr(live_signals, "session_logs_found", True) or ui_prompt_detected)
    config_screen_detected = bool(getattr(live_signals, "config_screen_detected", False) or ui_prompt_detected)
    phase_data_present = bool(live_signals and live_signals.phases)
    no_live_signals = (
        live_signals is None
        or (
            not session_logs_found
            and not phase_data_present
            and not config_attempted
        )
    )

    if no_live_signals:
        analysis_text = "INCONCLUSIVE – no log evidence captured."
        log_verdict = "INCONCLUSIVE"
        _add_live_root_cause(
            "live_button_logs_inconclusive_all_phases",
            "No Live-button configuration or press signals were found in the analyzed logs.",
        )

        for row in [config_row, phase_rows.get("PHASE1"), phase_rows.get("PHASE2"), phase_rows.get("PHASE3")]:
            if row:
                row.status = StepStatus.INCONCLUSIVE

        evidence_block = {
            "live_button_signals": {
                "expected_channel": expected_channel,
                "config_saved_channel": live_signals.config_saved_channel if live_signals else None,
                "config_attempted": config_attempted,
                "config_verified": config_verified,
                "session_logs_found": session_logs_found,
                "config_screen_detected": config_screen_detected,
                "ui_prompt_detected": ui_prompt_detected,
                "ui_value_after": ui_value_after,
                "ui_confirm_method": ui_confirm_method,
                "phases": [
                    {
                        "phase": phase.phase,
                        "live_key_pressed": phase.live_key_pressed,
                        "partnertv_launched": phase.partnertv_launched,
                        "observed_channel": phase.observed_channel,
                    }
                    for phase in (live_signals.phases if live_signals else [])
                ],
                "raw_excerpt": raw_excerpt_snippet,
                "no_markers_found": no_markers_found,
            },
        }

        awaiting_steps, failed_steps = _collect_step_statuses()

        if summary_row:
            details = dict(summary_row.details or {})
            details.update(
                {
                    "analysis": analysis_text,
                    "tester_verdict": "AUTOMATED",
                    "log_verdict": log_verdict,
                    "evidence": evidence_block,
                    "recommendations": recommendations,
                    "failure_insights": [ins.model_dump(mode="json") for ins in root_causes],
                }
            )
            summary_row.details = details
            summary_row.status = StepStatus.INCONCLUSIVE

        test_completed_row = _find_row(timeline_rows, "test_completed")
        if test_completed_row:
            test_completed_row.status = StepStatus.INCONCLUSIVE
            if finished_at:
                test_completed_row.timestamp = finished_at

        summary = SessionSummary(
            session_id=session_id,
            scenario_name=scenario_name,
            started_at=started_at,
            finished_at=finished_at,
            overall_status=StepStatus.INCONCLUSIVE,
            brand_mismatch=False,
            tv_brand_user=None,
            tv_brand_log=None,
            has_volume_issue=False,
            has_osd_issue=False,
            notes=None,
            analysis_text=analysis_text,
            has_failure=False,
            brand_status="NOT_EVALUATED",
            volume_status="NOT_EVALUATED",
            osd_status="NOT_EVALUATED",
        )

        analyzer_result = AnalyzerResult(
            overall_status=StepStatus.INCONCLUSIVE.value,
            has_failure=False,
            failed_steps=failed_steps,
            awaiting_steps=awaiting_steps,
            analysis_text=analysis_text,
            failure_insights=root_causes,
            evidence=evidence_block,
            recommendations=recommendations,
            confidence="low",
        )

        return summary, analyzer_result

    if not config_screen_detected and session_logs_found:
        analysis_text = "Live button mapping failed: the Live channel settings screen was never reached."
        log_verdict = "FAIL"
        confidence = "high"
        _add_live_root_cause("live_mapping_screen_not_reached", analysis_text)
        if config_row:
            config_row.status = StepStatus.FAIL
        for row in phase_rows.values():
            if row:
                row.status = StepStatus.INFO

        evidence_block = {
            "live_button_signals": {
                "expected_channel": expected_channel,
                "config_saved_channel": live_signals.config_saved_channel,
                "config_attempted": config_attempted,
                "config_verified": config_verified,
                "config_screen_detected": config_screen_detected,
                "ui_prompt_detected": ui_prompt_detected,
                "ui_value_after": ui_value_after,
                "ui_confirm_method": ui_confirm_method,
                "session_logs_found": session_logs_found,
                "phases": [
                    {
                        "phase": phase.phase,
                        "live_key_pressed": phase.live_key_pressed,
                        "partnertv_launched": phase.partnertv_launched,
                        "observed_channel": phase.observed_channel,
                        "raw_excerpt": phase.raw_excerpt,
                    }
                    for phase in live_signals.phases
                ],
                "raw_excerpt": raw_excerpt_snippet,
                "no_markers_found": no_markers_found,
            },
        }
        awaiting_steps, failed_steps = _collect_step_statuses()
        if summary_row:
            details = dict(summary_row.details or {})
            details.update(
                {
                    "analysis": analysis_text,
                    "tester_verdict": "AUTOMATED",
                    "log_verdict": log_verdict,
                    "evidence": evidence_block,
                    "recommendations": recommendations,
                    "failure_insights": [ins.model_dump(mode="json") for ins in root_causes],
                }
            )
            summary_row.details = details
            summary_row.status = StepStatus.FAIL
        test_completed_row = _find_row(timeline_rows, "test_completed")
        if test_completed_row:
            test_completed_row.status = StepStatus.FAIL
            if finished_at:
                test_completed_row.timestamp = finished_at

        summary = SessionSummary(
            session_id=session_id,
            scenario_name=scenario_name,
            started_at=started_at,
            finished_at=finished_at,
            overall_status=StepStatus.FAIL,
            brand_mismatch=False,
            tv_brand_user=None,
            tv_brand_log=None,
            has_volume_issue=False,
            has_osd_issue=False,
            notes=None,
            analysis_text=analysis_text,
            has_failure=True,
            brand_status="NOT_EVALUATED",
            volume_status="NOT_EVALUATED",
            osd_status="NOT_EVALUATED",
        )

        analyzer_result = AnalyzerResult(
            overall_status=StepStatus.FAIL.value,
            has_failure=True,
            failed_steps=failed_steps,
            awaiting_steps=awaiting_steps,
            analysis_text=analysis_text,
            failure_insights=root_causes,
            evidence=evidence_block,
            recommendations=recommendations,
            confidence=confidence,
        )

        return summary, analyzer_result

    phases_by_name = {(phase.phase or "").upper(): phase for phase in live_signals.phases}

    config_confirmed = config_verified or (
        live_signals.config_saved_channel is not None
        and expected_channel is not None
        and live_signals.config_saved_channel == expected_channel
    )
    if not config_confirmed and config_row:
        config_row.status = StepStatus.FAIL

    phase_descriptions = {
        "PHASE1": "initial Live press",
        "PHASE2": "Live press after force-stop",
        "PHASE3": "Live press after reboot",
    }
    phase_fail_messages: List[str] = []
    phase_inconclusive: List[str] = []

    for index, phase_name in enumerate(("PHASE1", "PHASE2", "PHASE3"), start=1):
        signals = phases_by_name.get(phase_name)
        row = phase_rows.get(phase_name)
        desc = phase_descriptions[phase_name]
        if row and row.details.get("skipped_due_to_config_error"):
            continue
        observed_channel = signals.observed_channel if signals else None
        phase_pass = (
            signals is not None
            and signals.live_key_pressed
            and signals.partnertv_launched
            and observed_channel is not None
            and observed_channel == expected_channel
        )
        if phase_pass:
            if row:
                row.status = StepStatus.PASS
            continue

        if signals is None or (
            not signals.live_key_pressed and not signals.partnertv_launched and signals.observed_channel is None
        ):
            reason = f"{desc}: logs were inconclusive."
            phase_inconclusive.append(reason)
            _add_live_root_cause(f"live_button_logs_inconclusive_phase{index}", reason)
            if row:
                row.status = StepStatus.INCONCLUSIVE
            continue

        if observed_channel is not None and observed_channel != expected_channel:
            reason = (
                f"{desc}: PartnerTV+ opened on channel {observed_channel}, expected {expected_channel}."
            )
            phase_fail_messages.append(reason)
            _add_live_root_cause(f"live_button_wrong_channel_phase{index}", reason)
            if row:
                row.status = StepStatus.FAIL
            continue

        if signals.live_key_pressed and not signals.partnertv_launched:
            reason = f"{desc}: Live key press detected but PartnerTV+ did not launch."
            phase_fail_messages.append(reason)
            _add_live_root_cause(f"live_button_no_launch_phase{index}", reason)
            if row:
                row.status = StepStatus.FAIL
            continue

        reason = f"{desc}: logs missing channel confirmation."
        phase_inconclusive.append(reason)
        _add_live_root_cause(f"live_button_logs_inconclusive_phase{index}", reason)
        if row:
            row.status = StepStatus.INCONCLUSIVE

    if not config_confirmed:
        overall = StepStatus.FAIL
        if config_attempted:
            analysis_text = (
                f"Live button mapping failed: automation could not confirm that the Live button field was set to "
                f"channel {expected_channel}."
            )
            log_verdict = "INCONCLUSIVE"
            confidence = "low"
        else:
            analysis_text = (
                "Live button mapping failed: configuration screen was not reached, so the expected channel "
                f"{expected_channel} was never applied."
            )
            log_verdict = "FAIL"
            confidence = "high"
        _add_live_root_cause("live_mapping_not_configured", analysis_text)
    elif phase_fail_messages:
        overall = StepStatus.FAIL
        analysis_text = "; ".join(phase_fail_messages)
        log_verdict = "FAIL"
        confidence = "high"
    elif phase_inconclusive:
        overall = StepStatus.FAIL
        analysis_text = "; ".join(phase_inconclusive)
        log_verdict = "INCONCLUSIVE"
        confidence = "low"
    else:
        overall = StepStatus.PASS
        analysis_text = (
            f"Live button mapping passed: PartnerTV+ opened on channel {expected_channel} across all phases "
            "(initial, after kill, after reboot)."
        )
        log_verdict = "PASS"
        confidence = "high"

    has_failure = overall == StepStatus.FAIL

    evidence_block = {
        "live_button_signals": {
            "expected_channel": expected_channel,
            "config_saved_channel": live_signals.config_saved_channel,
            "config_attempted": config_attempted,
            "config_verified": config_confirmed,
            "config_screen_detected": config_screen_detected,
            "session_logs_found": session_logs_found,
            "phases": [
                {
                    "phase": phase.phase,
                    "live_key_pressed": phase.live_key_pressed,
                    "partnertv_launched": phase.partnertv_launched,
                    "observed_channel": phase.observed_channel,
                    "raw_excerpt": phase.raw_excerpt,
                }
                for phase in live_signals.phases
            ],
            "raw_excerpt": raw_excerpt_snippet,
            "no_markers_found": no_markers_found,
        },
    }

    awaiting_steps, failed_steps = _collect_step_statuses()

    if summary_row:
        details = dict(summary_row.details or {})
        details.update(
            {
                "analysis": analysis_text,
                "tester_verdict": "AUTOMATED",
                "log_verdict": log_verdict,
                "evidence": evidence_block,
                "recommendations": recommendations,
                "failure_insights": [ins.model_dump(mode="json") for ins in root_causes],
            }
        )
        summary_row.details = details
        summary_row.status = overall

    test_completed_row = _find_row(timeline_rows, "test_completed")
    if test_completed_row:
        test_completed_row.status = overall
        if finished_at:
            test_completed_row.timestamp = finished_at

    summary = SessionSummary(
        session_id=session_id,
        scenario_name=scenario_name,
        started_at=started_at,
        finished_at=finished_at,
        overall_status=overall,
        brand_mismatch=False,
        tv_brand_user=None,
        tv_brand_log=None,
        has_volume_issue=False,
        has_osd_issue=False,
        notes=None,
        analysis_text=analysis_text,
        has_failure=has_failure,
        brand_status="NOT_EVALUATED",
        volume_status="NOT_EVALUATED",
        osd_status="NOT_EVALUATED",
    )

    analyzer_result = AnalyzerResult(
        overall_status=overall.value,
        has_failure=has_failure,
        failed_steps=failed_steps,
        awaiting_steps=awaiting_steps,
        analysis_text=analysis_text,
        failure_insights=root_causes,
        evidence=evidence_block,
        recommendations=recommendations,
        confidence=confidence,
    )

    return summary, analyzer_result


def _build_session_summary(
    session_id: str,
    scenario_name: str,
    raw_events: List[Dict[str, Any]],
    timeline_rows: List[StepRow],
    log_brand: Optional[str],
    missing_critical: set[str],
    log_evidence: LogEvidence,
) -> Tuple[SessionSummary, AnalyzerResult]:
    started_at, finished_at = _extract_session_times(raw_events)

    summary_row = next((r for r in timeline_rows if r.name == "analysis_summary"), None)
    brand_row = next((r for r in timeline_rows if r.name == "question_tv_brand_ui"), None)
    volume_row = next((r for r in timeline_rows if r.name == "question_tv_volume_changed"), None)
    osd_row = next((r for r in timeline_rows if r.name == "question_tv_osd_seen"), None)
    pairing_row = next((r for r in timeline_rows if r.name == "question_pairing_screen_seen"), None)
    notes_row = next((r for r in timeline_rows if r.name == "question_notes"), None)
    volume_answer = _normalized_answer(volume_row)
    osd_answer = _normalized_answer(osd_row)
    volume_yes = volume_answer in YES_ANSWERS
    volume_no = volume_answer in NO_ANSWERS
    osd_yes = osd_answer in YES_ANSWERS
    osd_no = osd_answer in NO_ANSWERS
    pairing_answer = _normalized_answer(pairing_row)
    pairing_yes = pairing_answer in YES_ANSWERS
    pairing_no = pairing_answer in NO_ANSWERS
    tv_control_evidence = _has_tv_control_evidence(volume_row, osd_row, log_evidence)
    missing_tv_responses = volume_no and osd_no and not tv_control_evidence
    volume_probe_step = next((r for r in timeline_rows if r.name == "volume_probe_result"), None)
    probe_details = volume_probe_step.details if volume_probe_step else {}
    raw_volume_source = probe_details.get("volume_source") or log_evidence.volume_source
    probe_confidence_value = _safe_float(probe_details.get("confidence"))
    telemetry_state, volume_probe_state, telemetry_metric_status, probe_insight = classify_volume_telemetry(
        volume_source=str(raw_volume_source) if raw_volume_source else None,
        tv_volume_events=log_evidence.tv_volume_events,
        tv_osd_events=log_evidence.tv_osd_events or log_evidence.osd_tv,
        volume_probe_confidence=probe_confidence_value,
        volume_source_history=log_evidence.volume_source_history,
        tv_config_seen=log_evidence.tv_config_seen,
        tv_config_cleared=log_evidence.tv_config_cleared_during_run,
        stb_volume_events=log_evidence.stb_volume_events,
    )
    probe_confidence = float(probe_confidence_value or 0.0)

    brand_mismatch_raw = bool(brand_row and brand_row.details.get("brand_mismatch"))

    tester_brand_issue = _tester_issue_from_row(brand_row)

    awaiting_steps = sorted(
        set(missing_critical).union(
            {
                row.name
                for row in timeline_rows
                if row.name in CRITICAL_STEPS and row.status == StepStatus.AWAITING_INPUT
            }
        )
    )
    any_await = bool(awaiting_steps)
    final_stage = summary_row is not None

    analyzer_ready = final_stage and not any_await

    analyzer_brand_issue = brand_mismatch_raw if analyzer_ready else None

    brand_status = _combine_metric_status(analyzer_brand_issue, tester_brand_issue)
    volume_status, has_volume_issue = _resolve_metric_status_from_tester(
        tester_yes=volume_yes,
        tester_no=volume_no,
        telemetry_state=telemetry_state,
        analyzer_ready=analyzer_ready,
        telemetry_metric_status=telemetry_metric_status,
    )
    osd_status, has_osd_issue = _resolve_metric_status_from_tester(
        tester_yes=osd_yes,
        tester_no=osd_no,
        telemetry_state=telemetry_state,
        analyzer_ready=analyzer_ready,
    )

    brand_mismatch = bool(analyzer_brand_issue)

    tv_brand_user = brand_row.details.get("tv_brand_user") if brand_row else None
    tv_brand_log = (
        brand_row.details.get("tv_brand_log") if brand_row else log_brand
    )

    autosync_logs = _evaluate_autosync_from_logs(log_evidence.log_signals)
    log_evidence.autosync_started = autosync_logs.autosync_started
    log_evidence.autosync_success = autosync_logs.autosync_success
    logs_inconclusive_for_autosync = autosync_logs.logs_inconclusive
    strong_log_fail = (
        autosync_logs.autosync_started
        and not autosync_logs.autosync_success
        and autosync_logs.autosync_failed
    )
    strong_log_pass = autosync_logs.autosync_started and autosync_logs.autosync_success

    _apply_axis_timeline_status(
        volume_row,
        axis_label="TV volume",
        tester_no=volume_no,
        telemetry_state=telemetry_state,
        analyzer_ready=analyzer_ready,
        probe_confidence=probe_confidence,
    )
    _apply_axis_timeline_status(
        osd_row,
        axis_label="TV OSD",
        tester_no=osd_no,
        telemetry_state=telemetry_state,
        analyzer_ready=analyzer_ready,
        probe_confidence=probe_confidence,
    )

    tester_fail_volume = volume_no
    tester_fail_osd = osd_no
    tester_fail_pairing = pairing_no
    functional_pass = volume_yes and osd_yes and pairing_yes
    tester_fail = tester_fail_volume or tester_fail_osd or tester_fail_pairing
    tester_verdict = "PASS" if functional_pass else ("FAIL" if tester_fail else "UNKNOWN")
    autosync_never_started = final_stage and not autosync_logs.autosync_started and not logs_inconclusive_for_autosync
    autosync_failed = final_stage and strong_log_fail
    telemetry_confident_failure = telemetry_state == "STB_CONTROL_CONFIDENT"
    telemetry_inconclusive = telemetry_state == "UNKNOWN"
    pass_summary_prefix = (
        "TV auto-sync functional criteria passed (tester confirmed volume, OSD, and pairing). "
        if functional_pass
        else "TV auto-sync functional checks did not report failures. "
    )
    if autosync_never_started:
        log_verdict = "FAIL"
        log_failure_reason = "Auto-sync was not triggered in logs."
    elif telemetry_confident_failure:
        log_verdict = "FAIL"
        log_failure_reason = "Telemetry indicates STB is controlling volume/OSD despite tester confirmation."
    elif strong_log_fail:
        log_verdict = "FAIL"
        log_failure_reason = "Auto-sync did not complete successfully in logs."
    elif logs_inconclusive_for_autosync:
        log_verdict = "INCONCLUSIVE"
        log_failure_reason = "Logs were inconclusive for auto-sync; relying on tester answers."
    elif telemetry_inconclusive:
        log_verdict = "INCONCLUSIVE"
        log_failure_reason = None
    elif strong_log_pass:
        log_verdict = "PASS"
        log_failure_reason = None
    else:
        log_verdict = "INCONCLUSIVE"
        log_failure_reason = None
    conflict_tester_vs_logs = functional_pass and strong_log_fail

    if not analyzer_ready:
        overall = StepStatus.AWAITING_INPUT
        analysis_text = "TV auto-sync in progress – awaiting tester input."
    elif tester_fail:
        overall = StepStatus.FAIL
        if missing_tv_responses:
            analysis_text = "TV auto-sync failed: no TV responses observed (no volume change, no TV OSD)."
        elif tester_fail_volume and tester_fail_osd:
            analysis_text = "TV auto-sync failed: tester did not observe TV volume change or OSD."
        elif tester_fail_volume:
            analysis_text = "TV auto-sync failed: tester did not observe TV volume change."
        elif tester_fail_osd:
            analysis_text = "TV auto-sync failed: tester did not observe TV OSD."
        elif tester_fail_pairing:
            analysis_text = "TV auto-sync failed: pairing screen was not seen."
        else:
            analysis_text = "TV auto-sync failed: one or more tester checks did not pass."
    elif brand_mismatch:
        overall = StepStatus.FAIL
        analysis_text = "TV auto-sync failed: TV brand seen by tester does not match logs."
    elif log_verdict == "FAIL":
        overall = StepStatus.FAIL
        analysis_text = log_failure_reason or "TV auto-sync failed due to log evidence."
    else:
        overall = StepStatus.PASS
        if log_verdict == "INCONCLUSIVE":
            if logs_inconclusive_for_autosync:
                analysis_text = pass_summary_prefix + "Logs were inconclusive for auto-sync; relying on tester answers."
            else:
                analysis_text = pass_summary_prefix + "Telemetry probe was inconclusive – no TV responses observed."
        else:
            analysis_text = "TV auto-sync completed successfully with no detected issues."

    failed_steps = [
        row.name
        for row in timeline_rows
        if row.name in CRITICAL_STEPS and row.status == StepStatus.FAIL
    ]

    if summary_row:
        summary_row.details["tester_verdict"] = tester_verdict
        summary_row.details["log_verdict"] = log_verdict
        summary_row.details["telemetry_state"] = telemetry_state
        summary_row.details["conflict_tester_vs_logs"] = conflict_tester_vs_logs
        if log_failure_reason:
            summary_row.details["log_failure_reason"] = log_failure_reason

    positive_volume_signal = volume_yes and not has_volume_issue
    positive_osd_signal = osd_yes and not has_osd_issue
    final_autosync_success = (
        autosync_logs.autosync_started
        and autosync_logs.autosync_success
        and positive_volume_signal
        and positive_osd_signal
        and not brand_mismatch
    )

    failure_insights, evidence_block, recs, confidence = _build_analysis_details(
        volume_row=volume_row,
        osd_row=osd_row,
        log_evidence=log_evidence,
        tv_brand_detected=tv_brand_log or tv_brand_user or log_evidence.log_brand,
        tv_control_evidence=tv_control_evidence,
        missing_tv_responses=missing_tv_responses,
        volume_yes=volume_yes,
        volume_no=volume_no,
        osd_yes=osd_yes,
        osd_no=osd_no,
        has_volume_issue=has_volume_issue,
        has_osd_issue=has_osd_issue,
        final_autosync_success=final_autosync_success,
        telemetry_state=telemetry_state,
        brand_mismatch=brand_mismatch,
        autosync_never_started=autosync_never_started,
        autosync_failed=autosync_failed,
        logs_inconclusive_for_autosync=logs_inconclusive_for_autosync,
        probe_state=volume_probe_state,
        probe_confidence=probe_confidence,
    )

    if probe_insight:
        insight_obj = FailureInsight(**probe_insight)
        if not any(existing.code == insight_obj.code for existing in failure_insights):
            failure_insights.append(insight_obj)

    has_failure = overall == StepStatus.FAIL

    analyzer_result = AnalyzerResult(
        overall_status=overall.value,
        has_failure=has_failure,
        failed_steps=failed_steps,
        awaiting_steps=awaiting_steps,
        analysis_text=analysis_text,
        failure_insights=failure_insights,
        evidence=evidence_block,
        recommendations=recs,
        confidence=confidence,
    )

    if summary_row:
        summary_row.status = overall
        summary_row.details["analysis"] = analysis_text
        summary_row.details["failed_steps"] = failed_steps
        summary_row.details["awaiting_steps"] = awaiting_steps
        summary_row.details["autosync_started"] = autosync_logs.autosync_started
        summary_row.details["autosync_success"] = final_autosync_success
        summary_row.details["failure_insights"] = [ins.model_dump(mode="json") for ins in failure_insights]
        summary_row.details["evidence"] = evidence_block
        summary_row.details["recommendations"] = recs
        summary_row.details["confidence"] = confidence
        summary_row.details["confidence_level"] = confidence

    test_completed_row = next((r for r in timeline_rows if r.name == "test_completed"), None)
    if test_completed_row:
        test_completed_row.status = overall
        if finished_at:
            test_completed_row.timestamp = finished_at

    session_summary = SessionSummary(
        session_id=session_id,
        scenario_name=scenario_name,
        started_at=started_at,
        finished_at=finished_at,
        overall_status=overall,
        brand_mismatch=brand_mismatch,
        tv_brand_user=tv_brand_user,
        tv_brand_log=tv_brand_log,
        has_volume_issue=has_volume_issue,
        has_osd_issue=has_osd_issue,
        notes=notes_row.user_answer if notes_row else None,
        analysis_text=analysis_text,
        has_failure=has_failure,
        brand_status=brand_status,
        volume_status=volume_status,
        osd_status=osd_status,
    )

    return session_summary, analyzer_result
