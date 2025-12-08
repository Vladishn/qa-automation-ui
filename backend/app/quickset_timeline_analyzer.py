# backend/quickset_timeline_analyzer.py

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Literal
from datetime import datetime
import re
from pathlib import Path

from .analyzers.base import AnalyzerResult, FailureInsight


class StepStatus(str, Enum):
    INFO = "INFO"
    PASS = "PASS"
    FAIL = "FAIL"
    AWAITING_INPUT = "AWAITING_INPUT"


MetricStatus = Literal["OK", "FAIL", "INCOMPATIBILITY", "NOT_EVALUATED"]
TelemetryState = Literal["TV_CONTROL", "STB_CONTROL_CONFIDENT", "UNKNOWN"]
PROBE_CONFIDENCE_CONFIDENT = 0.7


WHITELISTED_STEPS = {
    "question_manual_trigger",
    "question_tv_volume_changed",
    "question_tv_osd_seen",
    "question_pairing_screen_seen",
    "question_tv_brand_ui",
    "question_notes",
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
LOG_DIR_CANDIDATES = [
    PROJECT_ROOT / "artifacts" / "quickset_logs",
    PROJECT_ROOT / "artifacts" / "logs",
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

VOLUME_PROBE_ISSUE_STATES = {"UNKNOWN", "NONE", "NO_TV_CONTROL", "STB"}


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
    osd_tv: bool = False
    osd_stb: bool = False
    volume_source: Optional[str] = None
    log_brand: Optional[str] = None
    log_text: str = ""
    ir_commands_sent: bool = False
    cec_events_detected: bool = False
    cec_inactive: bool = False


def load_logcat_text(session_id: str) -> str:
    candidates: List[Path] = []
    for base in LOG_DIR_CANDIDATES:
        candidates.append(base / session_id / f"{session_id}_tv_auto_sync.log")
        candidates.append(base / f"{session_id}_tv_auto_sync.log")
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


def detect_autosync_from_events(events: List[Dict[str, Any]]) -> tuple[bool, bool]:
    started = False
    success = False
    for ev in events:
        step = str(ev.get("step_name") or "")
        step_upper = step.upper()
        details = ev.get("details") or {}
        tags = [
            str(tag).lower()
            for tag in (details.get("tags") or [])
            if isinstance(tag, str)
        ]
        signatures = details.get("matched_signatures") or []
        sig_has_autosync = False
        for sig in signatures:
            sig_id = str(sig.get("id") or "").upper()
            sig_tags = [
                str(tag).lower()
                for tag in (sig.get("tags") or [])
                if isinstance(tag, str)
            ]
            if sig_id.startswith("AUTOSYNC") or "autosync" in sig_tags:
                sig_has_autosync = True
                break
        event_autosync = (
            "AUTOSYNC" in step_upper
            or sig_has_autosync
            or "autosync" in tags
        )
        if not event_autosync:
            continue
        started = True
        state = details.get("state") or {}
        terminal_state = str(state.get("terminal_state") or "").upper()
        matched_success = state.get("matched_success") or []
        success_from_state = (
            terminal_state == "SUCCESS"
            and (
                sig_has_autosync
                or any(str(item).upper().startswith("AUTOSYNC") for item in matched_success)
            )
        )
        status_upper = str(ev.get("status") or "").upper()
        success_from_status = sig_has_autosync and status_upper == "PASS"
        if success_from_state or success_from_status:
            success = True
    return started, success


# ----------------------- PUBLIC ENTRYPOINT ----------------------- #

def build_timeline_and_summary(
    session_id: str,
    scenario_name: str,
    raw_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    snapshots = _extract_snapshots(raw_events)
    before_snap = snapshots.get(STATE_LABEL_BEFORE)
    after_snap = snapshots.get(STATE_LABEL_AFTER)

    user_answers = _extract_user_answers(raw_events)
    volume_probe = _extract_volume_probe(raw_events, user_answers)
    log_brand = _derive_log_brand(before_snap, after_snap, raw_events)
    event_autosync_started, event_autosync_success = detect_autosync_from_events(raw_events)
    log_text = load_logcat_text(session_id)
    log_evidence = analyze_log_evidence(log_text, log_brand)
    log_evidence.autosync_started = event_autosync_started or log_evidence.autosync_started
    log_evidence.autosync_success = event_autosync_success or log_evidence.autosync_success

    resolved_scenario_name = scenario_name or "UNKNOWN"
    if not resolved_scenario_name or resolved_scenario_name.upper() == "UNKNOWN":
        resolved_scenario_name = _infer_scenario_name(raw_events)

    timeline_rows, missing_critical = _build_timeline_rows(
        raw_events=raw_events,
        user_answers=user_answers,
        before_snap=before_snap,
        after_snap=after_snap,
        volume_probe=volume_probe,
        log_brand=log_evidence.log_brand,
        log_evidence=log_evidence,
    )

    summary, analyzer_result = _build_session_summary(
        session_id=session_id,
        scenario_name=resolved_scenario_name,
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

    _apply_volume_probe_to_rows(rows_by_name, volume_probe)

    rows = sorted(
        rows_by_name.values(),
        key=lambda r: (r.timestamp or "", r.name),
    )
    present_critical = {row.name for row in rows if row.name in CRITICAL_STEPS}
    missing_critical = CRITICAL_STEPS - present_critical
    return rows, missing_critical


def _friendly_label(name: str) -> str:
    mapping = {
        "question_manual_trigger": "Manual trigger",
        "question_tv_volume_changed": "TV volume changed",
        "question_tv_osd_seen": "TV OSD seen",
        "question_pairing_screen_seen": "Pairing screen",
        "question_tv_brand_ui": "TV brand (UI vs log)",
        "question_notes": "Tester notes",
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
    return False


def _derive_telemetry_state(
    *,
    tv_control_evidence: bool,
    log_evidence: LogEvidence,
    normalized_probe_state: str,
    probe_confidence: float,
) -> TelemetryState:
    if (
        tv_control_evidence
        or normalized_probe_state == "TV"
        or log_evidence.osd_tv
        or log_evidence.cec_events_detected
        or (log_evidence.volume_source or "").strip().upper() == "TV"
    ):
        return "TV_CONTROL"
    strong_probe_negative = (
        normalized_probe_state in {"STB", "NO_TV_CONTROL"}
        and probe_confidence >= PROBE_CONFIDENCE_CONFIDENT
    ) or (log_evidence.osd_stb and probe_confidence >= PROBE_CONFIDENCE_CONFIDENT)
    if strong_probe_negative:
        return "STB_CONTROL_CONFIDENT"
    return "UNKNOWN"


def _resolve_metric_status_from_tester(
    *,
    tester_yes: bool,
    tester_no: bool,
    telemetry_state: TelemetryState,
    analyzer_ready: bool,
) -> tuple[MetricStatus, bool]:
    if not analyzer_ready:
        return "NOT_EVALUATED", False
    if tester_no:
        return "FAIL", True
    if telemetry_state == "STB_CONTROL_CONFIDENT":
        return "INCOMPATIBILITY", True
    if tester_yes:
        if telemetry_state == "UNKNOWN":
            return "INCOMPATIBILITY", False
        return "OK", False
    if telemetry_state == "UNKNOWN":
        return "INCOMPATIBILITY", False
    return "OK", False


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


def _collect_probe_state(volume_row: Optional[StepRow], log_evidence: LogEvidence) -> tuple[str, float]:
    if volume_row:
        detection_state_raw = str(volume_row.details.get("volume_probe_detection_state") or "").strip().upper()
        source_raw = str(volume_row.details.get("volume_probe_source") or "").strip().upper()
        confidence_raw = _safe_float(volume_row.details.get("volume_probe_confidence"))
    else:
        detection_state_raw = ""
        source_raw = ""
        confidence_raw = None

    detection_state = detection_state_raw
    if detection_state == "TV_CONTROL":
        detection_state = "TV"
    elif detection_state == "STB_CONTROL":
        detection_state = "STB"
    elif detection_state == "NO_TV_CONTROL":
        detection_state = "NO_TV_CONTROL"
    elif detection_state in {"UNKNOWN", "NONE"}:
        detection_state = "UNKNOWN"

    if source_raw in {"TV", "STB", "UNKNOWN"}:
        source = source_raw
    else:
        source = ""

    fallback = str(log_evidence.volume_source or "").strip().upper()
    if fallback and fallback not in {"TV", "STB"}:
        fallback = ""

    state = detection_state or source or fallback or "UNKNOWN"
    confidence = confidence_raw if confidence_raw is not None else 0.0
    return state, confidence


def _volume_probe_metadata_present(row: Optional[StepRow]) -> bool:
    if not row:
        return False
    for key in ("volume_probe_state", "volume_probe_source", "volume_probe_detection_state", "volume_probe_confidence"):
        if key not in row.details:
            continue
        value = row.details.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return True
        else:
            return True
    return False


def _timeline_has_probe_event(raw_events: List[Dict[str, Any]], timeline_rows: List[StepRow]) -> bool:
    probe_names = {name.lower() for name in PROBE_EVENT_NAMES}
    for row in timeline_rows:
        if row.name.lower() in probe_names:
            return True
    for event in raw_events:
        step_name = str(event.get("step_name") or "").strip().lower()
        if step_name in probe_names:
            return True
    return False


def _has_autosync_signal(
    *,
    tv_brand_log: Optional[str],
    log_evidence: LogEvidence,
    volume_row: Optional[StepRow],
    tv_control_evidence: bool,
    raw_events: List[Dict[str, Any]],
    timeline_rows: List[StepRow],
) -> bool:
    if tv_brand_log or log_evidence.log_brand:
        return True
    if _volume_probe_metadata_present(volume_row):
        return True
    if log_evidence.volume_source:
        return True
    if tv_control_evidence or log_evidence.osd_tv or log_evidence.osd_stb:
        return True
    if _timeline_has_probe_event(raw_events, timeline_rows):
        return True
    return False


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
) -> Tuple[List[FailureInsight], Dict[str, Any], List[str], str]:
    root_causes: List[FailureInsight] = []
    recs: List[str] = []
    probe_state, probe_confidence = _collect_probe_state(volume_row, log_evidence)

    if volume_no:
        _add_root_cause(root_causes, recs, "tester_saw_no_volume_change", "Tester did not observe TV volume change.")
    if osd_no:
        _add_root_cause(root_causes, recs, "tester_saw_no_osd", "Tester did not observe TV OSD.")

    probe_inconclusive = (probe_state in {"UNKNOWN", "NONE"} or not probe_state) and not tv_control_evidence
    if probe_inconclusive:
        _add_root_cause(
            root_causes,
            recs,
            "volume_probe_inconclusive",
            "Volume probe returned UNKNOWN; no evidence of TV control.",
        )

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
    if telemetry_state == "STB_CONTROL_CONFIDENT":
        reason = "Probe indicates STB controls volume/OSD despite tester confirmation."
        if log_evidence.volume_source:
            reason = f"Probe indicates {log_evidence.volume_source} controls volume/OSD despite tester confirmation."
        _add_root_cause(
            root_causes,
            recs,
            "probe_detected_stb_control",
            reason,
        )
    if brand_mismatch:
        _add_root_cause(
            root_causes,
            recs,
            "brand_mismatch_detected",
            "Tester brand does not match logs.",
        )

    evidence_block = {
        "tv_brand_detected": tv_brand_detected,
        "ir_commands_sent": log_evidence.ir_commands_sent,
        "cec_events_detected": log_evidence.cec_events_detected,
        "tv_osd_events": log_evidence.osd_tv,
        "tv_volume_events": tv_control_evidence,
        "volume_probe_state": probe_state or "UNKNOWN",
        "volume_probe_confidence": probe_confidence,
    }

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
    probe_state, probe_confidence = _collect_probe_state(volume_row, log_evidence)
    normalized_probe_state = (probe_state or "").strip().upper() or "UNKNOWN"
    telemetry_state = _derive_telemetry_state(
        tv_control_evidence=tv_control_evidence,
        log_evidence=log_evidence,
        normalized_probe_state=normalized_probe_state,
        probe_confidence=probe_confidence,
    )

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

    if (
        not log_evidence.autosync_started
        and _has_autosync_signal(
            tv_brand_log=tv_brand_log,
            log_evidence=log_evidence,
            volume_row=volume_row,
            tv_control_evidence=tv_control_evidence,
            raw_events=raw_events,
            timeline_rows=timeline_rows,
        )
    ):
        log_evidence.autosync_started = True

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
    autosync_never_started = final_stage and not log_evidence.autosync_started
    autosync_failed = final_stage and log_evidence.autosync_started and not log_evidence.autosync_success
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
    elif autosync_failed:
        log_verdict = "FAIL"
        log_failure_reason = "Auto-sync did not complete successfully in logs."
    elif telemetry_confident_failure:
        log_verdict = "FAIL"
        log_failure_reason = "Telemetry indicates STB is controlling volume/OSD despite tester confirmation."
    elif telemetry_inconclusive:
        log_verdict = "INCONCLUSIVE"
        log_failure_reason = None
    else:
        log_verdict = "PASS"
        log_failure_reason = None
    conflict_tester_vs_logs = functional_pass and log_verdict == "FAIL"

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
        log_evidence.autosync_started
        and log_evidence.autosync_success
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
    )

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
        summary_row.details["autosync_started"] = log_evidence.autosync_started
        summary_row.details["autosync_success"] = final_autosync_success
        summary_row.details["failure_insights"] = [ins.model_dump(mode="json") for ins in failure_insights]
        summary_row.details["evidence"] = evidence_block
        summary_row.details["recommendations"] = recs
        summary_row.details["confidence"] = confidence
        summary_row.details["confidence_level"] = confidence

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
