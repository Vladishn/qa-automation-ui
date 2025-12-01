"""Helpers for listing and filtering adb-connected devices."""

from __future__ import annotations

import re
import subprocess
from typing import Dict, List, Optional

ADB_LINE_PATTERN = re.compile(
    r"^(?P<serial>[^\s]+)\s+(?P<state>device|offline|unauthorized)\s*(?P<details>.*)$"
)


def list_connected_devices(adb_path: str = "adb") -> List[Dict[str, str]]:
    """Run `adb devices -l` and parse the connected device list."""
    try:
        result = subprocess.run(
            (adb_path, "devices", "-l"),
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("adb binary not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"adb devices failed: {exc.stderr}") from exc

    devices: List[Dict[str, str]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        match = ADB_LINE_PATTERN.match(line)
        if not match:
            continue
        devices.append(match.groupdict())
    return devices


def find_device_by_ip(ip_or_serial: str, adb_path: str = "adb") -> Optional[Dict[str, str]]:
    """Return the first device whose serial or details match the requested IP."""
    for device in list_connected_devices(adb_path=adb_path):
        if device["serial"] == ip_or_serial or ip_or_serial in device.get("details", ""):
            return device
    return None
