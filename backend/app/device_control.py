from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.adb.adb_client import ADBClient

FOCUS_PATTERN = re.compile(r"mCurrentFocus=Window\{[^\s]+\s+([A-Za-z0-9_.]+)/([A-Za-z0-9_.]+)\}")
FOCUSED_APP_PATTERN = re.compile(r"mFocusedApp=AppWindowToken\{[^\s]+\s+token=Token\{[^\s]+\s+([A-Za-z0-9_.]+)/([A-Za-z0-9_.]+)\}")
GUIDANCE_TITLE_ID = "com.android.tv.settings:id/guidance_title"
GUIDED_ACTION_EDIT_ID = "com.android.tv.settings:id/guidedactions_item_title"
GUIDANCE_PROMPT_PRIMARY = "הזן את מספר הערוץ"
GUIDANCE_PROMPT_FALLBACK = "ערוץ"


@dataclass
class FocusInfo:
    package: Optional[str]
    activity: Optional[str]
    raw: str = ""
    source: str = "unknown"


class LiveChannelSetError(RuntimeError):
    def __init__(self, message: str, details: Dict[str, Any]):
        super().__init__(message)
        self.details = details


def get_current_focus(adb_client: ADBClient) -> FocusInfo:
    try:
        window_output = adb_client.shell("dumpsys window windows", check=False) or ""
    except Exception:
        window_output = ""
    focus = _parse_focus_from_window(window_output)
    if focus:
        return focus
    try:
        activity_output = adb_client.shell("dumpsys activity activities", check=False) or ""
    except Exception:
        activity_output = ""
    focus = _parse_focus_from_activity(activity_output)
    if focus:
        return focus
    return FocusInfo(package=None, activity=None, raw=window_output.strip() or activity_output.strip(), source="unavailable")


def _parse_focus_from_window(raw_output: str) -> Optional[FocusInfo]:
    if not raw_output:
        return None
    for pattern in (FOCUS_PATTERN, FOCUSED_APP_PATTERN):
        match = pattern.search(raw_output)
        if match:
            pkg, activity = match.groups()
            return FocusInfo(pkg, activity, raw_output.strip(), source="dumpsys_window")
    return None


RESUMED_PATTERN = re.compile(r"mResumedActivity:.*? ([A-Za-z0-9_.]+)/([A-Za-z0-9_.]+)")


def _parse_focus_from_activity(raw_output: str) -> Optional[FocusInfo]:
    if not raw_output:
        return None
    match = RESUMED_PATTERN.search(raw_output)
    if match:
        pkg, activity = match.groups()
        return FocusInfo(pkg, activity, raw_output.strip(), source="dumpsys_activity")
    return None


def escape_to_home(
    adb_client: ADBClient,
    *,
    allowed_packages: Optional[Iterable[str]] = None,
    max_steps: int = 3,
    delay: float = 0.6,
) -> FocusInfo:
    allowed = {pkg.lower() for pkg in (allowed_packages or [])}
    focus = get_current_focus(adb_client)
    pkg_lower = (focus.package or "").lower()
    if allowed and pkg_lower in allowed:
        return focus
    for _ in range(max_steps):
        adb_client.shell("input keyevent KEYCODE_HOME")
        time.sleep(delay)
        adb_client.shell("input keyevent KEYCODE_HOME")
        time.sleep(delay)
        adb_client.shell("input keyevent KEYCODE_BACK")
        time.sleep(delay)
        focus = get_current_focus(adb_client)
        pkg_lower = (focus.package or "").lower()
        if not allowed or pkg_lower in allowed:
            return focus
    return focus


def force_stop_if_running(adb_client: ADBClient, packages: Sequence[str]) -> None:
    for pkg in packages:
        try:
            adb_client.shell(f"am force-stop {pkg}", check=False)
        except Exception:
            continue


def uia_dump_xml(adb_client: ADBClient) -> str:
    dump_path = f"/sdcard/qa_live_dump_{int(time.time() * 1000)}.xml"
    try:
        adb_client.shell(f"uiautomator dump {dump_path}")
        xml_data = adb_client.shell(f"cat {dump_path}", check=False) or ""
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Unable to capture UIAutomator dump ({exc}).") from exc
    finally:
        adb_client.shell(f"rm {dump_path}", check=False)
    return xml_data


def xml_has_live_channel_prompt(xml_data: str) -> bool:
    if not xml_data:
        return False
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return False
    package_match = False
    guidance_match = False
    edit_text_present = False
    for node in root.iter("node"):
        pkg_attr = (node.attrib.get("package") or "").strip()
        if pkg_attr.startswith("com.android.tv.settings"):
            package_match = True
        resource_id = node.attrib.get("resource-id", "")
        text_value = (node.attrib.get("text") or "").strip()
        class_name = node.attrib.get("class", "")
        if resource_id == GUIDANCE_TITLE_ID and (
            GUIDANCE_PROMPT_PRIMARY in text_value or GUIDANCE_PROMPT_FALLBACK in text_value
        ):
            guidance_match = True
        if resource_id == GUIDED_ACTION_EDIT_ID and "EditText" in class_name:
            edit_text_present = True
    return package_match and guidance_match and edit_text_present


def read_live_channel_value(xml_data: str) -> Optional[int]:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return None
    for node in root.iter("node"):
        if node.attrib.get("resource-id") != GUIDED_ACTION_EDIT_ID:
            continue
        text_value = (node.attrib.get("text") or "").strip()
        if not text_value:
            return None
        try:
            return int(text_value)
        except ValueError:
            return None
    return None


def set_live_channel_value(
    adb_client: ADBClient,
    expected_channel: int,
    *,
    initial_xml: Optional[str] = None,
    max_attempts: int = 2,
) -> Dict[str, Any]:
    xml_data = initial_xml
    attempts: List[Dict[str, Any]] = []
    for attempt_index in range(max_attempts):
        confirm_method = "enter_only" if attempt_index == 0 else "back_then_enter"
        if not xml_data:
            xml_data = uia_dump_xml(adb_client)
        edit_node = _find_edit_node(xml_data)
        if edit_node is None:
            raise LiveChannelSetError(
                "Live channel field not found.",
                {"attempts": attempts, "diagnostics_excerpt": _xml_excerpt(xml_data)},
            )
        if edit_node.attrib.get("focused") != "true":
            _tap_edit_node(adb_client, edit_node)
            time.sleep(0.3)
            xml_data = uia_dump_xml(adb_client)
            edit_node = _find_edit_node(xml_data) or edit_node

        _clear_edit_text(adb_client)
        adb_client.shell(f"input text {expected_channel}")
        time.sleep(0.5)

        if confirm_method == "enter_only":
            adb_client.shell("input keyevent KEYCODE_ENTER")
        else:
            adb_client.shell("input keyevent KEYCODE_BACK")
            time.sleep(0.2)
            adb_client.shell("input keyevent KEYCODE_ENTER")

        time.sleep(0.6)
        xml_data = uia_dump_xml(adb_client)
        value_after = read_live_channel_value(xml_data)
        attempts.append({"confirm_method": confirm_method, "value_after": value_after})
        if value_after == expected_channel:
            return {
                "value_after": value_after,
                "confirm_method_used": confirm_method,
                "retries": attempt_index,
                "attempts": attempts,
            }

    raise LiveChannelSetError(
        "Live channel value did not match expected input.",
        {
            "attempts": attempts,
            "value_after": attempts[-1].get("value_after") if attempts else None,
            "diagnostics_excerpt": _xml_excerpt(xml_data or ""),
        },
    )


def build_diagnostics_excerpt(adb_client: ADBClient, *, xml_data: Optional[str] = None) -> str:
    try:
        focus_dump = adb_client.shell("dumpsys window windows | tail -n 30", check=False) or ""
    except Exception:
        focus_dump = ""
    snippet = ""
    source_xml = xml_data
    if source_xml is None:
        try:
            source_xml = uia_dump_xml(adb_client)
        except Exception:
            source_xml = ""
    if source_xml:
        snippet = "\n".join(source_xml.splitlines()[:15])
    combined = (focus_dump.strip(), snippet.strip())
    return "\n---\n".join(part for part in combined if part)


def _find_edit_node(xml_data: str) -> Optional[ET.Element]:
    if not xml_data:
        return None
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return None
    for node in root.iter("node"):
        if node.attrib.get("resource-id") == GUIDED_ACTION_EDIT_ID:
            return node
    return None


def _tap_edit_node(adb_client: ADBClient, node: ET.Element) -> None:
    bounds = node.attrib.get("bounds") or ""
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not match:
        return
    x1, y1, x2, y2 = map(int, match.groups())
    x = (x1 + x2) // 2
    y = (y1 + y2) // 2
    adb_client.shell(f"input tap {x} {y}")


def _clear_edit_text(adb_client: ADBClient, repetitions: int = 12) -> None:
    adb_client.shell("input keyevent KEYCODE_MOVE_END")
    time.sleep(0.1)
    for _ in range(repetitions):
        adb_client.shell("input keyevent KEYCODE_DEL")
        time.sleep(0.05)


def _xml_excerpt(xml_data: str) -> str:
    if not xml_data:
        return ""
    lines = xml_data.splitlines()
    return "\n".join(lines[:15])
