# File: src/quickset/state_snapshot.py
"""Helpers for capturing and comparing QuickSet related state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass
class QuicksetStateSnapshot:
    data: Dict[str, Any]
    label: str


_SETTING_NAMESPACES: Iterable[str] = ("global", "secure", "system")
_STATE_KEYS = (
    "change_volume_control_enable",
    "current_volume_source",
    "tv_device_name",
    "avr_device_name",
    "volume_keys_control_tv",
)


def _read_setting(adb_client: Any, key: str) -> Optional[str]:
    for namespace in _SETTING_NAMESPACES:
        try:
            value = adb_client.run_shell(f"settings get {namespace} {key}")
        except Exception:  # pragma: no cover
            continue
        if not value:
            continue
        lowered = value.strip().lower()
        if lowered in {"", "null", "unknown"}:
            continue
        return value.strip()
    return None


def capture_quickset_state(adb_client: Any, step_logger: Any, label: str) -> QuicksetStateSnapshot:
    """Capture a best-effort snapshot of QuickSet/volume state."""
    snapshot_data: Dict[str, Any] = {}
    for key in _STATE_KEYS:
        snapshot_data[key] = _read_setting(adb_client, key)

    snapshot = QuicksetStateSnapshot(snapshot_data, label)
    step_logger.log_step("state_snapshot", "INFO", {"label": label, "data": snapshot_data})
    return snapshot


def diff_quickset_state(
    before: QuicksetStateSnapshot,
    after: QuicksetStateSnapshot,
) -> Dict[str, Any]:
    before_data = before.data if before else {}
    after_data = after.data if after else {}

    changed: Dict[str, Dict[str, Any]] = {}
    unchanged = []
    missing_in_before = []
    missing_in_after = []

    all_keys = set(before_data) | set(after_data)
    for key in sorted(all_keys):
        in_before = key in before_data
        in_after = key in after_data

        if not in_before and in_after:
            missing_in_before.append(key)
            continue
        if in_before and not in_after:
            missing_in_after.append(key)
            continue

        before_value = before_data.get(key)
        after_value = after_data.get(key)
        if before_value == after_value:
            unchanged.append(key)
        else:
            changed[key] = {"before": before_value, "after": after_value}

    return {
        "changed": changed,
        "unchanged": unchanged,
        "missing_in_before": missing_in_before,
        "missing_in_after": missing_in_after,
        "before_label": before.label if before else None,
        "after_label": after.label if after else None,
    }
