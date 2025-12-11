from __future__ import annotations

import re
from datetime import datetime
from enum import Enum, auto
from typing import Iterable, List, Literal, Optional

from pydantic import BaseModel, Field

AUTOSYNC_START_MARKERS = (
    "quickset_sendstartsessionmsg",
    "startautosync",
    "autosync start",
    "tv_auto_sync start",
)

AUTOSYNC_SUCCESS_MARKERS = (
    "quickset_sendendsessionmsg",
    "autosync success",
    "autosync completed",
    "tv_auto_sync success",
)

AUTOSYNC_ERROR_MARKERS = (
    "autosync error",
    "autosync failed",
    "failed to complete autosync",
    "quickset error",
    "qs4requesthandlerthread: exception",
)

TV_OSD_MARKERS = (
    "set osd name",
    "tv osd",
    "volume_osd_tv",
    "hdmi_cec osd",
)

STB_OSD_MARKERS = (
    "systemui volume",
    "droidlogicvolumepanel",
    "stb osd",
    "volume panel stb",
)

BRAND_REGEX = re.compile(r'"brand"\s*:\s*"([^"]+)"', re.IGNORECASE)
VOLUME_SOURCE_REGEXES = (
    re.compile(r'"volume_source"\s*:\s*(?P<value>"[^"]+"|\d+)', re.IGNORECASE),
    re.compile(r'curvolsource\s*[:=]\s*(?P<num>\d+)', re.IGNORECASE),
    re.compile(r'current_volume_source[^\d]*(?P<num>\d+)', re.IGNORECASE),
)
TV_DEVICE_REGEX = re.compile(r'tv[_ ]?device[_ ]?name[^A-Za-z0-9]*(?P<value>[^,;]+)', re.IGNORECASE)
IS_TV_SETUP_REGEX = re.compile(r'is[_ ]?tv[_ ]?setup\s*[:=]\s*(true|false)', re.IGNORECASE)
TIMESTAMP_REGEXES = (
    (re.compile(r'^(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3,})'), "%m-%d %H:%M:%S.%f"),
    (re.compile(r'^(\d{2}-\d{2} \d{2}:\d{2}:\d{2})'), "%m-%d %H:%M:%S"),
)
TV_CONFIG_OFF_VALUES = {
    "",
    "none",
    "null",
    "not setup",
    "not_setup",
    "notset",
    "notconfigured",
    "not configured",
    "unset",
    "n/a",
}

IGNORED_BRANDS = {"", "partner", "network device"}


class ParserState(Enum):
    IDLE = auto()
    SYNCING = auto()
    COMPLETED_OK = auto()
    COMPLETED_ERROR = auto()


class QuicksetLogSignals(BaseModel):
    autosync_started: bool = False
    autosync_completed_successfully: bool = False
    autosync_failed: bool = False
    autosync_error_codes: List[str] = Field(default_factory=list)
    autosync_started_at: Optional[datetime] = None
    autosync_completed_at: Optional[datetime] = None

    volume_source_initial: Literal["STB", "TV", "UNKNOWN"] = "UNKNOWN"
    volume_source_final: Literal["STB", "TV", "UNKNOWN"] = "UNKNOWN"
    volume_source_history: List[str] = Field(default_factory=list)
    volume_switch_events: int = 0

    tv_volume_events: int = 0
    stb_volume_events: int = 0
    tv_osd_events: int = 0
    stb_osd_events: int = 0

    tv_brand_inferred: Optional[str] = None
    raw_markers: List[str] = Field(default_factory=list)

    tv_config_seen: bool = False
    tv_config_cleared_during_run: bool = False
    tv_config_events: List[str] = Field(default_factory=list)

    quickset_seen: bool = False


def _clean_line(line: str, limit: int = 160) -> str:
    trimmed = line.strip()
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[:limit].rstrip() + "…"


def _append_marker(signals: QuicksetLogSignals, value: str, limit: int = 64) -> None:
    if not value:
        return
    signals.raw_markers.append(value)
    if len(signals.raw_markers) > limit:
        del signals.raw_markers[: len(signals.raw_markers) - limit]


def _parse_timestamp(line: str) -> Optional[datetime]:
    for regex, fmt in TIMESTAMP_REGEXES:
        match = regex.search(line)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(1), fmt)
        except Exception:
            continue
    return None


def _normalize_volume_source(value: str) -> Optional[str]:
    token = value.strip().strip('"').upper()
    if not token:
        return None
    if token in {"1", "TV", "TELEVISION"}:
        return "TV"
    if token in {"0", "STB", "SETTOP", "SET_TOP_BOX", "BOX"}:
        return "STB"
    if token == "UNKNOWN":
        return "UNKNOWN"
    return None


def _extract_volume_source(line: str) -> Optional[str]:
    for regex in VOLUME_SOURCE_REGEXES:
        match = regex.search(line)
        if not match:
            continue
        value = match.groupdict().get("value") or match.groupdict().get("num") or match.group(0)
        if not value:
            continue
        normalized = _normalize_volume_source(str(value))
        if normalized:
            return normalized
    return None


def _maybe_extract_brand(line: str) -> Optional[str]:
    match = BRAND_REGEX.search(line)
    if not match:
        return None
    candidate = match.group(1).strip()
    if not candidate or candidate.lower() in IGNORED_BRANDS:
        return None
    return candidate


def _maybe_extract_tv_device(line: str) -> Optional[str]:
    match = TV_DEVICE_REGEX.search(line)
    if not match:
        return None
    return match.group("value").strip().strip('"')


def _maybe_extract_is_tv_setup(line: str) -> Optional[bool]:
    match = IS_TV_SETUP_REGEX.search(line)
    if not match:
        return None
    return match.group(1).lower() == "true"


def _is_config_cleared(value: Optional[str]) -> bool:
    if value is None:
        return False
    lowered = value.strip().strip('"').lower()
    if not lowered:
        return True
    return lowered in TV_CONFIG_OFF_VALUES


def _append_tv_config_event(signals: QuicksetLogSignals, value: str, limit: int = 12) -> None:
    if not value:
        return
    signals.tv_config_events.append(value)
    if len(signals.tv_config_events) > limit:
        signals.tv_config_events = signals.tv_config_events[-limit:]


def _update_volume_sources(signals: QuicksetLogSignals, source: str) -> None:
    if signals.volume_source_initial == "UNKNOWN":
        signals.volume_source_initial = source
    if signals.volume_source_history:
        last = signals.volume_source_history[-1]
        if source != "UNKNOWN" and last != "UNKNOWN" and last != source:
            signals.volume_switch_events += 1
    signals.volume_source_history.append(source)
    if len(signals.volume_source_history) > 60:
        signals.volume_source_history = signals.volume_source_history[-60:]
    signals.volume_source_final = source
    if source == "TV":
        signals.tv_volume_events += 1
    elif source == "STB":
        signals.stb_volume_events += 1


def _increment(value: int) -> int:
    return value + 1 if value < 10_000 else value


def parse_quickset_logs(device_log: str) -> QuicksetLogSignals:
    signals = QuicksetLogSignals()
    state = ParserState.IDLE
    tv_config_active = False

    for raw_line in device_log.splitlines():
        if not raw_line:
            continue
        line = raw_line.rstrip()
        lower = line.lower()
        if "quickset" in lower or "[uapi]" in lower:
            signals.quickset_seen = True

        timestamp = _parse_timestamp(line)

        if any(marker in lower for marker in AUTOSYNC_START_MARKERS):
            signals.autosync_started = True
            if not signals.autosync_started_at and timestamp:
                signals.autosync_started_at = timestamp
            state = ParserState.SYNCING
            _append_marker(signals, "AUTOSYNC_START")

        if any(marker in lower for marker in AUTOSYNC_SUCCESS_MARKERS):
            signals.autosync_completed_successfully = True
            signals.autosync_failed = False
            if not signals.autosync_completed_at and timestamp:
                signals.autosync_completed_at = timestamp
            state = ParserState.COMPLETED_OK
            _append_marker(signals, "AUTOSYNC_SUCCESS")

        if any(marker in lower for marker in AUTOSYNC_ERROR_MARKERS) or (
            "exception" in lower and "quickset" in lower
        ):
            signals.autosync_failed = True
            if timestamp and not signals.autosync_completed_at:
                signals.autosync_completed_at = timestamp
            cleaned = _clean_line(line)
            if cleaned not in signals.autosync_error_codes:
                signals.autosync_error_codes.append(cleaned)
            state = ParserState.COMPLETED_ERROR
            _append_marker(signals, f"AUTOSYNC_ERROR:{cleaned}")

        brand = _maybe_extract_brand(line)
        if brand and not signals.tv_brand_inferred:
            signals.tv_brand_inferred = brand

        volume_source = _extract_volume_source(line)
        if volume_source:
            _update_volume_sources(signals, volume_source)

        tv_device_value = _maybe_extract_tv_device(line)
        if tv_device_value is not None:
            cleaned = _clean_line(line)
            _append_tv_config_event(signals, cleaned)
            if not _is_config_cleared(tv_device_value):
                signals.tv_config_seen = True
                tv_config_active = True
            elif signals.tv_config_seen and tv_config_active:
                signals.tv_config_cleared_during_run = True
                tv_config_active = False

        setup_flag = _maybe_extract_is_tv_setup(line)
        if setup_flag is True:
            signals.tv_config_seen = True
            tv_config_active = True
        elif setup_flag is False and signals.tv_config_seen and tv_config_active:
            signals.tv_config_cleared_during_run = True
            tv_config_active = False

        if any(pattern in lower for pattern in TV_OSD_MARKERS):
            signals.tv_osd_events = _increment(signals.tv_osd_events)
        if any(pattern in lower for pattern in STB_OSD_MARKERS):
            signals.stb_osd_events = _increment(signals.stb_osd_events)

    if signals.volume_source_initial == "UNKNOWN" and signals.volume_source_history:
        signals.volume_source_initial = signals.volume_source_history[0]
    if signals.volume_source_final == "UNKNOWN" and signals.volume_source_history:
        signals.volume_source_final = signals.volume_source_history[-1]
    if state == ParserState.SYNCING and not signals.autosync_completed_successfully and not signals.autosync_failed:
        signals.autosync_failed = True
    return signals


def extract_quickset_log_signals(lines: Iterable[str]) -> QuicksetLogSignals:
    """Backward compatible helper for existing tests that supplied line iterables."""
    return parse_quickset_logs("\n".join(lines))
