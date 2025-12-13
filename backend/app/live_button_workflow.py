from __future__ import annotations

import re
import subprocess
import time
import xml.etree.ElementTree as ET
from typing import Callable, Optional, Sequence, Tuple

from src.adb.adb_client import ADBClient

LIVE_APP_PACKAGE = "il.co.partnertv.atv"
LIVE_LOG_TAG = "QA_LIVE"
SETTINGS_COMPONENT_CANDIDATES = (
    "com.google.android.tv.settings/.MainSettings",
    "com.android.tv.settings/.MainSettings",
)
HEBREW_PROMPT_TOKEN = "הזן את מספר הערוץ"
GUIDANCE_TITLE_ID = "com.android.tv.settings:id/guidance_title"
GUIDED_ACTION_EDIT_ID = "com.android.tv.settings:id/guidedactions_item_title"
ALLOWED_FOCUS_PACKAGES = {
    "com.google.android.tvlauncher",
    "com.google.android.tvlauncherx",
    "com.android.tvlauncher",
    "com.android.launcher",
    "com.android.systemui",
    "com.android.tv.settings",
    LIVE_APP_PACKAGE,
}


def configure_live_mapping(
    adb_client: ADBClient,
    session_id: str,
    expected_channel: int,
    *,
    navigation_delay: float = 0.5,
    settle_delay: float = 2.0,
) -> None:
    """Configure the Live button mapping through Android TV settings."""
    _emit_marker(adb_client, session_id, f"CONFIG_START expected={expected_channel}")
    component = _prepare_settings_focus(adb_client, session_id)
    _emit_marker(adb_client, session_id, f"SETTINGS_FOCUSED package={component}")
    _emit_marker(adb_client, session_id, "NAV_TO_LIVE_MAPPING")
    _navigate_to_live_customization(adb_client, navigation_delay)
    xml_data = _ensure_live_channel_screen(adb_client, session_id)
    _set_channel_value(adb_client, session_id, expected_channel, initial_xml=xml_data)
    time.sleep(settle_delay)
    _emit_marker(adb_client, session_id, f"CONFIG_DONE expected={expected_channel}")


def ensure_device_focus_ready(
    adb_client: ADBClient,
    session_id: str,
    *,
    timeout: float = 20.0,
) -> str:
    """
    Attempt to recover the device from a third-party app back to a controllable state.
    This helper never raises solely because the focus is unknown; it best-effort recovers
    and returns the latest package identifier (or 'unknown').
    """
    deadline = time.time() + timeout
    last_focus = "unknown"
    while time.time() < deadline:
        pkg = _detect_current_package(adb_client)
        if pkg:
            last_focus = pkg
        if pkg and _is_allowed_focus_package(pkg):
            return pkg
        _emit_marker(adb_client, session_id, f"FOCUS_RECOVERY package={pkg or 'unknown'}")
        _exit_to_home(adb_client)
        component = _resolve_settings_component(adb_client)
        _launch_live_button_settings(adb_client, component)
        time.sleep(2.0)
    return last_focus


def live_phase_press(
    adb_client: ADBClient,
    session_id: str,
    phase_label: str,
    expected_channel: int,
    *,
    do_force_stop: bool = False,
    do_reboot: bool = False,
    wait_after_press: float = 8.0,
    reboot_timeout: float = 90.0,
    post_reboot_callback: Optional[Callable[[], None]] = None,
) -> None:
    """Execute a Live-button verification phase (press, kill+press, reboot+press)."""
    normalized_phase = phase_label.strip().upper() or "PHASE1"
    _emit_marker(adb_client, session_id, f"{normalized_phase}_START expected={expected_channel}")

    if do_reboot:
        _emit_marker(adb_client, session_id, f"{normalized_phase}_REBOOT_INIT")
        _reboot_device(adb_client, reboot_timeout=reboot_timeout)
        _emit_marker(adb_client, session_id, f"{normalized_phase}_DEVICE_READY")
        if post_reboot_callback:
            post_reboot_callback()

    if do_force_stop:
        _emit_marker(adb_client, session_id, f"{normalized_phase}_FORCE_STOP")
        adb_client.shell(f"am force-stop {LIVE_APP_PACKAGE}")
        time.sleep(3.0)

    adb_client.shell("input keyevent 172")
    _emit_marker(adb_client, session_id, "LIVE_KEY_SENT")
    time.sleep(wait_after_press)
    _emit_marker(adb_client, session_id, f"{normalized_phase}_END verdict=PENDING")


def _emit_marker(adb_client: ADBClient, session_id: str, message: str) -> None:
    escaped = message.replace('"', '\\"')
    adb_client.shell(f'log -t {LIVE_LOG_TAG} "SESSION={session_id} {escaped}"', check=False)
    time.sleep(0.2)


def _prepare_settings_focus(adb_client: ADBClient, session_id: str) -> str:
    _emit_marker(adb_client, session_id, "SETTINGS_OPEN_START")
    try:
        _exit_to_home(adb_client)
        component = _resolve_settings_component(adb_client)
        _launch_live_button_settings(adb_client, component)
        _wait_for_settings_focus(adb_client, component)
        _emit_marker(adb_client, session_id, f"SETTINGS_OPEN_OK package={component}")
        return component
    except Exception as exc:  # noqa: BLE001
        _emit_marker(adb_client, session_id, f"SETTINGS_OPEN_FAIL error={exc}")
        raise


def _exit_to_home(adb_client: ADBClient) -> None:
    for _ in range(2):
        adb_client.shell("input keyevent 3")  # KEYCODE_HOME
        time.sleep(1.0)


def _resolve_settings_component(adb_client: ADBClient) -> str:
    try:
        packages = adb_client.shell("pm list packages | grep tv.settings", check=False) or ""
    except Exception:
        packages = ""
    packages_lower = packages.lower()
    for candidate in SETTINGS_COMPONENT_CANDIDATES:
        pkg = candidate.split("/")[0]
        if pkg.lower() in packages_lower:
            return candidate
    return SETTINGS_COMPONENT_CANDIDATES[0]


def _launch_live_button_settings(adb_client: ADBClient, component: str) -> None:
    adb_client.shell(f"am start -a android.intent.action.MAIN -n {component}")
    time.sleep(3.0)


def _wait_for_settings_focus(adb_client: ADBClient, component: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    component_pkg = component.split("/")[0]
    while time.time() < deadline:
        focus_pkg = _detect_current_package(adb_client) or ""
        if component_pkg in focus_pkg:
            return
        time.sleep(1.0)
    raise RuntimeError(
        f"Timed out waiting for Settings focus (expected {component_pkg}). "
        f"Current focus: {_get_current_focus(adb_client)}"
    )


def _navigate_to_live_customization(adb_client: ADBClient, delay: float) -> None:
    """
    Navigate through Settings -> Remotes & Accessories -> PartnerRC -> Live button customization.
    The DPAD sequence errs on the side of redundancy to accommodate UI differences.
    """
    navigation_sequences: Sequence[Sequence[str]] = [
        ("DPAD_RIGHT", "DPAD_RIGHT", "DPAD_DOWN", "DPAD_DOWN", "DPAD_DOWN", "DPAD_CENTER"),
        ("DPAD_DOWN", "DPAD_DOWN", "DPAD_CENTER"),
        ("DPAD_DOWN", "DPAD_CENTER"),
    ]
    for sequence in navigation_sequences:
        for key in sequence:
            _send_keyevent(adb_client, key)
            time.sleep(delay)


def _ensure_live_channel_screen(adb_client: ADBClient, session_id: str, *, timeout: float = 18.0) -> str:
    deadline = time.time() + timeout
    last_xml = ""
    while time.time() < deadline:
        xml_data = _dump_ui_xml(adb_client)
        last_xml = xml_data
        if _is_live_channel_screen(xml_data):
            _emit_marker(adb_client, session_id, "LIVE_CHANNEL_SCREEN_OK")
            return xml_data
        time.sleep(1.0)
    _emit_marker(adb_client, session_id, "LIVE_CHANNEL_SCREEN_FAIL")
    raise RuntimeError("Live channel customization screen not detected.")


def _set_channel_value(
    adb_client: ADBClient,
    session_id: str,
    expected_channel: int,
    *,
    initial_xml: Optional[str] = None,
) -> None:
    xml_data = initial_xml
    for attempt in range(3):
        if not xml_data:
            xml_data = _dump_ui_xml(adb_client)
        edit_node = _find_edit_node(xml_data)
        if edit_node is None:
            raise RuntimeError("Live channel EditText not found in UI dump.")
        if edit_node.attrib.get("focused") != "true":
            bounds = edit_node.attrib.get("bounds")
            if bounds:
                x, y = _tap_bounds_center(bounds)
                adb_client.shell(f"input tap {x} {y}")
                time.sleep(0.4)
                xml_data = _dump_ui_xml(adb_client)
                edit_node = _find_edit_node(xml_data) or edit_node

        _emit_marker(
            adb_client,
            session_id,
            f"CHANNEL_SET_ATTEMPT expected={expected_channel} attempt={attempt + 1}",
        )
        _clear_edit_text(adb_client)
        adb_client.shell(f"input text {expected_channel}")
        time.sleep(0.5)
        adb_client.shell("input keyevent KEYCODE_ENTER")
        time.sleep(0.4)
        xml_data = _dump_ui_xml(adb_client)
        new_value = _extract_edit_text_value(xml_data) or ""
        ok = new_value == str(expected_channel)
        if ok:
            _emit_marker(
                adb_client,
                session_id,
                f"CHANNEL_SET_RESULT expected={expected_channel} observed={new_value} ok=true",
            )
            return
        _emit_marker(
            adb_client,
            session_id,
            f"CHANNEL_SET_RESULT expected={expected_channel} observed={new_value or 'unknown'} ok=false attempt={attempt + 1}",
        )
    raise RuntimeError(f"Unable to set Live button channel to {expected_channel}.")


def _clear_edit_text(adb_client: ADBClient, deletions: int = 15) -> None:
    adb_client.shell("input keyevent KEYCODE_MOVE_END")
    time.sleep(0.1)
    for _ in range(deletions):
        adb_client.shell("input keyevent KEYCODE_DEL")
        time.sleep(0.05)


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


def _tap_bounds_center(bounds: str) -> Tuple[int, int]:
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
    if not match:
        return (0, 0)
    x1, y1, x2, y2 = map(int, match.groups())
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def _send_keyevent(adb_client: ADBClient, key_token: str) -> None:
    token = key_token.strip().upper()
    prefix = "" if token.startswith("KEYCODE_") else "KEYCODE_"
    adb_client.shell(f"input keyevent {prefix}{token}")


def _reboot_device(adb_client: ADBClient, *, reboot_timeout: float) -> None:
    cmd = [adb_client.adb_path, "-s", adb_client.target, "reboot"]
    subprocess.run(cmd, check=True)
    wait_cmd = [adb_client.adb_path, "-s", adb_client.target, "wait-for-device"]
    subprocess.run(wait_cmd, check=True, timeout=reboot_timeout)
    _wait_for_boot_completed(adb_client, timeout=reboot_timeout)
    time.sleep(8.0)


def _wait_for_boot_completed(adb_client: ADBClient, *, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            output = (adb_client.shell("getprop sys.boot_completed", check=False) or "").strip()
        except Exception:
            output = ""
        if output == "1":
            return
        time.sleep(3.0)
    raise TimeoutError("Timed out waiting for STB to complete boot sequence.")


def _get_current_focus(adb_client: ADBClient) -> str:
    try:
        focus_line = adb_client.shell(
            "dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'",
            check=False,
        ) or ""
    except Exception:
        focus_line = ""
    return focus_line.strip()


def _detect_current_package(adb_client: ADBClient) -> Optional[str]:
    focus_line = _get_current_focus(adb_client)
    match = re.search(r"([A-Za-z0-9_.]+)/", focus_line)
    if match:
        return match.group(1)
    return _get_package_from_ui_dump(adb_client)


def _get_package_from_ui_dump(adb_client: ADBClient) -> Optional[str]:
    try:
        xml_data = _dump_ui_xml(adb_client)
    except Exception:
        return None
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return None
    first_node = next(root.iter("node"), None)
    if first_node is None:
        return None
    return first_node.attrib.get("package")


def _get_current_focus_package(adb_client: ADBClient) -> Optional[str]:
    return _detect_current_package(adb_client)


def _is_allowed_focus_package(pkg: str) -> bool:
    normalized = pkg.lower()
    return any(allowed in normalized for allowed in ALLOWED_FOCUS_PACKAGES)


def _dump_ui_xml(adb_client: ADBClient) -> str:
    dump_path = f"/sdcard/qa_live_dump_{int(time.time() * 1000)}.xml"
    try:
        adb_client.shell(f"uiautomator dump {dump_path}")
        xml_data = adb_client.shell(f"cat {dump_path}", check=False) or ""
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Unable to capture UIAutomator dump ({exc}).") from exc
    finally:
        adb_client.shell(f"rm {dump_path}", check=False)
    return xml_data


def _is_live_channel_screen(xml_data: str) -> bool:
    if not xml_data:
        return False
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return False
    guidance_match = False
    edit_text_present = False
    for node in root.iter("node"):
        resource_id = node.attrib.get("resource-id", "")
        text_value = node.attrib.get("text", "")
        class_name = node.attrib.get("class", "")
        if resource_id == GUIDANCE_TITLE_ID and HEBREW_PROMPT_TOKEN in text_value:
            guidance_match = True
        if resource_id == GUIDED_ACTION_EDIT_ID and "EditText" in class_name:
            edit_text_present = True
    return guidance_match or edit_text_present


def _extract_edit_text_value(xml_data: str) -> Optional[str]:
    node = _find_edit_node(xml_data)
    if not node:
        return None
    return node.attrib.get("text", "")
