from __future__ import annotations

import subprocess
import time
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from src.adb.adb_client import ADBClient

from .device_control import (
    LiveChannelSetError,
    build_diagnostics_excerpt,
    escape_to_home,
    force_stop_if_running,
    get_current_focus,
    read_live_channel_value,
    set_live_channel_value,
    uia_dump_xml,
    xml_has_live_channel_prompt,
    FocusInfo,
)

LIVE_APP_PACKAGE = "il.co.partnertv.atv"
LIVE_LOG_TAG = "QA_LIVE"
SETTINGS_COMPONENT_CANDIDATES = (
    "com.google.android.tv.settings/.MainSettings",
    "com.android.tv.settings/.MainSettings",
)
SETTINGS_PACKAGE = "com.android.tv.settings"
HOME_LAUNCHER_PACKAGES = {
    "com.google.android.tvlauncher",
    "com.google.android.tvlauncherx",
    "com.android.tvlauncher",
    "com.android.launcher",
}
THIRD_PARTY_APPS = (
    "com.google.android.youtube.tv",
    "com.netflix.ninja",
)


class LiveConfigurationError(RuntimeError):
    def __init__(self, message: str, details: Dict[str, Any]):
        super().__init__(message)
        self.details = details


def configure_live_mapping(
    adb_client: ADBClient,
    session_id: str,
    expected_channel: int,
    *,
    navigation_delay: float = 0.5,
    settle_delay: float = 2.0,
) -> Dict[str, Any]:
    """Configure the Live button mapping through Android TV settings."""
    details: Dict[str, Any] = {
        "expected_channel": expected_channel,
        "ui_prompt_detected": False,
    }
    try:
        force_stop_if_running(adb_client, THIRD_PARTY_APPS)
        focus_before = get_current_focus(adb_client)
        details["focus_before"] = _format_focus(focus_before)
        normalized_focus = escape_to_home(
            adb_client,
            allowed_packages={pkg.lower() for pkg in (*HOME_LAUNCHER_PACKAGES, SETTINGS_PACKAGE)},
        )
        details["focus_after"] = _format_focus(normalized_focus)
        _emit_marker(adb_client, session_id, f"CONFIG_START expected={expected_channel}")
        component = _prepare_settings_focus(adb_client, session_id)
        _emit_marker(adb_client, session_id, f"SETTINGS_FOCUSED package={component}")
        _emit_marker(adb_client, session_id, "NAV_TO_LIVE_MAPPING")
        _navigate_to_live_customization(adb_client, navigation_delay)
        xml_data, diag_excerpt = _ensure_live_channel_screen(adb_client, session_id)
        details["ui_prompt_detected"] = True
        details["diagnostics_excerpt"] = diag_excerpt
        details["value_before"] = read_live_channel_value(xml_data)
        _emit_marker(adb_client, session_id, "CONFIG_UI_REACHED")
        set_result = set_live_channel_value(
            adb_client,
            expected_channel,
            initial_xml=xml_data,
        )
        value_after = set_result.get("value_after")
        details.update(
            {
                "value_after": value_after,
                "confirm_method_used": set_result.get("confirm_method_used"),
                "retries": set_result.get("retries", 0),
            }
        )
        _emit_marker(adb_client, session_id, f"CONFIG_VALUE_AFTER={value_after}")
        time.sleep(settle_delay)
        _emit_marker(adb_client, session_id, f"CONFIG_SAVED channel={expected_channel}")
        _emit_marker(adb_client, session_id, f"CONFIG_DONE expected={expected_channel}")
        return details
    except LiveChannelSetError as exc:
        details.update(exc.details)
        if "diagnostics_excerpt" not in details:
            details["diagnostics_excerpt"] = build_diagnostics_excerpt(adb_client)
        raise LiveConfigurationError(str(exc), details) from exc
    except LiveConfigurationError:
        raise
    except Exception as exc:  # noqa: BLE001
        if "diagnostics_excerpt" not in details:
            details["diagnostics_excerpt"] = build_diagnostics_excerpt(adb_client)
        raise LiveConfigurationError(str(exc), details) from exc


def ensure_device_focus_ready(
    adb_client: ADBClient,
    session_id: str,
    *,
    timeout: float = 20.0,
) -> str:
    focus = escape_to_home(
        adb_client,
        allowed_packages={pkg.lower() for pkg in (*HOME_LAUNCHER_PACKAGES, SETTINGS_PACKAGE)},
        max_steps=max(1, int(timeout // 2)),
    )
    if focus.package.lower() not in {pkg.lower() for pkg in (*HOME_LAUNCHER_PACKAGES, SETTINGS_PACKAGE)}:
        raise RuntimeError(
            f"Device not in controllable state (focus={_format_focus(focus)}, source={focus.source}, raw={focus.raw})"
        )
    return _format_focus(focus)


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
        escape_to_home(
            adb_client,
            allowed_packages={pkg.lower() for pkg in (*HOME_LAUNCHER_PACKAGES, SETTINGS_PACKAGE)},
        )
        component = _resolve_settings_component(adb_client)
        _launch_live_button_settings(adb_client, component)
        _wait_for_settings_focus(adb_client, component)
        _emit_marker(adb_client, session_id, f"SETTINGS_OPEN_OK package={component}")
        return component
    except Exception as exc:  # noqa: BLE001
        _emit_marker(adb_client, session_id, f"SETTINGS_OPEN_FAIL error={exc}")
        raise


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
        focus_info = get_current_focus(adb_client)
        if focus_info.package and component_pkg in focus_info.package:
            return
        time.sleep(1.0)
    raise RuntimeError(
        f"Timed out waiting for Settings focus (expected {component_pkg}). "
        f"Current focus: {_format_focus(focus_info)} source={focus_info.source} raw={focus_info.raw}"
    )


def _navigate_to_live_customization(adb_client: ADBClient, delay: float) -> None:
    sequences: Sequence[Sequence[str]] = [
        ("DPAD_RIGHT", "DPAD_RIGHT", "DPAD_DOWN", "DPAD_DOWN", "DPAD_DOWN", "DPAD_CENTER"),
        ("DPAD_DOWN", "DPAD_DOWN", "DPAD_CENTER"),
        ("DPAD_DOWN", "DPAD_CENTER"),
    ]
    for seq in sequences:
        for key in seq:
            _send_keyevent(adb_client, key)
            time.sleep(delay)


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


def _ensure_live_channel_screen(
    adb_client: ADBClient,
    session_id: str,
    *,
    timeout: float = 18.0,
) -> Tuple[str, str]:
    deadline = time.time() + timeout
    last_xml = ""
    while time.time() < deadline:
        xml_data = uia_dump_xml(adb_client)
        last_xml = xml_data
        if xml_has_live_channel_prompt(xml_data):
            snippet = "\n".join(xml_data.splitlines()[:15])
            _emit_marker(adb_client, session_id, "LIVE_CHANNEL_SCREEN_OK")
            return xml_data, snippet
        time.sleep(1.0)
    _emit_marker(adb_client, session_id, "LIVE_CHANNEL_SCREEN_FAIL")
    diagnostics = build_diagnostics_excerpt(adb_client, xml_data=last_xml)
    raise LiveConfigurationError(
        "Live channel customization screen not detected.",
        {"diagnostics_excerpt": diagnostics, "ui_prompt_detected": False},
    )


def _send_keyevent(adb_client: ADBClient, key_token: str) -> None:
    token = key_token.strip().upper()
    prefix = "" if token.startswith("KEYCODE_") else "KEYCODE_"
    adb_client.shell(f"input keyevent {prefix}{token}")


def _format_focus(focus: FocusInfo) -> str:
    pkg = focus.package or "unknown"
    act = focus.activity or "unknown"
    return f"{pkg}/{act}"
