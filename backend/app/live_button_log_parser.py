from __future__ import annotations

import re
from typing import Dict, Optional

from pydantic import BaseModel, Field

GUIDE_INTENT_REGEX = re.compile(
    r"partnertv\+\s+guide\s+intent\s+sent\s+with\s+channel\s*:\s*(?P<channel>\d+)",
    re.IGNORECASE,
)
SAVED_CHANNEL_REGEX = re.compile(
    r"saved\s+.*channel\s*:\s*(?P<channel>\d+)",
    re.IGNORECASE,
)
PHASE_ORDER = {"PHASE1": 1, "PHASE2": 2, "PHASE3": 3}


class LiveButtonPhaseSignals(BaseModel):
    phase: str
    live_key_pressed: bool = False
    partnertv_launched: bool = False
    observed_channel: Optional[int] = None
    raw_excerpt: Optional[str] = None


class LiveButtonSignals(BaseModel):
    expected_channel: Optional[int] = None
    config_saved_channel: Optional[int] = None
    phases: list[LiveButtonPhaseSignals] = Field(default_factory=list)
    config_attempted: bool = False
    config_verified: bool = False
    session_logs_found: bool = False

    def get_phase(self, name: str) -> Optional[LiveButtonPhaseSignals]:
        for phase in self.phases:
            if phase.phase == name:
                return phase
        return None


def parse_live_button_logs(
    log_text: str,
    expected_channel: Optional[int] = None,
    session_id: Optional[str] = None,
) -> LiveButtonSignals:
    signals = LiveButtonSignals(expected_channel=expected_channel)
    if not log_text:
        return signals

    phases: Dict[str, LiveButtonPhaseSignals] = {}
    session_token = f"SESSION={session_id}" if session_id else None
    session_seen = False

    def ensure_phase(name: str) -> LiveButtonPhaseSignals:
        phase_name = (name or "").upper()
        if phase_name not in phases:
            phase = LiveButtonPhaseSignals(phase=phase_name)
            phases[phase_name] = phase
            signals.phases.append(phase)
        return phases[phase_name]

    current_phase: Optional[str] = None
    for raw_line in log_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        upper = line.upper()
        lower = line.lower()
        is_qa_line = "QA_LIVE" in upper

        if session_token and is_qa_line and session_token not in line:
            continue

        if is_qa_line:
            if session_token:
                session_seen = True
            if "CONFIG_START" in upper:
                signals.config_attempted = True
                current_phase = "CONFIG"
            elif "PHASE_START" in upper:
                match = re.search(r"PHASE_START\s+NAME\s*=\s*([A-Z0-9_]+)", upper)
                if match:
                    current_phase = match.group(1).strip().upper()
                    ensure_phase(current_phase)
                else:
                    current_phase = None
            elif "PHASE" in upper and "_START" in upper:
                match = re.search(r"(PHASE[0-9]+)_START", upper)
                if match:
                    current_phase = match.group(1).strip().upper()
                    ensure_phase(current_phase)
            elif "PHASE" in upper and "_END" in upper:
                match = re.search(r"(PHASE[0-9]+)_END", upper)
                if match:
                    current_phase = match.group(1).strip().upper()
            elif "LIVE_KEY_SENT" in upper:
                phase = ensure_phase(current_phase or "PHASE1")
                phase.live_key_pressed = True
            elif "CHANNEL_SET_RESULT" in upper:
                signals.config_attempted = True
                expected_match = re.search(r"EXPECTED\s*=\s*(\d+)", upper)
                observed_match = re.search(r"OBSERVED\s*=\s*(\d+)", upper)
                ok = "OK=TRUE" in upper
                if observed_match:
                    try:
                        signals.config_saved_channel = int(observed_match.group(1))
                    except (TypeError, ValueError):
                        pass
                if ok and signals.config_saved_channel is not None:
                    signals.config_verified = True
            continue

        if session_token and not session_seen:
            continue

        saved_match = SAVED_CHANNEL_REGEX.search(line)
        saved_channel = _extract_int(saved_match)
        if saved_channel is not None:
            signals.config_saved_channel = saved_channel

        if ("globalkey" in lower and "172" in lower) or "one key down 172" in lower:
            phase = ensure_phase(current_phase or "PHASE1")
            phase.live_key_pressed = True

        if "activitytaskmanager" in lower and "il.co.partnertv.atv" in lower:
            phase = ensure_phase(current_phase or "PHASE1")
            phase.partnertv_launched = True

        guide_match = GUIDE_INTENT_REGEX.search(line)
        observed_channel = _extract_int(guide_match)
        if observed_channel is not None:
            phase = ensure_phase(current_phase or "PHASE1")
            phase.observed_channel = observed_channel
            if not phase.raw_excerpt:
                phase.raw_excerpt = line

    signals.phases.sort(key=lambda p: PHASE_ORDER.get(p.phase.upper(), 99))
    signals.session_logs_found = session_seen or not bool(session_token)
    return signals


def _extract_int(match: Optional[re.Match[str]]) -> Optional[int]:
    if not match:
        return None
    value = match.groupdict().get("channel") if match.groupdict() else match.group(1)
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
