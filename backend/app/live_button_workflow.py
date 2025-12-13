from __future__ import annotations

import subprocess
import time
from typing import Callable, Optional, Sequence

import re

from src.adb.adb_client import ADBClient

LIVE_APP_PACKAGE = "il.co.partnertv.atv"
LIVE_LOG_TAG = "QA_LIVE"
SETTINGS_COMPONENT_CANDIDATES = (
    "com.google.android.tv.settings/.MainSettings",
    "com.android.tv.settings/.MainSettings",
)
SAVED_CHANNEL_REGEX = re.compile(r"saved\s+.*channel\s*:\s*(\d+)", re.IGNORECASE)


def configure_live_mapping(
    adb_client: ADBClient,
    expected_channel: int,
    *,
    navigation_delay: float = 0.5,
    settle_delay: float = 4.0,
    saved_channel_timeout: float = 20.0,
) -> None:
    """Configure the Live button mapping through Android TV settings."""
    _emit_marker(adb_client, f"CONFIG_START channel={expected_channel}")
    component = _prepare_settings_focus(adb_client)
    _emit_marker(adb_client, f"SETTINGS_FOCUSED pkg={component}")
    _emit_marker(adb_client, "NAV_TO_LIVE_MAPPING")
    _navigate_to_live_customization(adb_client, navigation_delay)
    _emit_marker(adb_client, f"CHANNEL_TYPED channel={expected_channel}")
    _input_channel_digits(adb_client, expected_channel, navigation_delay)
    _emit_marker(adb_client, "SAVE_TRIGGERED")
    time.sleep(settle_delay)
    _wait_for_saved_channel_log(adb_client, expected_channel, timeout=saved_channel_timeout)
    _emit_marker(adb_client, f"CONFIG_DONE channel={expected_channel}")


def live_phase_press(
    adb_client: ADBClient,
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
    _emit_marker(adb_client, f"PHASE_START name={normalized_phase} expected={expected_channel}")

    if do_reboot:
        _emit_marker(adb_client, f"{normalized_phase}_REBOOT_INIT")
        _reboot_device(adb_client, reboot_timeout=reboot_timeout)
        _emit_marker(adb_client, f"{normalized_phase}_DEVICE_READY expected_channel={expected_channel}")
        if post_reboot_callback:
            post_reboot_callback()

    if do_force_stop:
        _emit_marker(adb_client, f"{normalized_phase}_FORCE_STOP")
        adb_client.shell(f"am force-stop {LIVE_APP_PACKAGE}")
        time.sleep(3.0)

    adb_client.shell("input keyevent 172")
    _emit_marker(adb_client, "LIVE_KEY_SENT")
    time.sleep(wait_after_press)
    _emit_marker(adb_client, f"PHASE_DONE name={normalized_phase} verdict=UNKNOWN")


def _emit_marker(adb_client: ADBClient, message: str) -> None:
    escaped = message.replace('"', '\\"')
    adb_client.shell(f'log -t {LIVE_LOG_TAG} "{escaped}"', check=False)
    time.sleep(0.3)


def _prepare_settings_focus(adb_client: ADBClient) -> str:
    _exit_to_home(adb_client)
    component = _resolve_settings_component(adb_client)
    _launch_live_button_settings(adb_client, component)
    _wait_for_settings_focus(adb_client, component)
    return component


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
    """Open Android TV Settings where the Live button mapping resides."""
    adb_client.shell(f"am start -a android.intent.action.MAIN -n {component}")
    time.sleep(3.0)


def _wait_for_settings_focus(adb_client: ADBClient, component: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    component_pkg = component.split("/")[0]
    while time.time() < deadline:
        focus_info = _get_current_focus(adb_client)
        if component_pkg in focus_info:
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
        # Reach Remotes & Accessories tile.
        ("DPAD_RIGHT", "DPAD_RIGHT", "DPAD_DOWN", "DPAD_DOWN", "DPAD_DOWN", "DPAD_CENTER"),
        # Enter PartnerRC entry.
        ("DPAD_DOWN", "DPAD_DOWN", "DPAD_CENTER"),
        # Focus Live button customization action.
        ("DPAD_DOWN", "DPAD_CENTER"),
    ]
    for sequence in navigation_sequences:
        for key in sequence:
            _send_keyevent(adb_client, key)
            time.sleep(delay)


def _input_channel_digits(adb_client: ADBClient, channel: int, delay: float) -> None:
    digits = list(str(abs(channel)))
    for digit in digits:
        _send_keyevent(adb_client, digit)
        time.sleep(delay)
    _send_keyevent(adb_client, "ENTER")
    time.sleep(delay)
    _send_keyevent(adb_client, "DPAD_CENTER")


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
        focus_line = adb_client.shell("dumpsys window windows | grep mCurrentFocus", check=False) or ""
    except Exception:
        focus_line = ""
    return focus_line.strip()


def _wait_for_saved_channel_log(
    adb_client: ADBClient,
    expected_channel: int,
    *,
    timeout: float,
) -> None:
    deadline = time.time() + timeout
    observed: Optional[int] = None
    while time.time() < deadline:
        try:
            # Capture a small slice of the recent logcat buffer.
            snippet = adb_client.shell("logcat -d -v brief | tail -n 400", check=False) or ""
        except Exception:
            snippet = ""
        for match in SAVED_CHANNEL_REGEX.finditer(snippet):
            try:
                observed = int(match.group(1))
            except (TypeError, ValueError):
                continue
        if observed is not None:
            if observed == expected_channel:
                return
            raise RuntimeError(
                f"Saved channel mismatch: logs reported {observed}, expected {expected_channel}."
            )
        time.sleep(1.0)
    raise RuntimeError(
        f"Timed out waiting for Saved channel log (expected {expected_channel}). "
        f"Focus snapshot: {_get_current_focus(adb_client)}"
    )
