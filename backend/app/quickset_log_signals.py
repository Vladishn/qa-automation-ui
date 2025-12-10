from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

QUICKSET_REFERENCES = (
    "quickset",
    "qsdprint",
    "[uapi]",
    "qs4requesthandlerthread",
    "quicksetapi",
    "qs::quickset",
)

AUTOSYNC_START_MARKERS = (
    "quickset_sendstartsessionmsg",
    "startautosync",
    "autosync start",
    "tv_auto_sync start",
)

AUTOSYNC_COMPLETE_MARKERS = (
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

IR_MARKERS = (
    "sendir",
    "send_ir",
    "ir blaster",
    "ir-blaster",
    "ir tx",
    "sending ir",
    "ir command",
)

CEC_MARKERS = (
    "hdmi-cec",
    "hdmicec",
    "<cec",
    "cec:",
    "cec event",
)

OSD_PATTERNS = (
    "set osd name",
    "tv osd",
    "volume_osd_tv",
    "osd event",
)

BRAND_REGEX = re.compile(r'"brand"\s*:\s*"([^"]+)"', re.IGNORECASE)
VOLUME_SOURCE_REGEXES = (
    re.compile(r'"volume_source"\s*:\s*(?P<value>"[^"]+"|\d+)', re.IGNORECASE),
    re.compile(r'curvolsource\s*[:=]\s*(?P<num>\d+)', re.IGNORECASE),
    re.compile(r'current_volume_source[^\d]*(?P<num>\d+)', re.IGNORECASE),
)
TV_DEVICE_REGEX = re.compile(r'tv[_ ]?device[_ ]?name[^A-Za-z0-9]*(?P<value>[^,;]+)', re.IGNORECASE)
IS_TV_SETUP_REGEX = re.compile(r'is[_ ]?tv[_ ]?setup\s*[:=]\s*(true|false)', re.IGNORECASE)

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


@dataclass
class QuickSetLogSignals:
    quickset_seen: bool = False
    autosync_started: bool = False
    autosync_completed: bool = False
    autosync_errors: List[str] = field(default_factory=list)
    tv_brand_detected: Optional[str] = None
    tv_volume_events: bool = False
    tv_osd_events: bool = False
    ir_commands_sent: bool = False
    cec_events_detected: bool = False
    volume_source_events: List[str] = field(default_factory=list)
    stb_volume_events: bool = False
    tv_config_events: List[str] = field(default_factory=list)
    tv_config_seen: bool = False
    tv_config_cleared_during_run: bool = False


def _clean_log_line(line: str, limit: int = 160) -> str:
    trimmed = line.strip()
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[:limit].rstrip() + "…"


def _line_mentions_quickset(lower_line: str) -> bool:
    return any(marker in lower_line for marker in QUICKSET_REFERENCES)


def _maybe_extract_brand(line: str, lower_line: str) -> Optional[str]:
    if '"brand"' not in lower_line:
        return None
    if not (_line_mentions_quickset(lower_line) or '"devices"' in lower_line):
        return None
    match = BRAND_REGEX.search(line)
    if not match:
        return None
    brand = match.group(1).strip()
    if not brand or brand.lower() in IGNORED_BRANDS:
        return None
    return brand


def _normalize_volume_source(raw_value: str) -> Optional[str]:
    token = raw_value.strip().strip('"').upper()
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
        if value is None:
            continue
        normalized = _normalize_volume_source(value)
        if normalized:
            return normalized
    return None


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


def _append_limited(collection: List[str], value: str, limit: int = 12) -> None:
    if not value:
        return
    collection.append(value)
    if len(collection) > limit:
        del collection[: len(collection) - limit]


def _append_volume_event(signals: QuickSetLogSignals, source: str, limit: int = 60) -> None:
    signals.volume_source_events.append(source)
    if len(signals.volume_source_events) > limit:
        signals.volume_source_events = signals.volume_source_events[-limit:]
    if source == "TV":
        signals.tv_volume_events = True
    elif source == "STB":
        signals.stb_volume_events = True


def extract_quickset_log_signals(lines: Iterable[str]) -> QuickSetLogSignals:
    signals = QuickSetLogSignals()
    tv_config_active = False
    for raw_line in lines:
        if not raw_line:
            continue
        line = raw_line.rstrip()
        lower_line = line.lower()
        if _line_mentions_quickset(lower_line):
            signals.quickset_seen = True

        if any(marker in lower_line for marker in AUTOSYNC_START_MARKERS):
            signals.autosync_started = True

        if any(marker in lower_line for marker in AUTOSYNC_COMPLETE_MARKERS):
            signals.autosync_completed = True

        if any(marker in lower_line for marker in AUTOSYNC_ERROR_MARKERS) or (
            "exception" in lower_line and _line_mentions_quickset(lower_line)
        ):
            cleaned = _clean_log_line(line)
            signals.autosync_errors.append(cleaned)

        brand = _maybe_extract_brand(line, lower_line)
        if brand and not signals.tv_brand_detected:
            signals.tv_brand_detected = brand

        volume_source = _extract_volume_source(line)
        if volume_source in {"TV", "STB", "UNKNOWN"}:
            _append_volume_event(signals, volume_source)

        tv_device_value = _maybe_extract_tv_device(line)
        if tv_device_value is not None:
            cleaned = _clean_log_line(line)
            _append_limited(signals.tv_config_events, cleaned)
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

        if any(pattern in lower_line for pattern in OSD_PATTERNS):
            signals.tv_osd_events = True

        if any(marker in lower_line for marker in IR_MARKERS):
            signals.ir_commands_sent = True

        if "cec" in lower_line and any(marker in lower_line for marker in CEC_MARKERS):
            signals.cec_events_detected = True

    return signals
