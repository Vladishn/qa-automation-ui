# backend/app/adb_service.py
from __future__ import annotations

import platform
import socket
import subprocess
import textwrap
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class AdbPrecheckStatus(str, Enum):
    OK = "ok"
    HOST_UNREACHABLE = "host_unreachable"
    ADB_PORT_CLOSED = "adb_port_closed"
    ADB_NOT_INSTALLED = "adb_not_installed"
    ADB_ERROR = "adb_error"
    INTERNAL_ERROR = "internal_error"


@dataclass
class AdbPrecheckResult:
    status: AdbPrecheckStatus
    message: str
    adb_stdout: str = ""
    adb_stderr: str = ""
    ping_ok: Optional[bool] = None
    tcp_port_open: Optional[bool] = None


def precheck(ip: str, port: int = 5555, max_retries: int = 3) -> AdbPrecheckResult:
    """
    High-level ADB precheck:
    1. Ping host (best-effort).
    2. TCP connectivity to ip:port.
    3. adb connect with retries.
    4. Return structured result with clear reason.
    """
    try:
        ping_ok = _ping_host(ip)
        tcp_ok = _check_tcp_port(ip, port)

        adb_stdout = ""
        adb_stderr = ""
        last_exc: Optional[Exception] = None

        for _attempt in range(max_retries):
            try:
                adb_stdout, adb_stderr = _adb_connect(ip, port)
                lower_out = (adb_stdout or "").lower()

                # adb connect usually prints "connected to" or "already connected to"
                if "connected to" in lower_out or "already connected to" in lower_out:
                    return AdbPrecheckResult(
                        status=AdbPrecheckStatus.OK,
                        message=f"ADB connected successfully to {ip}:{port}.",
                        adb_stdout=adb_stdout,
                        adb_stderr=adb_stderr,
                        ping_ok=ping_ok,
                        tcp_port_open=tcp_ok,
                    )
            except FileNotFoundError as e:
                # adb binary missing
                return AdbPrecheckResult(
                    status=AdbPrecheckStatus.ADB_NOT_INSTALLED,
                    message=(
                        "adb executable not found on PATH. "
                        "Install Android Platform Tools and ensure 'adb' is available."
                    ),
                    adb_stdout="",
                    adb_stderr=str(e),
                    ping_ok=ping_ok,
                    tcp_port_open=tcp_ok,
                )
            except Exception as e:
                last_exc = e

        # אם הגענו לכאן – אף ניסיון לא הצליח
        status, msg = _interpret_failure(
            ip=ip,
            port=port,
            ping_ok=ping_ok,
            tcp_ok=tcp_ok,
            adb_stderr=adb_stderr,
        )

        if status == AdbPrecheckStatus.INTERNAL_ERROR and last_exc is not None:
            msg = f"Internal error while running adb connect for {ip}:{port}: {last_exc!r}"

        return AdbPrecheckResult(
            status=status,
            message=msg,
            adb_stdout=adb_stdout,
            adb_stderr=adb_stderr,
            ping_ok=ping_ok,
            tcp_port_open=tcp_ok,
        )

    except Exception as e:
        # אולטרה־דפנסיבי – לא להפיל את השרת בגלל כשל infra
        return AdbPrecheckResult(
            status=AdbPrecheckStatus.INTERNAL_ERROR,
            message=f"Unexpected error during adb precheck for {ip}:{port}: {e!r}",
        )


# ---------------------- helpers ----------------------


def _ping_host(ip: str) -> Optional[bool]:
    """
    Best-effort ICMP ping.

    Returns:
    - True  → ping succeeded
    - False → ping clearly failed
    - None  → ping not available / could not be executed
    """
    system = platform.system().lower()
    if system not in ("linux", "darwin", "windows"):
        return None

    count_flag = "-c" if system in ("linux", "darwin") else "-n"
    cmd = ["ping", count_flag, "1", ip]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0
    except FileNotFoundError:
        # ping binary not available
        return None
    except Exception:
        return None


def _check_tcp_port(ip: str, port: int) -> Optional[bool]:
    """
    Check reachability of TCP ip:port.

    Returns:
    - True  → port is reachable
    - False → refused / timed out
    - None  → internal error during check
    """
    try:
        with socket.create_connection((ip, port), timeout=5):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False
    except Exception:
        return None


def _adb_connect(ip: str, port: int) -> Tuple[str, str]:
    cmd = ["adb", "connect", f"{ip}:{port}"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    return stdout, stderr


def _interpret_failure(
    ip: str,
    port: int,
    ping_ok: Optional[bool],
    tcp_ok: Optional[bool],
    adb_stderr: str,
) -> Tuple[AdbPrecheckStatus, str]:
    """
    Map adb + network symptoms into a precise, actionable failure.
    Includes an explicit hint that sometimes the issue is on the test machine
    (stuck adb server / local networking) and reboot may help.
    """
    lower_err = (adb_stderr or "").lower()

    # בסיס להודעה כללית על בעיית מכונה (מה שאתה חווית – הסתדר אחרי reboot)
    host_hint = textwrap.dedent(
        """
        If STB configuration looks correct (ADB over network enabled, correct IP, no firewall on the STB side),
        there might be a stuck ADB server or local networking issue on the test machine.
        Try restarting the ADB server (`adb kill-server` / `adb start-server`) or rebooting the machine.
        """
    ).strip()

    # 1. No route to host
    if "no route to host" in lower_err:
        if ping_ok:
            # זה בדיוק המקרה שלך: IP חי, אבל 5555 לא נגיש
            base_msg = textwrap.dedent(
                f"""
                adb reported 'No route to host' for {ip}:{port}, but ICMP ping succeeded.
                IP is reachable but TCP {port} is blocked or ADB over network is disabled on the STB.
                """
            ).strip()
            full_msg = f"{base_msg}\n\n{host_hint}"
            return AdbPrecheckStatus.ADB_PORT_CLOSED, full_msg
        else:
            msg = (
                f"adb reported 'No route to host' for {ip}:{port}, and ping did not succeed. "
                "The STB may be offline, on a different network, or blocking all IP traffic."
            )
            return AdbPrecheckStatus.HOST_UNREACHABLE, msg

    # 2. Connection refused → host עונה אבל הפורט סגור
    if "connection refused" in lower_err:
        base_msg = (
            f"Host {ip} is reachable but TCP port {port} refused the connection. "
            "ADB over network may be disabled on the STB or a firewall is blocking the port."
        )
        full_msg = f"{base_msg}\n\n{host_hint}"
        return AdbPrecheckStatus.ADB_PORT_CLOSED, full_msg

    # 3. ביטויים כלליים של כישלון חיבור
    if any(
        phrase in lower_err
        for phrase in (
            "failed to connect",
            "cannot connect",
            "unable to connect",
            "offline",
        )
    ):
        if ping_ok is False:
            msg = (
                f"Failed to connect to {ip}:{port}, and ping also failed. "
                "The STB may be powered off, disconnected, or on a different network."
            )
            return AdbPrecheckStatus.HOST_UNREACHABLE, msg

        if tcp_ok is False:
            base_msg = (
                f"Failed to connect to {ip}:{port}. TCP port {port} is not reachable. "
                "ADB over network may be disabled or a firewall is blocking the port."
            )
            full_msg = f"{base_msg}\n\n{host_hint}"
            return AdbPrecheckStatus.ADB_PORT_CLOSED, full_msg

        # ping_ok == True and tcp_ok is None/True but adb still fails → שגיאת ADB כללית
        msg = (
            f"adb failed to connect to {ip}:{port}. "
            f"stderr: {adb_stderr or 'no stderr output'}\n\n{host_hint}"
        )
        return AdbPrecheckStatus.ADB_ERROR, msg

    # 4. אין stderr – כשל פנימי / timeout
    if not adb_stderr:
        msg = (
            f"adb connect to {ip}:{port} failed without any stderr output. "
            "This may indicate a timeout or an internal ADB failure.\n\n"
            f"{host_hint}"
        )
        return AdbPrecheckStatus.INTERNAL_ERROR, msg

    # 5. ברירת מחדל: שגיאה כללית של adb
    msg = (
        f"adb connect failed for {ip}:{port}. "
        f"adb stderr: {adb_stderr}\n\n{host_hint}"
    )
    return AdbPrecheckStatus.ADB_ERROR, msg


if __name__ == "__main__":
    # כלי קטן להרצה ידנית, לא חובה בשימוש בשרת
    import argparse
    import json

    parser = argparse.ArgumentParser(description="ADB precheck utility")
    parser.add_argument("ip", help="STB IPv4 address")
    parser.add_argument(
        "--port",
        type=int,
        default=5555,
        help="ADB TCP port (default: 5555)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max adb connect retries (default: 3)",
    )
    args = parser.parse_args()

    res = precheck(ip=args.ip, port=args.port, max_retries=args.retries)
    print(json.dumps(res.__dict__, ensure_ascii=False, indent=2))
